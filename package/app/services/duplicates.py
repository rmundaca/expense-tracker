"""
Possible duplicates: the same movement recorded twice, typically typed by hand and later imported from the
bank's email (or created by a recurring rule and also imported). Two emails never duplicate each other here:
identical purchases on one day are real, and two notices of one operation share a bank reference instead.
"""
from datetime import date, timedelta
from typing import Dict, List

from sqlalchemy.orm import Session

from app.models.schemas import Transaction

MAX_DAYS_APART = 1


def _day(value: str) -> date:
    return date.fromisoformat(value[:10])


def _is_email(tx) -> bool:
    return tx.source == "email"


def _same_movement(a, b) -> bool:
    return (a.id != b.id and a.type == b.type and a.account_id == b.account_id
            and a.destination_account_id == b.destination_account_id
            and a.currency == b.currency and abs(a.amount - b.amount) < 0.005
            and _is_email(a) != _is_email(b)
            and abs((_day(a.date) - _day(b.date)).days) <= MAX_DAYS_APART)


def find_possible_duplicates(db: Session, txs: List[Transaction]) -> Dict[int, Transaction]:
    """For each movement in `txs` that looks recorded twice, the other movement (the closest in date)."""
    txs = [t for t in txs if t.type != "adjustment"]
    if not txs:
        return {}
    days = [_day(t.date) for t in txs]
    first, last = min(days) - timedelta(days=MAX_DAYS_APART), max(days) + timedelta(days=MAX_DAYS_APART)
    candidates = db.query(Transaction).filter(
        Transaction.type != "adjustment",
        Transaction.amount.in_({t.amount for t in txs}),
        Transaction.date >= first.isoformat(),
        Transaction.date <= f"{last.isoformat()} 23:59:59",
    ).all()
    found = {}
    for tx in txs:
        matches = [c for c in candidates if _same_movement(tx, c)]
        if matches:
            found[tx.id] = min(matches, key=lambda c: abs((_day(c.date) - _day(tx.date)).days))
    return found
