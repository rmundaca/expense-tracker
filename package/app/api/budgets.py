import json
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.i18n import t
from app.models.dtos import BudgetIn, TransactionOut, to_dict
from app.models.schemas import Budget, Category
from app.services import budgets as service
from app.services.recurrence import expected_monthly_income

router = APIRouter(prefix="/api/budgets", tags=["budgets"])

FIELDS = ("id", "name", "scope", "amount_type", "amount", "period", "period_count", "start_date", "end_date")


def budget_out(db: Session, budget: Budget, monthly_income: float) -> dict:
    return {**{f: getattr(budget, f) for f in FIELDS}, "category_ids": budget.category_list,
            "status": service.status(db, budget, date.today(), monthly_income)}


def _get_or_404(db: Session, budget_id: int) -> Budget:
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(status_code=404, detail=t("budgets.not_found"))
    return budget


def _apply(db: Session, budget: Budget, data: BudgetIn) -> dict:
    values = to_dict(data)
    values["name"] = values["name"].strip()[:100]
    ids = sorted(set(values.pop("category_ids"))) if values["scope"] != "all" else []
    if not values["name"]:
        raise HTTPException(status_code=400, detail=t("common.name_required"))
    if values["scope"] not in service.SCOPES or values["amount_type"] not in ("fixed", "income_pct"):
        raise HTTPException(status_code=400, detail=t("budgets.invalid"))
    if values["period"] not in service.PERIODS or values["period_count"] < 1:
        raise HTTPException(status_code=400, detail=t("budgets.invalid_period"))
    if values["amount"] <= 0:
        raise HTTPException(status_code=400, detail=t("common.amount_positive"))
    if values["scope"] != "all":
        found = db.query(Category.id).filter(Category.id.in_(ids), Category.type == "expense").count()
        if not ids or found != len(ids):
            raise HTTPException(status_code=400, detail=t("budgets.pick_category"))
    if values["period"] == "once":
        if not values["end_date"] or values["end_date"] < values["start_date"]:
            raise HTTPException(status_code=400, detail=t("budgets.end_after_start"))
    else:
        values["end_date"] = None
    try:
        date.fromisoformat(values["start_date"])
        if values["end_date"]:
            date.fromisoformat(values["end_date"])
    except ValueError:
        raise HTTPException(status_code=400, detail=t("common.invalid_date"))
    for key, value in values.items():
        setattr(budget, key, value)
    budget.category_ids = json.dumps(ids)
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget_out(db, budget, expected_monthly_income(db))


@router.get("")
def list_budgets(db: Session = Depends(get_db)):
    income = expected_monthly_income(db)
    budgets = [budget_out(db, b, income) for b in db.query(Budget).order_by(Budget.name).all()]
    return {"expected_income": income, "budgets": budgets}


@router.get("/{budget_id}/history")
def budget_history(budget_id: int, count: int = Query(6, ge=1, le=24), db: Session = Depends(get_db)):
    return service.history(db, _get_or_404(db, budget_id), count, expected_monthly_income(db))


@router.get("/{budget_id}/period")
def budget_period(budget_id: int, day: Optional[str] = None, db: Session = Depends(get_db)):
    """Status and counted movements of the period containing `day` (today by default)."""
    budget = _get_or_404(db, budget_id)
    try:
        when = date.fromisoformat(day) if day else date.today()
    except ValueError:
        raise HTTPException(status_code=400, detail=t("common.invalid_date"))
    return {**service.status(db, budget, when, expected_monthly_income(db)),
            "transactions": [TransactionOut.from_orm(tx) for tx in service.movements(db, budget, when)]}


@router.post("")
def create_budget(data: BudgetIn, db: Session = Depends(get_db)):
    return _apply(db, Budget(), data)


@router.put("/{budget_id}")
def update_budget(budget_id: int, data: BudgetIn, db: Session = Depends(get_db)):
    return _apply(db, _get_or_404(db, budget_id), data)


@router.delete("/{budget_id}")
def delete_budget(budget_id: int, db: Session = Depends(get_db)):
    db.delete(_get_or_404(db, budget_id))
    db.commit()
    return {"deleted": budget_id}
