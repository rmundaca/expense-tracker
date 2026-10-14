"""Recurring movements, the planning timeline, budgets and the Home layout."""
from datetime import date

from test_api import create


def rule(client, **fields):
    payload = {"type": "income", "amount": 100000, "account_id": fields.pop("account_id"),
               "frequency": "month", "start_date": "2025-01-31", "merchant": "Sueldo"}
    payload.update(fields)
    res = client.post("/api/recurring", json=payload)
    assert res.status_code == 200, res.text
    return res.json()


def budget(client, **fields):
    payload = {"name": "Mes", "amount": 50000, "start_date": "2026-01-01"}
    payload.update(fields)
    return client.post("/api/budgets", json=payload)


# --- Recurrence ----------------------------------------------------------------

def test_month_end_occurrences_do_not_drift():
    from app.models.schemas import RecurringRule
    from app.services.recurrence import occurrences

    r = RecurringRule(frequency="month", start_date="2024-01-31")
    days = [d.isoformat() for d in occurrences(r, None, "2024-05-31")]
    assert days == ["2024-01-31", "2024-02-29", "2024-03-31", "2024-04-30", "2024-05-31"]
    yearly = RecurringRule(frequency="year", start_date="2024-02-29")
    assert [d.isoformat() for d in occurrences(yearly, "2024-02-29", "2028-12-31")] == ["2025-02-28", "2026-02-28", "2027-02-28", "2028-02-29"]


def test_past_occurrences_are_created_once(client, ids, db):
    from app.services.recurrence import materialize_due

    r = rule(client, account_id=ids["checking"], category_id=ids["salary"], end_date="2025-04-30")
    assert r["created"] == 4 and r["next_date"] is None
    txs = client.get("/api/transactions", params={"type": "income"}).json()
    assert sorted(t["date"] for t in txs) == ["2025-01-31", "2025-02-28", "2025-03-31", "2025-04-30"]
    assert all(t["recurring_id"] == r["id"] and t["status"] == "confirmed" for t in txs)
    assert materialize_due(db) == 0


def test_catch_up_and_review(client, ids, db):
    from app.services.recurrence import materialize_due

    r = rule(client, account_id=ids["checking"], type="expense", category_id=ids["groceries"], frequency="week",
             start_date="2099-01-01", auto_confirm=False)
    assert r["created"] == 0 and r["next_date"] == "2099-01-01"
    assert materialize_due(db, today=date(2099, 1, 20)) == 3  # the NAS was off: 1, 8 and 15 January
    assert client.get("/api/transactions/pending-count").json()["count"] == 3


def test_rule_validation_and_delete_keeps_movements(client, ids):
    base = {"type": "transfer", "amount": 10, "account_id": ids["checking"], "frequency": "month", "start_date": "2025-01-01"}
    assert client.post("/api/recurring", json=base).status_code == 400  # no destination
    assert client.post("/api/recurring", json={**base, "destination_account_id": ids["cash"], "frequency": "hour"}).status_code == 400
    assert client.post("/api/recurring", json={**base, "destination_account_id": ids["cash"], "end_date": "2024-01-01"}).status_code == 400

    r = rule(client, account_id=ids["checking"], category_id=ids["salary"], end_date="2025-02-28")
    assert client.delete(f"/api/recurring/{r['id']}").status_code == 200
    txs = client.get("/api/transactions").json()
    assert len(txs) == 2 and all(t["recurring_id"] is None for t in txs)


def test_account_with_recurring_rule_cannot_be_deleted(client, ids):
    rule(client, account_id=ids["cash"], category_id=ids["salary"], start_date="2099-01-01")
    res = client.delete(f"/api/accounts/{ids['cash']}")
    assert res.status_code == 400 and "recurring" in res.json()["detail"]


# --- Timeline -------------------------------------------------------------------

def test_timeline_history_and_plan(client, ids):
    create(client, account_id=ids["checking"], amount=1000, date="2025-01-10", category_id=ids["groceries"])
    create(client, account_id=ids["checking"], type="income", amount=5000, date="2025-03-05", category_id=ids["salary"])
    months = client.get("/api/stats/timeline", params={"start": "2025-01", "months": 3}).json()["months"]
    assert [m["net_worth"] for m in months] == [-1000, -1000, 4000]
    assert months[0]["expense"] == 1000 and months[2]["income"] == 5000

    rule(client, account_id=ids["checking"], category_id=ids["salary"], start_date="2099-01-15", end_date="2099-03-15")
    months = client.get("/api/stats/timeline", params={"start": "2099-01", "months": 4}).json()["months"]
    assert [m["planned_income"] for m in months] == [100000, 100000, 100000, 0]
    assert [m["net_worth"] for m in months] == [104000, 204000, 304000, 304000]


def test_dashboard_reports_net_worth(client, ids):
    create(client, account_id=ids["checking"], type="income", amount=7000, category_id=ids["salary"])
    assert client.get("/api/stats/dashboard").json()["net_worth"] == 7000


# --- Budgets --------------------------------------------------------------------

def test_budget_windows():
    from app.models.schemas import Budget
    from app.services.budgets import window

    every_two_months = Budget(period="month", period_count=2, start_date="2026-01-15")
    assert window(every_two_months, date(2026, 4, 1)) == (date(2026, 3, 15), date(2026, 5, 14))
    weekly = Budget(period="week", period_count=1, start_date="2026-09-07")
    assert window(weekly, date(2026, 9, 29)) == (date(2026, 9, 28), date(2026, 10, 4))
    once = Budget(period="once", period_count=1, start_date="2026-12-01", end_date="2026-12-31")
    assert window(once, date(2026, 9, 29)) == (date(2026, 12, 1), date(2026, 12, 31))


def test_budget_scopes(client, ids, db):
    from app.models.schemas import Budget
    from app.services.budgets import status

    create(client, account_id=ids["checking"], amount=3000, date="2026-03-10", category_id=ids["groceries"])
    create(client, account_id=ids["checking"], amount=2000, date="2026-03-11", category_id=ids["restaurants"])
    create(client, account_id=ids["checking"], amount=900, date="2026-04-01", category_id=ids["groceries"])  # next month
    for scope, expected in (("all", 5000), ("include", 3000), ("exclude", 2000)):
        res = budget(client, name=scope, scope=scope, category_ids=[] if scope == "all" else [ids["groceries"]])
        assert res.status_code == 200, res.text
        b = db.get(Budget, res.json()["id"])
        s = status(db, b, date(2026, 3, 20), 0)
        assert (s["start"], s["end"], s["spent"], s["limit"]) == ("2026-03-01", "2026-03-31", expected, 50000)
        assert s["days_left"] == 0 and s["forecast"] == expected  # a past period: nothing left to project


def test_budget_pace_is_measured_against_today(client, ids, db):
    from app.models.schemas import Budget
    from app.services.budgets import status

    today = date.today()
    create(client, account_id=ids["checking"], amount=3100, date=today.isoformat(), category_id=ids["groceries"])
    b = db.get(Budget, budget(client, period="day", period_count=10, start_date=today.isoformat()).json()["id"])
    s = status(db, b, today, 0)
    assert s["days_left"] == 9 and s["forecast"] == 31000  # 1 of 10 days elapsed


def test_budget_period_lists_the_counted_movements(client, ids):
    create(client, account_id=ids["checking"], amount=3000, date="2026-03-10", category_id=ids["groceries"], merchant="Jumbo")
    create(client, account_id=ids["checking"], amount=7000, date="2026-03-12", category_id=ids["groceries"], merchant="Lider")
    create(client, account_id=ids["checking"], amount=2000, date="2026-03-11", category_id=ids["restaurants"])  # other category
    create(client, account_id=ids["checking"], amount=900, date="2026-04-01", category_id=ids["groceries"])  # next period
    b = budget(client, scope="include", category_ids=[ids["groceries"]], start_date="2026-01-01").json()

    period = client.get(f"/api/budgets/{b['id']}/period", params={"day": "2026-03-01"}).json()
    assert (period["start"], period["end"], period["spent"]) == ("2026-03-01", "2026-03-31", 10000)
    assert [t["merchant"] for t in period["transactions"]] == ["Lider", "Jumbo"]  # biggest first
    assert client.get(f"/api/budgets/{b['id']}/period", params={"day": "marzo"}).status_code == 400


def test_budget_percentage_of_expected_income(client, ids):
    rule(client, account_id=ids["checking"], category_id=ids["salary"], start_date="2099-01-01")  # still running
    res = budget(client, amount_type="income_pct", amount=10, period="year")
    assert res.status_code == 200, res.text
    assert res.json()["status"]["limit"] == 120000  # 10 % of 100.000 a month, for 12 months
    listing = client.get("/api/budgets").json()
    assert listing["expected_income"] == 100000 and len(listing["budgets"]) == 1


def test_budget_validation(client, ids):
    assert budget(client, scope="include", category_ids=[]).status_code == 400
    assert budget(client, scope="include", category_ids=[ids["salary"]]).status_code == 400  # income category
    assert budget(client, period="once").status_code == 400  # needs an end date
    assert budget(client, amount=0).status_code == 400
    assert budget(client, period="month", period_count=0).status_code == 400


def test_budget_history(client, ids):
    b = budget(client, start_date="2026-01-01").json()
    history = client.get(f"/api/budgets/{b['id']}/history", params={"count": 24}).json()
    current_start = date.fromisoformat(b["status"]["start"])
    assert len(history) == (current_start.year - 2026) * 12 + current_start.month - 1
    assert all(p["days_left"] == 0 for p in history)


# --- Home layout ------------------------------------------------------------------

def test_home_layout_round_trip(client):
    assert client.get("/api/stats/dashboard").json()["home_layout"] == []
    layout = [{"id": "accounts", "visible": True}, {"id": "hero", "visible": False}]
    assert client.put("/api/stats/home-layout", json=layout).status_code == 200
    assert client.get("/api/stats/dashboard").json()["home_layout"] == layout
