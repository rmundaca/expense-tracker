from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.transactions import USER_TYPES, validate_movement
from app.core.database import get_db
from app.i18n import t
from app.models.dtos import RecurringIn, to_dict
from app.models.schemas import RecurringRule, Transaction
from app.services.exchange_rates import SUPPORTED_CURRENCIES, normalize_currency
from app.services.recurrence import UNITS, materialize_due, next_occurrence

router = APIRouter(prefix="/api/recurring", tags=["recurring"])

FIELDS = ("id", "type", "amount", "currency", "account_id", "destination_account_id", "category_id",
          "merchant", "description", "frequency", "start_date", "end_date", "auto_confirm")


def rule_out(rule: RecurringRule) -> dict:
    return {**{f: getattr(rule, f) for f in FIELDS}, "next_date": next_occurrence(rule)}


def _get_or_404(db: Session, rule_id: int) -> RecurringRule:
    rule = db.query(RecurringRule).filter(RecurringRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail=t("recurring.not_found"))
    return rule


def _apply(db: Session, rule: RecurringRule, data: RecurringIn) -> dict:
    """Validates and saves the rule, then creates the occurrences already due (e.g. a start date in the past)."""
    for key, value in to_dict(data).items():
        setattr(rule, key, value)
    rule.currency = normalize_currency(rule.currency)
    if rule.type not in USER_TYPES:
        raise HTTPException(status_code=400, detail=t("common.invalid_tx_type"))
    if rule.currency not in SUPPORTED_CURRENCIES:
        raise HTTPException(status_code=400, detail=t("common.unsupported_currency"))
    if rule.frequency not in UNITS:
        raise HTTPException(status_code=400, detail=t("recurring.invalid_frequency"))
    try:
        date.fromisoformat(rule.start_date)
        if rule.end_date:
            date.fromisoformat(rule.end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail=t("common.invalid_date"))
    if rule.end_date and rule.end_date < rule.start_date:
        raise HTTPException(status_code=400, detail=t("recurring.end_before_start"))
    validate_movement(db, rule)
    db.add(rule)
    db.flush()
    created = materialize_due(db)
    db.refresh(rule)
    return {**rule_out(rule), "created": created}


@router.get("")
def list_rules(db: Session = Depends(get_db)):
    rules = [rule_out(r) for r in db.query(RecurringRule).all()]
    # Running rules by their next date, ended ones last
    return sorted(rules, key=lambda r: (r["next_date"] is None, r["next_date"] or ""))


@router.post("")
def create_rule(data: RecurringIn, db: Session = Depends(get_db)):
    return _apply(db, RecurringRule(), data)


@router.put("/{rule_id}")
def update_rule(rule_id: int, data: RecurringIn, db: Session = Depends(get_db)):
    """Changes apply to the occurrences still to come; the ones already created are ordinary movements."""
    return _apply(db, _get_or_404(db, rule_id), data)


@router.delete("/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    """Stops the repetition. Movements already created are kept."""
    rule = _get_or_404(db, rule_id)
    db.query(Transaction).filter(Transaction.recurring_id == rule_id).update({Transaction.recurring_id: None}, synchronize_session=False)
    db.delete(rule)
    db.commit()
    return {"deleted": rule_id}
