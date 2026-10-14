from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.i18n import t
from app.models.dtos import CategoryCreate, CategoryOut, CategoryUpdate, to_dict
from app.models.schemas import Category, MLTrainingSample, RecurringRule, RuleMapping, Transaction
from app.services.classifier import classifier_service

router = APIRouter(prefix="/api/categories", tags=["categories"])

CATEGORY_TYPES = ("expense", "income")


def _get_or_404(db: Session, category_id: int) -> Category:
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail=t("categories.not_found"))
    return cat


@router.get("", response_model=List[CategoryOut])
def list_categories(include_archived: bool = False, db: Session = Depends(get_db)):
    """Archived categories are only needed to label the movements that still use them."""
    q = db.query(Category)
    if not include_archived:
        q = q.filter(Category.is_active == True)
    return q.order_by(Category.type, Category.name).all()


@router.post("", response_model=CategoryOut)
def create_category(data: CategoryCreate, db: Session = Depends(get_db)):
    if data.type not in CATEGORY_TYPES or not data.name.strip():
        raise HTTPException(status_code=400, detail=t("categories.required"))
    cat = Category(**to_dict(data))
    cat.name = cat.name.strip()
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.put("/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, data: CategoryUpdate, db: Session = Depends(get_db)):
    cat = _get_or_404(db, category_id)
    changes = to_dict(data, exclude_unset=True)
    if changes.get("type") and changes["type"] not in CATEGORY_TYPES:
        raise HTTPException(status_code=400, detail=t("categories.invalid_type"))
    type_change = changes.get("type") and changes["type"] != cat.type
    if type_change and db.query(Transaction.id).filter(Transaction.category_id == category_id).first():
        raise HTTPException(status_code=400, detail=t("categories.type_locked"))
    for key, value in changes.items():
        setattr(cat, key, value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    """Deletes an unused category; one with movements (or recurring ones) is archived so history keeps its label."""
    cat = _get_or_404(db, category_id)
    if (db.query(Transaction.id).filter(Transaction.category_id == category_id).first()
            or db.query(RecurringRule.id).filter(RecurringRule.category_id == category_id).first()):
        cat.is_active = False
        db.commit()
        classifier_service.invalidate(db)
        return {"archived": True, "message": t("common.archived_with_history", name=cat.name)}
    db.query(RuleMapping).filter(RuleMapping.category_id == category_id).delete(synchronize_session=False)
    db.query(MLTrainingSample).filter(MLTrainingSample.category_id == category_id).delete(synchronize_session=False)
    db.delete(cat)
    db.commit()
    classifier_service.invalidate(db)
    return {"archived": False, "message": t("common.deleted", name=cat.name)}
