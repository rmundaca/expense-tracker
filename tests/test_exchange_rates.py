"""mindicador.cl sync (network mocked) and rate lookup."""
from app.models.schemas import ExchangeRateHistory, Transaction
from app.services import exchange_rates
from app.services.exchange_rates import get_exchange_rate, sync_exchange_rates


def fake_series(client, indicator, year=None):
    values = {"dolar": 950.0, "euro": 1100.0, "uf": 40000.0}
    y = year or 2026
    return [{"date": f"{y}-09-10", "value": values[indicator]}, {"date": f"{y}-09-11", "value": values[indicator] + 1}]


def test_sync_upserts_and_backfills_years_with_movements(db, ids, monkeypatch):
    monkeypatch.setattr(exchange_rates, "_fetch_series", fake_series)
    db.add(Transaction(account_id=ids["checking"], type="expense", amount=1, currency="CLP", exchange_rate=1,
                       base_amount=1, date="2024-05-01", status="confirmed"))
    db.commit()
    first = sync_exchange_rates(db)
    assert first["success"] and first["inserted"] > 0
    years = {r.date[:4] for r in db.query(ExchangeRateHistory).filter(ExchangeRateHistory.currency_code == "USD")}
    assert {"2024", "2025"} <= years  # past years with movements were backfilled
    again = sync_exchange_rates(db)
    assert again["inserted"] == 0  # no duplicates


def test_sync_failure_is_reported(db, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("no network")
    monkeypatch.setattr(exchange_rates, "_fetch_series", boom)
    res = sync_exchange_rates(db)
    assert not res["success"] and "no network" in res["message"]


def test_rate_lookup_uses_previous_business_day(db, usd_rate):
    assert get_exchange_rate(db, "CLP") == 1.0
    assert get_exchange_rate(db, "USD", "2026-09-13") == 950.0   # after the last value
    assert get_exchange_rate(db, "USD", "2026-05-01") == 900.0   # between values
    assert get_exchange_rate(db, "USD", "2020-01-01") == 900.0   # before any value: oldest known
    assert get_exchange_rate(db, "usd") == 950.0                  # latest
    assert get_exchange_rate(db, "EUR") == exchange_rates.FALLBACK_RATES["EUR"]


def _rate(db, code, day, value):
    db.add(ExchangeRateHistory(currency_code=code, date=day, series_id="test", raw_value=value, rate_to_clp=value))
    db.commit()


def test_provisional_rates(db):
    from app.services.exchange_rates import resolve_rate
    assert resolve_rate(db, "EUR", "2026-09-10") == (exchange_rates.FALLBACK_RATES["EUR"], True)  # nothing stored
    _rate(db, "USD", "2026-09-04", 940.0)  # a Friday
    _rate(db, "USD", "2026-09-07", 945.0)  # the Monday after
    assert resolve_rate(db, "USD", "2026-09-04 10:00:00") == (940.0, False)  # its own day
    assert resolve_rate(db, "USD", "2026-09-06") == (940.0, False)  # Sunday: Friday's value is the official one
    assert resolve_rate(db, "USD", "2026-09-08") == (945.0, True)   # newer values may still be published
    assert resolve_rate(db, "USD", "2026-09-30") == (945.0, True)   # stale
    assert resolve_rate(db, "USD", "2026-01-01") == (940.0, True)   # before any value: oldest known


def test_uf_without_date_never_uses_future_values(db):
    from datetime import date, timedelta
    today = date.today()
    _rate(db, "UF", today.isoformat(), 40000.0)
    _rate(db, "UF", (today + timedelta(days=5)).isoformat(), 40100.0)  # the UF series runs ahead
    assert get_exchange_rate(db, "UF") == 40000.0


def test_provisional_rates_are_corrected_after_sync(client, db, ids, monkeypatch):
    res = client.post("/api/transactions", json={"type": "expense", "amount": 10, "currency": "USD", "date": "2026-09-10",
                                                 "account_id": ids["usd_card"], "category_id": ids["groceries"]}).json()
    assert res["rate_estimated"] is True and res["exchange_rate"] == exchange_rates.FALLBACK_RATES["USD"]
    typed = client.post("/api/transactions", json={"type": "expense", "amount": 10, "currency": "USD", "date": "2026-09-10",
                                                   "exchange_rate": 999, "account_id": ids["usd_card"],
                                                   "category_id": ids["groceries"]}).json()
    assert typed["rate_estimated"] is False

    monkeypatch.setattr(exchange_rates, "_fetch_series", fake_series)
    status = client.post("/api/exchange-rates/sync").json()
    assert status["success"] and status["fixed"] == 1 and status["estimated_count"] == 0
    assert {c["code"]: c["rate"] for c in status["currencies"]}["USD"] == 951.0
    fixed = {t["id"]: t for t in client.get("/api/transactions").json()}
    assert fixed[res["id"]]["exchange_rate"] == 950.0 and fixed[res["id"]]["base_amount"] == 9500.0
    assert fixed[res["id"]]["rate_estimated"] is False
    assert fixed[typed["id"]]["exchange_rate"] == 999  # a typed rate is never replaced


def test_a_dropped_connection_is_retried(db, monkeypatch):
    calls = []

    def flaky(client, indicator, year=None):
        calls.append(indicator)
        if calls.count(indicator) == 1:
            raise RuntimeError("Server disconnected")
        return fake_series(client, indicator, year)

    monkeypatch.setattr(exchange_rates, "_fetch_series", flaky)
    assert sync_exchange_rates(db)["success"]


def test_failed_run_schedules_a_retry(admin, monkeypatch):
    from app.schedulers import tasks

    def boom(*args, **kwargs):
        raise RuntimeError("no network")
    monkeypatch.setattr(exchange_rates, "_fetch_series", boom)
    tasks._rates_job()
    assert tasks.scheduler.get_job(tasks.RATES_RETRY_JOB) is not None
    tasks.scheduler.remove_job(tasks.RATES_RETRY_JOB)


def test_csv_with_old_foreign_rows_downloads_their_year_right_away(client, db, monkeypatch):
    fetched = []

    def fake(client, indicator, year=None):
        fetched.append(year)
        return [{"date": f"{year}-03-10", "value": 800.0}]
    monkeypatch.setattr(exchange_rates, "_fetch_series", fake)

    csv = ("Date,Account,Category,Tags,Expense amount,Income amount,Currency,Description\n"
           "10-03-22,Tarjeta de Crédito USD,Other,,12,0,USD,Libro\n")
    res = client.post("/api/system/import-csv", json={"csv_content": csv}).json()
    assert res["estimated_rates"] == 1 and "provisional" in res["message"]
    # The import started a background download of 2022, which corrected the provisional rate
    assert 2022 in fetched
    db.expire_all()
    tx = db.query(Transaction).filter(Transaction.merchant == "Libro").one()
    assert (tx.exchange_rate, tx.rate_estimated) == (800.0, False)
