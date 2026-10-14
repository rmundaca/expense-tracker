"""Access control: first-run setup, login, lockout, password change and protected routes."""
import _isolated_env  # noqa: F401  (must be imported before any app module)

import pytest
from fastapi.testclient import TestClient

from app.core import auth
from app.main import app


@pytest.fixture
def fresh():
    """Fresh install: no users at all."""
    _isolated_env.reset_users()
    return TestClient(app)


@pytest.fixture
def with_user(fresh):
    auth.create_user("ana", "secreto1", is_admin=True)
    return fresh


def login(client, username="ana", password="secreto1"):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def test_protected_routes_require_session(fresh):
    assert fresh.get("/api/accounts").status_code == 401
    assert fresh.get("/api/system/backup").status_code == 401
    assert fresh.get("/api/users").status_code == 401
    assert fresh.get("/api/health").status_code == 200
    assert fresh.get("/static/css/app.css").status_code == 200
    # Without a session the root serves the login page instead of the app
    assert 'id="loginForm"' in fresh.get("/").text


def test_setup_creates_first_admin_only_once(fresh):
    assert fresh.get("/api/auth/status").json()["configured"] is False
    assert fresh.post("/api/auth/setup", json={"username": "ana", "password": "123"}).status_code == 400
    assert fresh.post("/api/auth/setup", json={"username": "a b", "password": "secreto1"}).status_code == 400
    res = fresh.post("/api/auth/setup", json={"username": "Ana", "password": "secreto1", "display_name": "Ana P."})
    assert res.status_code == 200, res.text
    assert res.json()["user"] == {"id": res.json()["user"]["id"], "username": "ana", "display_name": "Ana P.",
                                  "is_admin": True, "is_active": True}
    assert fresh.get("/api/accounts").status_code == 200
    status = fresh.get("/api/auth/status").json()
    assert status["authenticated"] and status["user"]["username"] == "ana"
    # A second setup must not be able to take over the install
    other = TestClient(app)
    assert other.post("/api/auth/setup", json={"username": "intruso", "password": "hijacked"}).status_code == 409
    assert other.get("/api/accounts").status_code == 401


def test_login_logout(with_user):
    c = with_user
    assert login(c, password="incorrecta").status_code == 401
    assert login(c, username="nadie").status_code == 401
    # Both failures look the same: the response does not reveal which usernames exist
    assert login(c, password="incorrecta").json() == login(c, username="nadie2").json()
    assert login(c, username="  ANA ").status_code == 200  # usernames are case-insensitive
    assert c.get("/api/accounts").status_code == 200
    assert 'class="tabbar"' in c.get("/").text
    c.post("/api/auth/logout")
    assert c.get("/api/accounts").status_code == 401


def test_lockout_is_per_username(with_user):
    auth.create_user("bruno", "secreto2")
    for _ in range(auth.MAX_FAILED_ATTEMPTS):
        login(with_user, password="incorrecta")
    # Even the right password is refused while locked out...
    assert login(with_user).status_code == 429
    # ...but another user from the same address can still log in
    assert login(with_user, "bruno", "secreto2").status_code == 200


def test_lockout_per_ip_across_usernames(with_user):
    for i in range(auth.MAX_FAILED_ATTEMPTS_PER_IP):
        login(with_user, username=f"nadie{i}")
    assert login(with_user).status_code == 429


def test_password_change_invalidates_other_sessions(with_user):
    other = TestClient(app)
    login(other)
    login(with_user)

    bad = with_user.post("/api/auth/change-password", json={"current_password": "x", "new_password": "nuevo123"})
    assert bad.status_code == 400
    short = with_user.post("/api/auth/change-password", json={"current_password": "secreto1", "new_password": "123"})
    assert short.status_code == 400
    ok = with_user.post("/api/auth/change-password", json={"current_password": "secreto1", "new_password": "nuevo123"})
    assert ok.status_code == 200

    assert with_user.get("/api/accounts").status_code == 200
    assert other.get("/api/accounts").status_code == 401
    assert login(other, password="nuevo123").status_code == 200


def test_forged_cookie_is_rejected(with_user):
    with_user.cookies.set(auth.SESSION_COOKIE, "forged.token.value")
    assert with_user.get("/api/accounts").status_code == 401


def test_password_hashing():
    stored = auth.hash_password("secreto1")
    assert "secreto1" not in stored
    assert auth.verify_password("secreto1", stored)
    assert not auth.verify_password("otro", stored)
    assert not auth.verify_password("secreto1", "garbage")


def test_logout_revokes_the_cookie_but_not_other_devices(with_user):
    phone, laptop = with_user, TestClient(app)
    assert login(phone).status_code == 200 and login(laptop).status_code == 200
    stolen = phone.cookies.get(auth.SESSION_COOKIE)
    phone.post("/api/auth/logout")

    thief = TestClient(app)
    thief.cookies.set(auth.SESSION_COOKIE, stolen)
    assert thief.get("/api/accounts").status_code == 401  # the copied cookie no longer works
    assert laptop.get("/api/accounts").status_code == 200  # other sessions stay open

    auth.reset_cache()  # survives a restart: revocations are stored in app.db
    assert thief.get("/api/accounts").status_code == 401


def test_old_failures_are_forgotten(with_user, monkeypatch):
    clock = [1_000_000.0]
    monkeypatch.setattr(auth.time, "time", lambda: clock[0])
    for _ in range(auth.MAX_FAILED_ATTEMPTS - 1):
        login(with_user, password="incorrecta")
    clock[0] += auth.FAILURE_WINDOW + 1  # a typo much later starts a new count instead of locking out
    login(with_user, password="incorrecta")
    assert login(with_user).status_code == 200
