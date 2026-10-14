"""
Recurring movements: each occurrence of a RecurringRule becomes an ordinary Transaction on its date
(materialize_due, run daily by the scheduler). Occurrences not created yet are what Planning projects.

Also the calendar arithmetic shared with budgets and planning.
"""
from calendar import monthrange
from datetime import date, timedelta
from typing import Iterator, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.schemas import RecurringRule, Transaction
from app.services.exchange_rates import RateCache, resolve_rate

UNITS = ("day", "week", "month", "year")
MONTH_DAYS = 365.25 / 12
PER_MONTH = {"day": MONTH_DAYS, "week": MONTH_DAYS / 7, "month": 1.0, "year": 1 / 12}


def add_months(day: date, months: int) -> date:
    """Same day `months` later, clamped to the month's last day (Jan 31 + 1 month = Feb 28)."""
    years, month0 = divmod(day.month - 1 + months, 12)
    year, month = day.year + years, month0 + 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))


def shift(day: date, unit: str, n: int) -> date:
    if unit == "day":
        return day + timedelta(days=n)
    if unit == "week":
        return day + timedelta(weeks=n)
    return add_months(day, n * (12 if unit == "year" else 1))


def month_end(ym: str) -> str:
    """Last day (YYYY-MM-DD) of the month YYYY-MM."""
    first = date.fromisoformat(f"{ym}-01")
    return (add_months(first, 1) - timedelta(days=1)).isoformat()


def occurrences(rule: RecurringRule, after: Optional[str], until: str) -> Iterator[date]:
    """
    Dates of `rule` in (after, until]. The n-th one is always counted from start_date, so a rule on the
    31st falls on the last day of shorter months without drifting to the 28th afterwards.
    """
    start = date.fromisoformat(rule.start_date)
    last = date.fromisoformat(min(until, rule.end_date or until))
    floor = date.fromisoformat(after) if after else None
    n = 0
    while (day := shift(start, rule.frequency, n)) <= last:
        if floor is None or day > floor:
            yield day
        n += 1


def next_occurrence(rule: RecurringRule) -> Optional[str]:
    """First occurrence not created yet, or None once the rule has ended."""
    day = next(occurrences(rule, rule.last_date, rule.end_date or "9999-12-31"), None)
    return day.isoformat() if day else None


def _movement(db: Session, rule: RecurringRule, day: str) -> Transaction:
    rate, estimated = resolve_rate(db, rule.currency, day)
    return Transaction(
        type=rule.type, amount=rule.amount, currency=rule.currency,
        exchange_rate=rate, rate_estimated=estimated, base_amount=round(rule.amount * rate, 2), base_currency="CLP",
        date=day, account_id=rule.account_id, destination_account_id=rule.destination_account_id,
        category_id=rule.category_id, merchant=rule.merchant, description=rule.description,
        source="recurring", recurring_id=rule.id, status="confirmed" if rule.auto_confirm else "pending_review",
    )


def materialize_due(db: Session, today: Optional[date] = None) -> int:
    """Creates every occurrence up to today that does not exist yet (also the ones missed while the NAS was off)."""
    today_iso = (today or date.today()).isoformat()
    created = 0
    for rule in db.query(RecurringRule).all():
        for day in occurrences(rule, rule.last_date, today_iso):
            db.add(_movement(db, rule, day.isoformat()))
            rule.last_date = day.isoformat()
            created += 1
    db.commit()
    return created


def expected_monthly_income(db: Session) -> float:
    """
    Income expected per month in CLP: the monthly equivalent of the recurring incomes still running,
    or, without any, the average confirmed income of the last three complete months.
    """
    today = date.today().isoformat()
    rates = RateCache(db)
    expected = sum(
        rule.amount * rates.get(rule.currency) * PER_MONTH[rule.frequency]
        for rule in db.query(RecurringRule).filter(RecurringRule.type == "income")
        if not rule.end_date or rule.end_date >= today
    )
    if expected:
        return round(expected, 2)
    this_month = date.today().replace(day=1)
    total = db.query(func.sum(Transaction.base_amount)).filter(
        Transaction.status == "confirmed", Transaction.type == "income",
        Transaction.date >= add_months(this_month, -3).isoformat(), Transaction.date < this_month.isoformat(),
    ).scalar()
    return round((total or 0.0) / 3, 2)
