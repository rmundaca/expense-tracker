"""
Account balances are derived, never stored: opening_balance + effect of every confirmed transaction,
converted into the account's currency with the rate of the transaction's own date.
"""
from typing import Dict, List

from sqlalchemy.orm import Session

from app.models.schemas import Account, Transaction
from app.services.exchange_rates import RateCache, normalize_currency


def amount_in_currency(tx, target_currency: str, rates: RateCache) -> float:
    """Expresses a transaction's amount in `target_currency`, using the rate stored on the transaction."""
    src = normalize_currency(tx.currency)
    tgt = normalize_currency(target_currency)
    amount = tx.amount or 0.0
    if src == tgt:
        return amount
    base_clp = tx.base_amount if tx.base_amount is not None else amount * (tx.exchange_rate or 1.0)
    if tgt == "CLP":
        return base_clp
    return base_clp / rates.get(tgt, tx.date)


def compute_balances(db: Session) -> Dict[int, float]:
    """Current balance of every account (active or archived), in each account's own currency."""
    return balances_at(db, ["9999-12-31"])[0]


def balances_at(db: Session, cutoffs: List[str]) -> List[Dict[int, float]]:
    """Balances (as compute_balances) at the end of each day in `cutoffs` (ascending), in one pass over the movements."""
    accounts = {a.id: a for a in db.query(Account).all()}
    balances = {acc_id: float(a.opening_balance or 0.0) for acc_id, a in accounts.items()}
    rates = RateCache(db)
    snapshots = []

    def snapshot():
        snapshots.append({acc_id: round(value, 2) for acc_id, value in balances.items()})

    rows = db.query(
        Transaction.account_id, Transaction.destination_account_id, Transaction.type,
        Transaction.amount, Transaction.currency, Transaction.base_amount,
        Transaction.exchange_rate, Transaction.date,
    ).filter(Transaction.status == "confirmed").order_by(Transaction.date)

    for tx in rows:
        while len(snapshots) < len(cutoffs) and tx.date[:10] > cutoffs[len(snapshots)]:
            snapshot()
        source = accounts.get(tx.account_id)
        if source:
            value = amount_in_currency(tx, source.currency, rates)
            if tx.type in ("expense", "transfer"):
                balances[source.id] -= value
            elif tx.type in ("income", "adjustment"):
                balances[source.id] += value
        if tx.type == "transfer" and tx.destination_account_id in accounts:
            dest = accounts[tx.destination_account_id]
            balances[dest.id] += amount_in_currency(tx, dest.currency, rates)

    while len(snapshots) < len(cutoffs):
        snapshot()
    return snapshots
