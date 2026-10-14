import _isolated_env  # noqa: F401  (must run before any app import)

import pytest


@pytest.fixture(autouse=True)
def no_rates_network(monkeypatch):
    """Tests never download exchange rates (creating a user starts a background download); tests that need
    rates patch _fetch_series themselves."""
    from app.services import exchange_rates

    def offline(*args, **kwargs):
        raise RuntimeError("no network in tests")
    monkeypatch.setattr(exchange_rates, "_fetch_series", offline)


@pytest.fixture
def admin():
    """Fresh install with a single administrator (the user every `db`/`client` test runs as)."""
    from app.core import auth

    _isolated_env.reset_users()
    return auth.create_user(_isolated_env.TEST_USERNAME, _isolated_env.TEST_PASSWORD, is_admin=True)


@pytest.fixture
def db(admin):
    """The administrator's database: fresh and seeded for each test."""
    from app.core.database import user_session

    session = user_session(admin.id)
    yield session
    session.close()


@pytest.fixture
def client(db):
    """Authenticated API client (the scheduler does not start: no lifespan context)."""
    from fastapi.testclient import TestClient
    from app.main import app

    c = TestClient(app)
    _isolated_env.authenticate(c)
    return c


@pytest.fixture
def make_client():
    """Factory: a new TestClient logged in as the given user."""
    from fastapi.testclient import TestClient
    from app.main import app

    def _make(username, password):
        c = TestClient(app)
        _isolated_env.authenticate(c, username, password)
        return c
    return _make


@pytest.fixture
def other_user(admin):
    """A second, non-admin user."""
    from app.core import auth

    return auth.create_user("bruno", "bruno-password", display_name="Bruno")


@pytest.fixture
def other_client(other_user, make_client):
    return make_client("bruno", "bruno-password")


@pytest.fixture
def ids(db):
    """Handy ids from the seed data (named in English: requests without a language get the default one)."""
    from app.models.schemas import Account, Category

    acc = {a.name: a.id for a in db.query(Account).all()}
    cat = {c.name: c.id for c in db.query(Category).all()}
    return {
        "checking": acc["Checking Account"],
        "card": acc["Credit Card"],
        "usd_card": acc["Credit Card USD"],
        "cash": acc["Cash"],
        "groceries": cat["Groceries & Food"],
        "restaurants": cat["Restaurants & Coffee"],
        "salary": cat["Salary"],
    }


@pytest.fixture
def usd_rate(db):
    """A known USD rate so conversions are deterministic."""
    from app.models.schemas import ExchangeRateHistory

    db.add(ExchangeRateHistory(currency_code="USD", date="2026-01-01", series_id="test", raw_value=900.0, rate_to_clp=900.0))
    db.add(ExchangeRateHistory(currency_code="USD", date="2026-09-01", series_id="test", raw_value=950.0, rate_to_clp=950.0))
    db.commit()
