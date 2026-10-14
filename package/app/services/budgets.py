"""
Budgets: the period a day falls in, the limit for that period and how much of it was spent.
Spending is confirmed expenses in CLP; a percentage limit applies to the expected monthly income
(services/recurrence.expected_monthly_income), prorated to the period's length.
"""
from datetime import date, timedelta
from typing import Dict, List, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.schemas import Budget, Transaction
from app.services.recurrence import MONTH_DAYS, shift

PERIODS = ("day", "week", "month", "year", "once")
SCOPES = ("all", "include", "exclude")


def window(budget: Budget, day: date) -> Tuple[date, date]:
    """Period of `budget` that contains `day` (the first one if `day` is earlier; the only one for "once")."""
    start = date.fromisoformat(budget.start_date)
    if budget.period == "once":
        return start, date.fromisoformat(budget.end_date)
    step = max(budget.period_count, 1)
    k = 0
    while shift(start, budget.period, (k + 1) * step) <= day:
        k += 1
    return shift(start, budget.period, k * step), shift(start, budget.period, (k + 1) * step) - timedelta(days=1)


def _limit(budget: Budget, first: date, last: date, monthly_income: float) -> float:
    if budget.amount_type == "fixed":
        return budget.amount
    if budget.period in ("month", "year"):
        months = max(budget.period_count, 1) * (12 if budget.period == "year" else 1)
    else:
        months = ((last - first).days + 1) / MONTH_DAYS
    return round(budget.amount / 100 * monthly_income * months, 2)


def _expenses(db: Session, budget: Budget, first: date, last: date):
    """Query of the movements a budget counts between two days: confirmed expenses within its scope."""
    q = db.query(Transaction).filter(
        Transaction.status == "confirmed", Transaction.type == "expense",
        Transaction.date >= first.isoformat(), Transaction.date <= f"{last.isoformat()} 23:59:59",
    )
    ids = budget.category_list
    if budget.scope == "include":
        q = q.filter(Transaction.category_id.in_(ids))
    elif budget.scope == "exclude":
        q = q.filter(or_(Transaction.category_id.is_(None), Transaction.category_id.notin_(ids)))
    return q


def _spent(db: Session, budget: Budget, first: date, last: date) -> float:
    return round(_expenses(db, budget, first, last).with_entities(func.sum(Transaction.base_amount)).scalar() or 0.0, 2)


def movements(db: Session, budget: Budget, day: date) -> List[Transaction]:
    """Movements counted in the period containing `day`, biggest first (so an odd one stands out)."""
    first, last = window(budget, day)
    return _expenses(db, budget, first, last).order_by(Transaction.base_amount.desc(), Transaction.date.desc()).all()


def status(db: Session, budget: Budget, day: date, monthly_income: float) -> Dict:
    """
    Limit, spending and end-of-period forecast (at the pace so far) for the period containing `day`.
    Days left and pace are measured against today: a past period has none left, a future one hasn't started.
    """
    first, last = window(budget, day)
    spent = _spent(db, budget, first, last)
    total_days = (last - first).days + 1
    elapsed = min(max((date.today() - first).days + 1, 0), total_days)
    return {
        "start": first.isoformat(),
        "end": last.isoformat(),
        "limit": _limit(budget, first, last, monthly_income),
        "spent": spent,
        "days_left": total_days - elapsed,
        "forecast": round(spent / elapsed * total_days, 2) if elapsed else spent,
    }


def history(db: Session, budget: Budget, count: int, monthly_income: float) -> List[Dict]:
    """The `count` periods before the current one, newest first."""
    if budget.period == "once":
        return []
    start = date.fromisoformat(budget.start_date)
    periods = []
    first, _ = window(budget, date.today())
    while len(periods) < count and first > start:
        periods.append(status(db, budget, first - timedelta(days=1), monthly_income))
        first = date.fromisoformat(periods[-1]["start"])
    return periods
