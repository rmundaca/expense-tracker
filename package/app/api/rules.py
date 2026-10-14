from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.i18n import t
from app.models.dtos import RuleCreate, RuleOut, RuleUpdate, to_dict
from app.models.schemas import RuleMapping

router = APIRouter(prefix="/api/rules", tags=["rules"])


def _get_or_404(db: Session, rule_id: int) -> RuleMapping:
    rule = db.query(RuleMapping).filter(RuleMapping.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail=t("rules.not_found"))
    return rule


def _check(rule: RuleMapping):
    if not (rule.pattern or "").strip():
        raise HTTPException(status_code=400, detail=t("rules.pattern_required"))
    if rule.tx_type == "transfer" and not rule.destination_account_id:
        raise HTTPException(status_code=400, detail=t("rules.transfer_needs_destination"))
    if rule.tx_type != "transfer" and not rule.category_id:
        raise HTTPException(status_code=400, detail=t("rules.pick_category"))


@router.get("", response_model=List[RuleOut])
def list_rules(db: Session = Depends(get_db)):
    return db.query(RuleMapping).order_by(RuleMapping.priority.desc(), RuleMapping.id).all()


@router.post("", response_model=RuleOut)
def create_rule(data: RuleCreate, db: Session = Depends(get_db)):
    rule = RuleMapping(**to_dict(data))
    _check(rule)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.put("/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: int, data: RuleUpdate, db: Session = Depends(get_db)):
    rule = _get_or_404(db, rule_id)
    for key, value in to_dict(data, exclude_unset=True).items():
        setattr(rule, key, value)
    _check(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    db.delete(_get_or_404(db, rule_id))
    db.commit()
    return {"deleted": rule_id}
