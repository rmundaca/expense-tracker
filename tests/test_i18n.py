"""Translations: catalog consistency (backend and web app) and the language the server answers in."""
import _isolated_env  # noqa: F401  (must run before any app import)

import json
import re
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parent.parent / "package" / "app" / "static"
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _placeholders(message) -> set:
    return set(PLACEHOLDER.findall(json.dumps(message, ensure_ascii=False)))


def _web_catalog(code: str) -> dict:
    """A js/locales/<code>.js catalog: its object literal is plain JSON."""
    source = (STATIC / "js" / "locales" / f"{code}.js").read_text(encoding="utf-8")
    return json.loads(source[source.index("= {") + 2:source.rindex("}") + 1])


def _check_same_shape(reference: dict, other: dict):
    assert sorted(other) == sorted(reference)
    for key, message in reference.items():
        assert type(other[key]) is type(message), key
        assert _placeholders(other[key]) == _placeholders(message), key
        if isinstance(message, dict):
            assert set(other[key]) == set(message) == {"one", "other"}, key


def test_server_catalogs_match():
    from app.i18n import CATALOGS, DEFAULT_LANGUAGE

    for catalog in CATALOGS.values():
        _check_same_shape(CATALOGS[DEFAULT_LANGUAGE], catalog)


def test_web_catalogs_match():
    english = _web_catalog("en")
    _check_same_shape(english, _web_catalog("es"))
    assert len(english["date.months"]) == 12 and len(english["date.weekdays"]) == 7


def test_every_key_in_the_code_exists():
    """Keys used literally (t("..."), tHtml("..."), data-i18n="...") must be in the catalogs."""
    from app.i18n import CATALOGS

    web = _web_catalog("en")
    web_sources = [STATIC / "js" / "app.js", STATIC / "js" / "api.js", STATIC / "index.html", STATIC / "login.html"]
    used = set()
    for path in web_sources:
        text = path.read_text(encoding="utf-8")
        used |= set(re.findall(r'\btHtml?\("([\w.]+)"', text))
        used |= set(re.findall(r'data-i18n(?:-[\w-]+)?="([\w.]+)"', text))
    assert used and not used - set(web)

    server_used = set()
    for path in (Path(__file__).resolve().parent.parent / "package" / "app").rglob("*.py"):
        server_used |= set(re.findall(r'\bt(?:_in)?\((?:\w+, )?"([\w.]+)"', path.read_text(encoding="utf-8")))
    assert server_used and not server_used - set(CATALOGS["en"])


def test_translate_and_plurals():
    from app import i18n

    with i18n.use("es"):
        assert i18n.t("mail.new_transactions", count=1) == "1 movimiento nuevo"
        assert i18n.t("mail.new_transactions", count=0) == "0 movimientos nuevos"
        assert i18n.t("auth.locked", seconds=30) == "Demasiados intentos fallidos. Espera 30 segundos."
    assert i18n.t("mail.new_transactions", count=2) == "2 new transactions"
    assert i18n.all_variants("system.reset_word") == ["DELETE", "BORRAR"]


@pytest.mark.parametrize("cookie, header, expected", [
    (None, None, "en"),
    ("es", None, "es"),
    ("fr", "es-CL,es;q=0.9,en;q=0.8", "es"),  # unsupported cookie: the browser's preference decides
    (None, "fr-FR, en;q=0.5, es;q=0.9", "es"),  # by quality, not by order
    ("en", "es", "en"),  # the language chosen in the app wins over the browser's
])
def test_language_resolution(cookie, header, expected):
    from app import i18n

    assert i18n.resolve(cookie, header) == expected


def test_api_errors_follow_the_language_cookie(client):
    res = client.post("/api/categories", json={"name": "", "type": "expense"})
    assert res.json()["detail"] == "Name and type (expense/income) are required"
    client.cookies.set("lang", "es")
    res = client.post("/api/categories", json={"name": "", "type": "expense"})
    assert res.json()["detail"] == "Nombre y tipo (gasto/ingreso) son obligatorios"


def test_new_users_get_default_data_in_their_language(admin):
    from fastapi.testclient import TestClient
    from app.core import auth
    from app.core.database import user_session
    from app.main import app
    from app.models.schemas import Category, get_setting

    auth.create_user("lucia", "lucia-password", display_name="Lucía")
    client = TestClient(app, cookies={"lang": "es"})
    _isolated_env.authenticate(client, "lucia", "lucia-password")
    names = {c["name"] for c in client.get("/api/categories").json()}
    assert "Supermercado & Alimentos" in names and "Groceries & Food" not in names

    user = auth.find_user("lucia")
    db = user_session(user.id)
    try:
        assert get_setting(db, "language") == "es"  # what background jobs will write in
        assert {c.name for c in db.query(Category)} == names
    finally:
        db.close()


def test_language_setting_drives_background_messages(client, db):
    from app import i18n
    from app.models.schemas import get_setting
    from app.schedulers import tasks
    from app.services.mail import sync

    assert client.put("/api/system/language", json={"language": "es"}).json() == {"language": "es"}
    assert client.put("/api/system/language", json={"language": "xx"}).status_code == 400
    db.expire_all()
    assert get_setting(db, "language") == "es"
    with i18n.use(tasks._user_language(db)):
        assert sync.sync_mail_now(db)["message"] == "Agrega una casilla de correo."


def test_csv_import_finds_default_categories_named_in_another_language(db):
    """A database seeded in English, imported while the app is in Spanish (and vice versa)."""
    from app import i18n
    from app.services.csv_import import import_csv

    csv = ("Date,Account,Category,Tags,Expense amount,Income amount,Currency,In main currency,Main currency,Description\n"
           "14-08-22,Checking Account,Food & Drinks,restaurants,6.990,0,CLP,6.990,CLP,Sushi\n")
    with i18n.use("es"):
        res = import_csv(db, csv)
    assert res["categories_created"] == 0 and res["accounts_created"] == 0
    assert "importados" in res["message"]


def test_reset_accepts_the_confirmation_word_of_any_language(client):
    assert client.post("/api/system/reset-data", json={"confirm": "nope"}).json()["detail"] == "Type DELETE to confirm"
    assert client.post("/api/system/reset-data", json={"confirm": "delete"}).status_code == 200
    assert client.post("/api/system/reset-data", json={"confirm": "BORRAR"}).status_code == 200
