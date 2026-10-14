"""Mailboxes: encrypted credentials, Gmail migration, IMAP/POP3 sources, Outlook OAuth and multi-mailbox sync."""
import os
import sqlite3
import time
from email.utils import formatdate

import pytest

BANK_SENDER = "Banco de Chile <enviodigital@bancochile.cl>"
BANK_BODY = ("Te informamos que se ha realizado una compra por $22.347 con Tarjeta de Crédito ****1234 "
             "en UNIMARC CENTRO el 16/09/2026 19:46.")


def raw_email(msg_id, sender=BANK_SENDER, body=BANK_BODY, age_days=0):
    return (f"Message-ID: {msg_id}\r\nFrom: {sender}\r\nSubject: Compra con Tarjeta\r\n"
            f"Date: {formatdate(time.time() - age_days * 86400)}\r\n\r\n{body}\r\n").encode()


# ---------------------------------------------------------------------------
# Encryption
# ---------------------------------------------------------------------------

def test_credentials_round_trip_and_tampering_is_detected():
    from app.core.crypto import CredentialError, decrypt, encrypt

    token = encrypt("clave secreta ñ")
    assert token.startswith("enc1:") and "clave" not in token
    assert decrypt(token) == "clave secreta ñ"
    assert encrypt("x") != encrypt("x")  # random nonce
    assert encrypt("") == "" and decrypt("") == ""
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    with pytest.raises(CredentialError):
        decrypt(tampered)
    with pytest.raises(CredentialError):
        decrypt("texto plano")


def test_key_lives_outside_the_databases():
    from app.core import crypto
    from app.core.config import DATA_DIR, USERS_DIR

    crypto.encrypt("x")
    assert crypto.KEY_PATH.parent == DATA_DIR and crypto.KEY_PATH.exists()
    assert USERS_DIR not in crypto.KEY_PATH.parents


# ---------------------------------------------------------------------------
# v3 -> v4 migration
# ---------------------------------------------------------------------------

def test_gmail_settings_become_an_encrypted_mailbox(tmp_path):
    from app.core.crypto import decrypt
    from app.core.database import make_engine
    from app.models.schemas import MailAccount, get_setting, run_migrations
    from sqlalchemy.orm import Session

    path = tmp_path / "v3.db"
    engine = make_engine(path)
    run_migrations(engine)
    con = sqlite3.connect(str(path))
    con.execute("UPDATE settings SET value = '3' WHERE key = 'schema_version'")
    con.execute("DELETE FROM settings WHERE key LIKE 'mail_%'")
    con.executemany("INSERT INTO settings VALUES (?, ?)", [
        ("gmail_email", "yo@gmail.com"), ("gmail_app_password", "abcdefghijklmnop"), ("gmail_sync_enabled", "true"),
        ("gmail_sync_interval_mins", "60"), ("gmail_lookback_days", "14"), ("gmail_last_sync", "2026-10-01 10:00:00"),
    ])
    con.commit()
    run_migrations(engine)
    run_migrations(engine)  # idempotent

    with Session(bind=engine) as db:
        (box,) = db.query(MailAccount).all()
        assert (box.provider, box.email, box.host, box.port) == ("gmail", "yo@gmail.com", "imap.gmail.com", 993)
        assert decrypt(box.secret) == "abcdefghijklmnop"
        assert box.last_sync == "2026-10-01 10:00:00"
        assert get_setting(db, "mail_sync_enabled") == "true" and get_setting(db, "mail_sync_interval_mins") == "60"
        assert get_setting(db, "mail_lookback_days") == "14" and get_setting(db, "schema_version") == "4"
    keys = {r[0] for r in con.execute("SELECT key FROM settings")}
    stored = [r[0] for r in con.execute("SELECT secret FROM mail_accounts")]
    con.close()
    engine.dispose()
    assert not any(k.startswith("gmail_") for k in keys)
    assert "abcdefghijklmnop" not in stored[0]  # never in plain text in the database file


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def stored_secret(db, box_id):
    from app.models.schemas import MailAccount

    db.expire_all()
    return db.get(MailAccount, box_id).secret


def test_mailbox_api_never_returns_or_stores_the_password(client, db):
    from app.core.crypto import decrypt

    box = client.post("/api/mail/accounts", json={"provider": "gmail", "name": "Personal", "email": "yo@gmail.com",
                                                  "password": "abcd efgh ijkl mnop", "host": "evil.example.com"}).json()
    assert box["has_secret"] and box["host"] == "imap.gmail.com"  # Gmail's server cannot be changed
    assert "secret" not in box and "password" not in box
    assert decrypt(stored_secret(db, box["id"])) == "abcdefghijklmnop"  # app passwords are shown with spaces

    other = client.post("/api/mail/accounts", json={"provider": "imap", "name": "Trabajo", "email": "yo",
                                                    "host": "mail.empresa.cl", "security": "starttls", "password": "p"}).json()
    assert (other["port"], other["security"]) == (143, "starttls")
    assert [b["name"] for b in client.get("/api/mail/accounts").json()] == ["Personal", "Trabajo"]


def test_changing_the_server_discards_the_stored_password(client, db):
    box = client.post("/api/mail/accounts", json={"provider": "imap", "name": "X", "email": "yo",
                                                  "host": "mail.uno.cl", "password": "p"}).json()
    # Renaming or changing the port keeps it...
    assert client.put(f"/api/mail/accounts/{box['id']}", json={"name": "Y", "port": 1993}).json()["has_secret"]
    # ...pointing it at another server does not: the password would be sent there
    assert not client.put(f"/api/mail/accounts/{box['id']}", json={"host": "atacante.com"}).json()["has_secret"]
    assert stored_secret(db, box["id"]) == ""


def test_test_endpoint_reuses_the_stored_password_only_for_the_same_server(client, monkeypatch):
    from app.api import mail as mail_api
    from app.core.crypto import decrypt

    tried = []
    monkeypatch.setattr(mail_api, "test_mailbox", lambda acc: tried.append((acc.host, decrypt(acc.secret))) or {"success": True})
    box = client.post("/api/mail/accounts", json={"provider": "imap", "name": "X", "email": "yo",
                                                  "host": "mail.uno.cl", "password": "p"}).json()
    client.post("/api/mail/test", json={"account_id": box["id"]})
    client.post("/api/mail/test", json={"account_id": box["id"], "host": "otro.cl"})
    client.post("/api/mail/test", json={"account_id": box["id"], "host": "otro.cl", "password": "nueva"})
    assert tried == [("mail.uno.cl", "p"), ("otro.cl", ""), ("otro.cl", "nueva")]
    assert client.get("/api/mail/accounts").json()[0]["host"] == "mail.uno.cl"  # testing never saves


def test_mailbox_validation(client):
    def create(**data):
        return client.post("/api/mail/accounts", json={"name": "X", "email": "yo@x.cl", **data})

    assert create(provider="yahoo").status_code == 400
    assert create(provider="imap").status_code == 400  # no server
    assert create(provider="imap", host="h", security="none").status_code == 400  # plain text is not offered
    assert create(provider="pop3", host="h", port=70000).status_code == 400
    assert create(provider="outlook").status_code == 400  # needs the user's own client id
    assert create(provider="gmail", email="sin-arroba").status_code == 400
    assert create(provider="pop3", host="pop.x.cl").json()["port"] == 995


def test_outlook_device_login_stores_the_encrypted_refresh_token(client, db, monkeypatch):
    from app.core.crypto import decrypt
    from app.services.mail import oauth_microsoft

    box = client.post("/api/mail/accounts", json={"provider": "outlook", "name": "Hotmail", "email": "yo@outlook.com",
                                                  "oauth_client_id": "app-1"}).json()
    assert (box["host"], box["oauth_tenant"], box["has_secret"]) == ("outlook.office365.com", "common", False)

    monkeypatch.setattr(oauth_microsoft, "start_device_flow", lambda cid, tenant: {
        "device_code": "dev", "user_code": "ABCD-EFGH", "verification_uri": "https://microsoft.com/devicelogin",
        "expires_in": 900, "interval": 5})
    answers = iter([("pending", {}), ("ok", {"refresh_token": "rt-1"})])
    monkeypatch.setattr(oauth_microsoft, "poll_device_flow", lambda cid, tenant, code: next(answers))

    assert client.post(f"/api/mail/accounts/{box['id']}/oauth/start").json()["user_code"] == "ABCD-EFGH"
    assert client.post(f"/api/mail/accounts/{box['id']}/oauth/poll").json()["status"] == "pending"
    assert client.post(f"/api/mail/accounts/{box['id']}/oauth/poll").json()["status"] == "ok"
    assert decrypt(stored_secret(db, box["id"])) == "rt-1"
    assert client.post(f"/api/mail/accounts/{box['id']}/oauth/poll").json()["status"] == "expired"  # flow finished

    # The token belongs to that app registration: another client id needs a new login
    assert not client.put(f"/api/mail/accounts/{box['id']}", json={"oauth_client_id": "app-2"}).json()["has_secret"]


def test_outlook_refresh_token_rotation_is_saved(db, monkeypatch):
    from app.core.crypto import decrypt, encrypt
    from app.models.schemas import MailAccount
    from app.services.mail import oauth_microsoft, sync

    box = MailAccount(name="O", provider="outlook", email="yo@outlook.com", host="outlook.office365.com", port=993,
                      security="ssl", folders="", secret=encrypt("rt-old"), oauth_client_id="app", oauth_tenant="common")
    db.add(box)
    db.commit()
    monkeypatch.setattr(oauth_microsoft, "refresh_access_token", lambda cid, tenant, rt: ("access", "rt-new"))
    source = sync.open_source(db, box)
    assert source.access_token == "access" and source.user == "yo@outlook.com"
    assert decrypt(stored_secret(db, box.id)) == "rt-new"


def test_xoauth2_string():
    from app.services.mail.oauth_microsoft import xoauth2_string

    assert xoauth2_string("a@b.com", "tok") == b"user=a@b.com\x01auth=Bearer tok\x01\x01"


# ---------------------------------------------------------------------------
# IMAP and POP3 sources
# ---------------------------------------------------------------------------

def test_imap_folder_names():
    from app.services.mail.sources import find_all_mail_folder, imap_utf7, quote_mailbox

    assert imap_utf7("Notificación") == "Notificaci&APM-n"
    assert imap_utf7("A&B") == "A&-B"
    assert quote_mailbox('Bancos/"Chile"') == '"Bancos/\\"Chile\\""'
    lines = [b'(\\HasNoChildren) "/" "INBOX"', b'(\\HasNoChildren \\All) "/" "[Gmail]/Todos"', b'(\\Trash) "/" Papelera']
    assert find_all_mail_folder(lines) == '"[Gmail]/Todos"'
    assert find_all_mail_folder([b'(\\HasNoChildren) "/" "INBOX"']) is None


class FakeImap:
    """Folders of {number: raw email}; SEARCH returns every message of the selected folder."""

    def __init__(self, folders, all_flag=None):
        self.folders, self.all_flag = folders, all_flag
        self.selected = None
        self.readonly = []

    def select(self, box, readonly=False):
        self.readonly.append(readonly)
        name = box.strip('"')
        if name not in self.folders:
            return "NO", [b""]
        self.selected = name
        return "OK", [b""]

    def search(self, _charset, _criteria):
        return "OK", [b" ".join(str(n).encode() for n in self.folders[self.selected])]

    def list(self):
        return "OK", [b'(\\HasNoChildren) "/" "INBOX"'] + ([f'(\\All) "/" "{self.all_flag}"'.encode()] if self.all_flag else [])

    def fetch(self, num, what):
        assert "PEEK" in what  # never marks emails as read
        raw = self.folders[self.selected][int(num)]
        if "MESSAGE-ID" in what:
            return "OK", [(b"header", raw.split(b"\r\n")[0] + b"\r\n\r\n")]
        return "OK", [(b"body", raw)]


def imap_candidates(fake, folders=None):
    from app.services.mail.sources import ImapSource

    source = ImapSource("h", 993, "ssl", "u", password="p", folders=folders)
    source.mail = fake
    return [(msg_id, load()) for msg_id, load in source.candidates(["enviodigital@bancochile.cl"], 7)], source


def test_imap_reads_the_inbox_and_falls_back_to_the_all_mail_folder():
    inbox_only = FakeImap({"INBOX": {1: raw_email("<a@x>")}, "Archivo": {1: raw_email("<b@x>")}}, all_flag="Archivo")
    got, source = imap_candidates(inbox_only)
    assert [m for m, _ in got] == ["<a@x>"] and source.found == 1
    assert got[0][1] == raw_email("<a@x>")

    archived = FakeImap({"INBOX": {}, "Archivo": {1: raw_email("<b@x>")}}, all_flag="Archivo")
    assert [m for m, _ in imap_candidates(archived)[0]] == ["<b@x>"]
    assert all(archived.readonly)


def test_imap_searches_only_the_configured_folders():
    fake = FakeImap({"INBOX": {1: raw_email("<a@x>")}, "Bancos": {1: raw_email("<b@x>")},
                     "Pagos": {1: raw_email("<c@x>")}})
    got, _ = imap_candidates(fake, folders=["Bancos", "Pagos", "No existe"])
    assert [m for m, _ in got] == ["<b@x>", "<c@x>"]


class FakePop3:
    def __init__(self, messages):
        self.messages = messages  # oldest first, like POP3 numbering
        self.retrieved, self.calls = [], []

    def stat(self):
        return len(self.messages), 0

    def top(self, n, _lines):
        self.calls.append(("top", n))
        head = self.messages[n - 1].split(b"\r\n\r\n")[0]
        return b"+OK", head.split(b"\r\n"), 0

    def retr(self, n):
        self.retrieved.append(n)
        return b"+OK", self.messages[n - 1].split(b"\r\n"), 0

    def dele(self, n):
        raise AssertionError("POP3 must never delete")


def test_pop3_scans_back_to_the_lookback_and_filters_senders():
    from app.services.mail import sources

    old = [raw_email(f"<old{i}@x>", age_days=30) for i in range(sources.POP3_OLDER_STREAK_STOP)]
    recent = [raw_email("<r1@x>", age_days=2), raw_email("<spam@x>", sender="otro@tienda.cl"),
              raw_email("<r2@x>", age_days=1)]
    fake = FakePop3([raw_email("<ancient@x>", age_days=40)] + old + recent)
    source = sources.Pop3Source("h", 995, "ssl", "u", "p")
    source.mail = fake
    got = [(msg_id, load()) for msg_id, load in source.candidates(["enviodigital@bancochile.cl"], 7)]
    assert [m for m, _ in got] == ["<r2@x>", "<r1@x>"]
    assert source.found == 2 and len(fake.retrieved) == 2
    # Stopped after a run of old emails: the oldest one was never read
    assert ("top", 1) not in fake.calls


def test_pop3_catches_up_since_the_last_successful_sync():
    from datetime import datetime, timedelta

    from app.models.schemas import MailAccount
    from app.services.mail.sync import _pop3_lookback

    box = MailAccount(last_sync=(datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S"))
    assert _pop3_lookback(box, 7) == 21
    box.last_sync = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d %H:%M:%S")
    assert _pop3_lookback(box, 7) == 60
    box.last_sync = None
    assert _pop3_lookback(box, 7) == 7


# ---------------------------------------------------------------------------
# Sync over several mailboxes
# ---------------------------------------------------------------------------

class FakeSource:
    def __init__(self, emails=None, error=None):
        self.emails, self.error, self.found = emails or [], error, 0

    def __enter__(self):
        if self.error:
            raise self.error
        return self

    def __exit__(self, *exc):
        pass

    def candidates(self, senders, lookback_days):
        for raw in self.emails:
            self.found += 1
            msg_id = raw.split(b"\r\n")[0].split(b": ", 1)[1].decode()
            yield msg_id, (lambda r=raw: r)


def add_box(db, name, enabled=True):
    from app.core.crypto import encrypt
    from app.models.schemas import MailAccount

    box = MailAccount(name=name, provider="imap", email=name, host="h", port=993, security="ssl", folders="",
                      secret=encrypt("p"), is_enabled=enabled)
    db.add(box)
    db.commit()
    return box


def test_sync_reads_every_enabled_mailbox_once_per_email(db, monkeypatch):
    import imaplib

    from app.models.schemas import MailAccount, Transaction, get_setting
    from app.services.mail import sync

    shared = raw_email("<shared@x>")  # forwarded to both mailboxes: same Message-ID
    sources_by_name = {
        "personal": FakeSource([shared, raw_email("<p@x>", body=BANK_BODY.replace("22.347", "1.000"))]),
        "trabajo": FakeSource([shared]),
        "rota": FakeSource(error=imaplib.IMAP4.error("AUTHENTICATIONFAILED")),
        "apagada": FakeSource([raw_email("<off@x>")]),
    }
    for name in sources_by_name:
        add_box(db, name, enabled=name != "apagada")
    monkeypatch.setattr(sync, "open_source", lambda _db, acc: sources_by_name[acc.name])

    res = sync.sync_mail_now(db)
    assert res["success"] and res["new_transactions"] == 2
    assert "rota: The server refused access" in res["message"]
    assert sorted(t.email_message_id for t in db.query(Transaction).all()) == ["<p@x>", "<shared@x>"]
    boxes = {b.name: b for b in db.query(MailAccount).all()}
    assert boxes["personal"].last_sync and not boxes["rota"].last_sync and not boxes["apagada"].last_sync
    assert "refused" in boxes["rota"].last_result
    assert get_setting(db, "mail_last_sync")

    # One mailbox on demand (even a disabled one)
    res = sync.sync_mail_now(db, account_id=boxes["apagada"].id)
    assert res["new_transactions"] == 1


def test_sync_fails_when_no_mailbox_answers(db, monkeypatch):
    from app.services.mail import sync

    assert sync.sync_mail_now(db)["message"] == "Add a mailbox."
    add_box(db, "rota")
    monkeypatch.setattr(sync, "open_source", lambda _db, acc: FakeSource(error=OSError("timed out")))
    res = sync.sync_mail_now(db)
    assert not res["success"] and "Could not connect to h:993" in res["message"]


def test_undecryptable_password_asks_to_type_it_again(db):
    from app.models.schemas import MailAccount
    from app.services.mail import sync

    box = add_box(db, "restaurada")
    db.query(MailAccount).filter(MailAccount.id == box.id).update({MailAccount.secret: "enc1:" + "A" * 80})
    db.commit()
    res = sync.test_mailbox(db.get(MailAccount, box.id))
    assert not res["success"] and "enter the password again" in res["message"]
