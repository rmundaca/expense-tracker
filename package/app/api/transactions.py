import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.i18n import t
from app.models.dtos import TransactionCreate, TransactionOut, TransactionUpdate, to_dict
from app.models.schemas import Account, Category, IgnoredEmail, Tag, Transaction
from app.services.classifier import classifier_service
from app.services.duplicates import find_possible_duplicates
from app.services.exchange_rates import SUPPORTED_CURRENCIES, normalize_currency, resolve_rate

router = APIRouter(prefix="/api/transactions", tags=["transactions"])
logger = logging.getLogger("api.transactions")

USER_TYPES = ("expense", "income", "transfer")


def _end_of_day(date_str: str) -> str:
    return date_str if len(date_str) > 10 else f"{date_str} 23:59:59"


def apply_period(q, month: Optional[str], start_date: Optional[str], end_date: Optional[str]):
    """Filters a Transaction query by an explicit date range, or by month (YYYY-MM)."""
    if start_date:
        q = q.filter(Transaction.date >= start_date)
    if end_date:
        q = q.filter(Transaction.date <= _end_of_day(end_date))
    if month and not (start_date or end_date):
        q = q.filter(Transaction.date.startswith(month))
    return q


def _set_tags(db: Session, tx: Transaction, names: List[str]):
    tx.tags.clear()
    for raw in names:
        name = raw.strip().lower()[:60]
        if not name:
            continue
        tag = db.query(Tag).filter(Tag.name == name).first()
        if not tag:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()
        if tag not in tx.tags:
            tx.tags.append(tag)


def validate_movement(db: Session, tx, check_category: bool = True):
    """Enforces a consistent movement (a Transaction or a RecurringRule) before saving: type, accounts and category."""
    if tx.type not in USER_TYPES and tx.type != "adjustment":
        raise HTTPException(status_code=400, detail=t("common.invalid_tx_type"))
    if tx.type != "adjustment" and (tx.amount is None or tx.amount <= 0):
        raise HTTPException(status_code=400, detail=t("common.amount_positive"))
    if not db.query(Account.id).filter(Account.id == tx.account_id).first():
        raise HTTPException(status_code=400, detail=t("transactions.invalid_account"))
    if tx.type == "transfer":
        if not tx.destination_account_id:
            raise HTTPException(status_code=400, detail=t("transactions.destination_required"))
        if tx.destination_account_id == tx.account_id:
            raise HTTPException(status_code=400, detail=t("transactions.same_account"))
        if not db.query(Account.id).filter(Account.id == tx.destination_account_id).first():
            raise HTTPException(status_code=400, detail=t("transactions.invalid_destination"))
        tx.category_id = None
    else:
        tx.destination_account_id = None
        if check_category and tx.category_id is not None:
            cat = db.query(Category).filter(Category.id == tx.category_id).first()
            if not cat:
                raise HTTPException(status_code=400, detail=t("transactions.invalid_category"))
            if tx.type in ("expense", "income") and cat.type != tx.type:
                raise HTTPException(status_code=400, detail=t("transactions.category_mismatch"))


def _refresh_amounts(db: Session, tx: Transaction, explicit_rate: Optional[float], rate_inputs_changed: bool):
    """Keeps exchange_rate/base_amount coherent with currency, date and amount."""
    tx.currency = normalize_currency(tx.currency)
    if tx.currency not in SUPPORTED_CURRENCIES:
        raise HTTPException(status_code=400, detail=t("common.unsupported_currency"))
    if tx.currency == "CLP":
        tx.exchange_rate, tx.rate_estimated = 1.0, False
    elif explicit_rate and explicit_rate > 0:
        tx.exchange_rate, tx.rate_estimated = explicit_rate, False  # typed by the user: never replaced
    elif rate_inputs_changed or not tx.exchange_rate or tx.exchange_rate <= 0:
        tx.exchange_rate, tx.rate_estimated = resolve_rate(db, tx.currency, tx.date)
    tx.base_currency = "CLP"
    tx.base_amount = round(tx.amount * tx.exchange_rate, 2)


def _learn(db: Session, tx: Transaction):
    if tx.status == "confirmed" and tx.type in USER_TYPES:
        classifier_service.learn(
            db, tx.merchant, tx.description, category_id=tx.category_id, account_id=tx.account_id,
            tx_type=tx.type, destination_account_id=tx.destination_account_id,
        )


def _get_or_404(db: Session, tx_id: int) -> Transaction:
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail=t("transactions.not_found"))
    return tx


@router.get("", response_model=List[TransactionOut])
def list_transactions(
    status: Optional[str] = None,
    account_id: Optional[int] = None,
    category_id: Optional[int] = None,
    type: Optional[str] = None,
    month: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = apply_period(db.query(Transaction), month, start_date, end_date)
    if status:
        q = q.filter(Transaction.status == status)
    if account_id:
        q = q.filter(or_(Transaction.account_id == account_id, Transaction.destination_account_id == account_id))
    if category_id:
        q = q.filter(Transaction.category_id == category_id)
    if type:
        q = q.filter(Transaction.type == type)
    if search and search.strip():
        s = f"%{search.strip()}%"
        q = q.filter(or_(Transaction.merchant.ilike(s), Transaction.description.ilike(s)))
    items = q.order_by(desc(Transaction.date), desc(Transaction.id)).offset(offset).limit(limit).all()
    duplicates = find_possible_duplicates(db, items)
    for tx in items:
        tx.duplicate_of = duplicates.get(tx.id)
    return items


@router.get("/pending-count")
def pending_count(db: Session = Depends(get_db)):
    """Movements waiting for review (the badge on the Review tab)."""
    return {"count": db.query(Transaction.id).filter(Transaction.status == "pending_review").count()}


@router.get("/suggest")
def suggest(merchant: str = Query(..., min_length=1), description: Optional[str] = None, db: Session = Depends(get_db)):
    """Real-time suggestion while the user types a merchant/description."""
    res = classifier_service.classify(db, merchant=merchant, description=description or "")
    return {
        "category_id": res.category_id,
        "account_id": res.account_id,
        "destination_account_id": res.destination_account_id,
        "type": res.tx_type,
        "source": res.source,
        "confidence": res.confidence,
    }


@router.post("", response_model=TransactionOut)
def create_transaction(data: TransactionCreate, db: Session = Depends(get_db)):
    tx = Transaction(**to_dict(data, exclude={"tags", "exchange_rate"}))
    tx.status = "confirmed"
    tx.source = "manual"
    validate_movement(db, tx)
    _refresh_amounts(db, tx, data.exchange_rate, rate_inputs_changed=True)
    db.add(tx)
    db.flush()
    _set_tags(db, tx, data.tags)
    _learn(db, tx)
    db.commit()
    db.refresh(tx)
    return tx


@router.put("/{tx_id}", response_model=TransactionOut)
def update_transaction(tx_id: int, data: TransactionUpdate, db: Session = Depends(get_db)):
    tx = _get_or_404(db, tx_id)
    if tx.type == "adjustment":
        raise HTTPException(status_code=400, detail=t("transactions.adjustment_locked"))
    changes = to_dict(data, exclude_unset=True, exclude={"tags", "exchange_rate"})
    if changes.get("type") == "adjustment" or changes.get("status") not in (None, "confirmed", "pending_review"):
        raise HTTPException(status_code=400, detail=t("transactions.change_not_allowed"))

    rate_inputs_changed = any(
        k in changes and changes[k] != getattr(tx, k) for k in ("currency", "date")
    )
    user_edit = any(k in changes for k in ("type", "category_id", "account_id", "destination_account_id", "merchant"))
    was_pending = tx.status == "pending_review"
    for key, value in changes.items():
        setattr(tx, key, value)

    validate_movement(db, tx, check_category="category_id" in changes or "type" in changes)
    _refresh_amounts(db, tx, data.exchange_rate, rate_inputs_changed)
    if data.tags is not None:
        _set_tags(db, tx, data.tags)
    if tx.status == "confirmed" and (was_pending or user_edit):
        _learn(db, tx)
    db.commit()
    db.refresh(tx)
    return tx


@router.post("/{tx_id}/confirm", response_model=TransactionOut)
def confirm_transaction(tx_id: int, db: Session = Depends(get_db)):
    """Approves a pending movement as suggested."""
    tx = _get_or_404(db, tx_id)
    if tx.status != "confirmed":
        validate_movement(db, tx, check_category=False)
        tx.status = "confirmed"
        _learn(db, tx)
        db.commit()
        db.refresh(tx)
    return tx


@router.post("/confirm-all")
def confirm_all_pending(db: Session = Depends(get_db)):
    """Approves every pending movement that is complete (has a category, or a destination for transfers).
    Possible duplicates wait for the user to approve or discard them one by one."""
    confirmed = skipped = 0
    pending = db.query(Transaction).filter(Transaction.status == "pending_review").all()
    duplicates = find_possible_duplicates(db, pending)
    for tx in pending:
        if tx.id in duplicates:
            continue
        complete = tx.destination_account_id if tx.type == "transfer" else tx.category_id
        if not complete:
            skipped += 1
            continue
        tx.status = "confirmed"
        _learn(db, tx)
        confirmed += 1
    db.commit()
    return {"confirmed": confirmed, "skipped": skipped, "duplicates": len(duplicates)}


@router.delete("/{tx_id}")
def delete_transaction(tx_id: int, db: Session = Depends(get_db)):
    """Deletes (or discards, if pending) a movement. Imported emails are remembered so they never come back."""
    tx = _get_or_404(db, tx_id)
    if tx.email_message_id and not db.query(IgnoredEmail.id).filter(IgnoredEmail.email_message_id == tx.email_message_id).first():
        db.add(IgnoredEmail(
            email_message_id=tx.email_message_id,
            subject=(tx.merchant or tx.description or "")[:250],
            sender="email",
            reason="user_discarded" if tx.status == "pending_review" else "user_deleted",
        ))
    tx.tags.clear()
    db.delete(tx)
    db.commit()
    return {"deleted": tx_id}
