import json
from collections import defaultdict
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.accounts import account_out
from app.api.transactions import apply_period
from app.core.database import get_db
from app.i18n import t
from app.models.dtos import HomeCard, to_dict
from app.models.schemas import Account, Category, RecurringRule, Transaction, get_setting, set_setting
from app.services.balances import balances_at, compute_balances
from app.services.exchange_rates import RateCache
from app.services.recurrence import add_months, month_end, occurrences

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/dashboard")
def dashboard(month: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None,
              db: Session = Depends(get_db)):
    """Totals for the period (in CLP), spending by category, current balances and the Home layout."""
    if not (month or start_date or end_date):
        month = datetime.now().strftime("%Y-%m")

    balances = compute_balances(db)
    accounts = [account_out(a, balances.get(a.id, 0.0), db)
                for a in db.query(Account).filter(Account.is_active == True).order_by(Account.id).all()]

    # Only confirmed income/expense count: transfers move money and adjustments correct balances
    q = db.query(Transaction.type, Transaction.category_id, func.sum(Transaction.base_amount)).filter(
        Transaction.status == "confirmed", Transaction.type.in_(("income", "expense"))
    )
    rows = apply_period(q, month, start_date, end_date).group_by(Transaction.type, Transaction.category_id).all()

    categories = {c.id: c for c in db.query(Category).all()}
    totals = {"income": 0.0, "expense": 0.0}
    breakdown = {"income": [], "expense": []}
    for tx_type, category_id, total in rows:
        total = float(total or 0.0)
        totals[tx_type] += total
        cat = categories.get(category_id)
        breakdown[tx_type].append({
            "category_id": category_id,
            "name": cat.name if cat else t("common.uncategorized"),
            "color": cat.color if cat else "#78909c",
            "icon": cat.icon if cat else "tag",
            "total": round(total, 2),
        })
    for tx_type, items in breakdown.items():
        items.sort(key=lambda i: i["total"], reverse=True)
        for item in items:
            item["percentage"] = round(item["total"] / totals[tx_type] * 100, 1) if totals[tx_type] else 0

    return {
        "month": month,
        "net_worth": round(sum(a["balance_clp"] for a in accounts), 2),
        "total_income": round(totals["income"], 2),
        "total_expense": round(totals["expense"], 2),
        "net": round(totals["income"] - totals["expense"], 2),
        "pending_count": db.query(Transaction).filter(Transaction.status == "pending_review").count(),
        "expense_breakdown": breakdown["expense"],
        "income_breakdown": breakdown["income"],
        "accounts": accounts,
        "home_layout": json.loads(get_setting(db, "home_layout", "[]")),
    }


@router.put("/home-layout")
def save_home_layout(cards: List[HomeCard], db: Session = Depends(get_db)):
    """Order and visibility of the Home cards (the app owns the card ids)."""
    set_setting(db, "home_layout", json.dumps([to_dict(c) for c in cards]))
    db.commit()
    return cards


@router.get("/timeline")
def timeline(start: str, months: int = Query(12, ge=1, le=36), db: Session = Depends(get_db)):
    """
    Month by month (in CLP): confirmed income and expense, the part still planned by recurring movements
    (occurrences not created yet) and the net worth at the month's end, planned movements included.
    """
    try:
        first = date.fromisoformat(f"{start}-01")
    except ValueError:
        raise HTTPException(status_code=400, detail=t("stats.invalid_month"))
    keys = [add_months(first, i).isoformat()[:7] for i in range(months)]
    ends = [month_end(k) for k in keys]

    actual = defaultdict(float)
    rows = db.query(func.substr(Transaction.date, 1, 7), Transaction.type, func.sum(Transaction.base_amount)).filter(
        Transaction.status == "confirmed", Transaction.type.in_(("income", "expense")),
        Transaction.date >= keys[0], Transaction.date <= f"{ends[-1]} 23:59:59",
    ).group_by(func.substr(Transaction.date, 1, 7), Transaction.type)
    for month, tx_type, total in rows:
        actual[(month, tx_type)] = float(total or 0.0)

    # Planned occurrences before the window also move the net worth inside it
    rates = RateCache(db)
    planned = defaultdict(float)
    for rule in db.query(RecurringRule).filter(RecurringRule.type.in_(("income", "expense"))):
        value = rule.amount * rates.get(rule.currency)
        for day in occurrences(rule, rule.last_date, ends[-1]):
            planned[(day.isoformat()[:7], rule.type)] += value

    accounts = db.query(Account).all()
    result = []
    for key, end, balances in zip(keys, ends, balances_at(db, ends)):
        planned_net = sum(v if t == "income" else -v for (m, t), v in planned.items() if m <= key)
        net_worth = sum(balances.get(a.id, 0.0) * rates.get(a.currency, end) for a in accounts) + planned_net
        result.append({
            "month": key,
            "income": round(actual[(key, "income")], 2),
            "expense": round(actual[(key, "expense")], 2),
            "planned_income": round(planned[(key, "income")], 2),
            "planned_expense": round(planned[(key, "expense")], 2),
            "net_worth": round(net_worth, 2),
        })
    return {"current_month": date.today().isoformat()[:7], "months": result}
