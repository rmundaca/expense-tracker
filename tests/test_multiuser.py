"""Several users: each one's data is fully independent; only administrators manage users."""
import io
import sqlite3
import zipfile

import _isolated_env

import pytest
from fastapi.testclient import TestClient


def create_tx(client, account_id, merchant="Jumbo", amount=1000, **fields):
    payload = {"type": "expense", "amount": amount, "date": "2026-09-10", "merchant": merchant, "account_id": account_id}
    payload.update(fields)
    res = client.post("/api/transactions", json=payload)
    assert res.status_code == 200, res.text
    return res.json()


def first_account(client):
    return client.get("/api/accounts").json()[0]["id"]


# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------

def test_users_start_with_their_own_seeded_data(client, other_client):
    names = lambda c: sorted(a["name"] for a in c.get("/api/accounts").json())
    assert names(client) == names(other_client)  # same defaults...
    client.post("/api/accounts", json={"name": "Solo de admin", "type": "corriente"})
    assert "Solo de admin" in names(client)
    assert "Solo de admin" not in names(other_client)  # ...but separate copies


def test_movements_and_balances_are_independent(client, other_client):
    acc = first_account(client)
    tx = create_tx(client, acc, amount=5000, tags=["viaje"])
    assert other_client.get("/api/transactions").json() == []
    assert all(a["balance"] == 0 for a in other_client.get("/api/accounts").json())
    # Ids are per database: the other user cannot reach, edit or delete the admin's movement
    assert other_client.put(f"/api/transactions/{tx['id']}", json={"amount": 1}).status_code == 404
    assert other_client.delete(f"/api/transactions/{tx['id']}").status_code == 404
    dashboard = other_client.get("/api/stats/dashboard", params={"month": "2026-09"}).json()
    assert dashboard["total_expense"] == 0
    assert client.get("/api/stats/dashboard", params={"month": "2026-09"}).json()["total_expense"] == 5000


def test_settings_and_rules_are_independent(client, other_client):
    client.post("/api/mail/accounts", json={"provider": "gmail", "name": "Gmail", "email": "admin@gmail.com", "password": "abcd efgh"})
    client.put("/api/mail/settings", json={"sync_enabled": True})
    assert other_client.get("/api/mail/accounts").json() == []
    assert other_client.get("/api/mail/settings").json()["sync_enabled"] is False
    rules_before = len(other_client.get("/api/rules").json())
    cat = client.get("/api/categories").json()[0]["id"]
    client.post("/api/rules", json={"pattern": "solo-admin", "category_id": cat})
    assert len(other_client.get("/api/rules").json()) == rules_before


def test_learning_is_independent(client, other_client, db):
    acc = first_account(client)
    cats = {c["name"]: c["id"] for c in client.get("/api/categories").json()}
    tx = create_tx(client, acc, merchant="Kiosko Raro", category_id=cats["Health & Pharmacy"])
    assert client.get("/api/transactions/suggest", params={"merchant": "Kiosko Raro"}).json()["source"] == "memory"
    assert other_client.get("/api/transactions/suggest", params={"merchant": "Kiosko Raro"}).json()["source"] != "memory"
    assert tx["id"]


def test_same_email_can_be_imported_by_two_users(db, other_user):
    from app.core.database import user_session
    from app.models.schemas import Account, Transaction

    other_db = user_session(other_user.id)
    try:
        for session in (db, other_db):
            acc = session.query(Account).first()
            session.add(Transaction(account_id=acc.id, type="expense", amount=10, date="2026-09-01",
                                    email_message_id="<same@bank.cl>", status="pending_review"))
            session.commit()
        assert other_db.query(Transaction).count() == 1
    finally:
        other_db.close()


def test_backup_contains_only_the_users_data(client, other_client, tmp_path):
    create_tx(client, first_account(client), merchant="Privado")
    res = other_client.get("/api/system/backup")
    assert res.status_code == 200 and "bruno" in res.headers["content-disposition"]
    path = tmp_path / "b.db"
    path.write_bytes(res.content)
    con = sqlite3.connect(str(path))
    assert con.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0
    con.close()


def test_reset_data_only_affects_the_user(client, other_client):
    create_tx(client, first_account(client))
    create_tx(other_client, first_account(other_client))
    assert other_client.post("/api/system/reset-data", json={"confirm": "BORRAR"}).json()["deleted"] == 1
    assert len(client.get("/api/transactions").json()) == 1


# ---------------------------------------------------------------------------
# User administration
# ---------------------------------------------------------------------------

def test_only_admins_manage_users(client, other_client):
    assert other_client.get("/api/users").status_code == 403
    assert other_client.post("/api/users", json={"username": "x-user", "password": "secreto1"}).status_code == 403
    assert other_client.get("/api/system/backup-all").status_code == 403
    users = client.get("/api/users").json()
    assert [u["username"] for u in users] == ["admin", "bruno"]
    assert "password_hash" not in users[0]


def test_admin_creates_user_who_can_log_in(client, make_client):
    res = client.post("/api/users", json={"username": "Carla", "password": "carla-pass", "display_name": "Carla"})
    assert res.status_code == 200, res.text
    assert res.json()["username"] == "carla" and res.json()["is_admin"] is False
    assert client.post("/api/users", json={"username": "carla", "password": "otra-pass"}).status_code == 400
    assert client.post("/api/users", json={"username": "dani", "password": "123"}).status_code == 400
    carla = make_client("carla", "carla-pass")
    assert carla.get("/api/auth/status").json()["user"]["display_name"] == "Carla"
    assert len(carla.get("/api/accounts").json()) > 0


def test_deactivating_or_resetting_password_closes_sessions(client, other_client, other_user, make_client):
    res = client.patch(f"/api/users/{other_user.id}", json={"password": "nueva-clave"})
    assert res.status_code == 200
    assert other_client.get("/api/accounts").status_code == 401
    again = make_client("bruno", "nueva-clave")
    assert client.patch(f"/api/users/{other_user.id}", json={"is_active": False}).json()["is_active"] is False
    assert again.get("/api/accounts").status_code == 401
    assert TestClient(again.app).post("/api/auth/login", json={"username": "bruno", "password": "nueva-clave"}).status_code == 401
    client.patch(f"/api/users/{other_user.id}", json={"is_active": True})
    assert make_client("bruno", "nueva-clave").get("/api/accounts").status_code == 200


def test_the_last_admin_is_protected(client, admin, other_user, make_client):
    assert client.patch(f"/api/users/{admin.id}", json={"is_admin": False}).status_code == 400
    assert client.patch(f"/api/users/{admin.id}", json={"is_active": False}).status_code == 400
    assert client.delete(f"/api/users/{admin.id}", params={"confirm": "admin"}).status_code == 400
    # With a second admin, that admin may demote the first one
    client.patch(f"/api/users/{other_user.id}", json={"is_admin": True})
    bruno = make_client("bruno", "bruno-password")
    assert bruno.patch(f"/api/users/{admin.id}", json={"is_admin": False}).json()["is_admin"] is False
    assert client.get("/api/users").status_code == 403


def test_delete_user_archives_their_database(client, other_client, other_user):
    from app.core.config import DELETED_USERS_DIR, user_db_path

    create_tx(other_client, first_account(other_client))
    assert client.delete(f"/api/users/{other_user.id}", params={"confirm": "otro"}).status_code == 400
    res = client.delete(f"/api/users/{other_user.id}", params={"confirm": "bruno"})
    assert res.status_code == 200, res.text
    archived = DELETED_USERS_DIR / res.json()["archived_as"]
    assert archived.exists() and not user_db_path(other_user.id).exists()
    assert other_client.get("/api/accounts").status_code == 401
    # A new user with the same name starts from scratch (ids are never reused)
    new = client.post("/api/users", json={"username": "bruno", "password": "bruno-password"}).json()
    assert new["id"] != other_user.id


def test_full_backup_has_every_database(client, other_user, admin):
    res = client.get("/api/system/backup-all")
    assert res.status_code == 200
    names = set(zipfile.ZipFile(io.BytesIO(res.content)).namelist())
    assert names == {"app.db", f"users/{admin.id}.db", f"users/{other_user.id}.db"}


# ---------------------------------------------------------------------------
# Background jobs
# ---------------------------------------------------------------------------

def test_exchange_rates_are_downloaded_once_for_all_users(admin, other_user, monkeypatch):
    from app.core.database import user_session
    from app.models.schemas import ExchangeRateHistory
    from app.schedulers import tasks
    from app.services import exchange_rates

    calls = []

    def fake_fetch(client, indicator, year=None):
        calls.append((indicator, year))
        return [{"date": f"{year}-09-01", "value": 900.0}]

    monkeypatch.setattr(exchange_rates, "_fetch_series", fake_fetch)
    tasks._rates_job()
    assert len(calls) == len(set(calls)) == len(exchange_rates.CURRENCIES)
    for user in (admin, other_user):
        s = user_session(user.id)
        assert s.query(ExchangeRateHistory).count() == len(exchange_rates.CURRENCIES)
        s.close()


def test_mail_jobs_are_per_user(admin, other_user, monkeypatch):
    from app.core import auth
    from app.core.database import user_session
    from app.models.schemas import set_setting
    from app.schedulers import tasks

    synced = []
    monkeypatch.setattr(tasks, "sync_mail_now", lambda db: synced.append(str(db.get_bind().url)) or {"message": "ok"})
    s = user_session(other_user.id)
    set_setting(s, "mail_sync_enabled", "true")
    s.commit()
    s.close()

    tasks._mail_job(admin.id)  # sync disabled for the admin
    tasks._mail_job(other_user.id)
    assert len(synced) == 1 and synced[0].endswith(f"{other_user.id}.db")

    auth.update_user(other_user.id, is_active=False)
    tasks._mail_job(other_user.id)  # inactive users are skipped
    assert len(synced) == 1


def test_mail_sync_lock_is_per_user(db, other_user):
    from app.core.database import user_session
    from app.services.mail.sync import _sync_lock_for

    other_db = user_session(other_user.id)
    try:
        assert _sync_lock_for(db) is not _sync_lock_for(other_db)
        assert _sync_lock_for(db) is _sync_lock_for(db)
    finally:
        other_db.close()


# ---------------------------------------------------------------------------
# Move from the single-user layout (<= 2.0.x)
# ---------------------------------------------------------------------------

def _build_legacy_db(password_hash=None):
    """A 2.0.x database: seeded schema, one movement and (optionally) the access password."""
    from app.core.config import LEGACY_DB_PATH
    from app.core.database import make_engine
    from app.models.schemas import run_migrations, seed_initial_data
    from sqlalchemy.orm import Session

    from app import i18n

    engine = make_engine(LEGACY_DB_PATH)
    run_migrations(engine)
    with Session(bind=engine) as s, i18n.use("es"):  # installs from before translations were all in Spanish
        seed_initial_data(s)
    engine.dispose()
    con = sqlite3.connect(str(LEGACY_DB_PATH))
    con.execute("UPDATE accounts SET opening_balance = 150000 WHERE id = 1")
    con.execute("INSERT INTO transactions (account_id, type, amount, currency, exchange_rate, base_amount, "
                "base_currency, date, merchant, status) VALUES (1, 'expense', 50000, 'CLP', 1, 50000, 'CLP', "
                "'2026-09-02', 'Jumbo', 'confirmed')")
    con.execute("INSERT INTO settings VALUES ('auth_secret_key', 'old-secret')")
    if password_hash:
        con.execute("INSERT INTO settings VALUES ('auth_password_hash', ?)", (password_hash,))
    con.commit()
    con.close()


@pytest.fixture
def no_users():
    from app.core.config import DATA_DIR, LEGACY_DB_PATH

    _isolated_env.reset_users()
    yield
    for f in DATA_DIR.glob(f"{LEGACY_DB_PATH.name}*"):
        f.unlink()


def _auth_keys(user_id):
    from app.core.config import user_db_path

    con = sqlite3.connect(str(user_db_path(user_id)))
    keys = [r[0] for r in con.execute("SELECT key FROM settings WHERE key LIKE 'auth_%'")]
    con.close()
    return keys


def test_single_user_install_is_moved_to_its_owner(no_users):
    from app.core import auth
    from app.core.app_setup import LEGACY_ADMIN_USERNAME, init_app_database
    from app.core.config import DATA_DIR, LEGACY_DB_PATH
    from app.main import app

    _build_legacy_db(auth.hash_password("clave-antigua"))
    init_app_database()
    init_app_database()  # idempotent

    users = auth.list_users()
    assert [(u.username, u.is_admin) for u in users] == [(LEGACY_ADMIN_USERNAME, True)]
    assert not LEGACY_DB_PATH.exists()
    assert list(DATA_DIR.glob(f"{LEGACY_DB_PATH.name}.pre-multiuser-*"))
    assert _auth_keys(users[0].id) == []

    c = TestClient(app)
    _isolated_env.authenticate(c, LEGACY_ADMIN_USERNAME, "clave-antigua")
    balances = {a["name"]: a["balance"] for a in c.get("/api/accounts").json()}
    assert balances["Cuenta Corriente"] == 100000
    assert c.get("/api/transactions").json()[0]["merchant"] == "Jumbo"


def test_single_user_install_without_password_goes_to_first_admin(no_users):
    from app.core.app_setup import init_app_database
    from app.core.config import LEGACY_DB_PATH
    from app.main import app

    _build_legacy_db()
    init_app_database()
    assert LEGACY_DB_PATH.exists()  # waits for the first-run setup
    c = TestClient(app)
    res = c.post("/api/auth/setup", json={"username": "duena", "password": "secreto1"})
    assert res.status_code == 200, res.text
    assert not LEGACY_DB_PATH.exists()
    assert c.get("/api/transactions").json()[0]["merchant"] == "Jumbo"
    assert _auth_keys(res.json()["user"]["id"]) == []
