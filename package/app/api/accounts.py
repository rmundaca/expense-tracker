from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.i18n import t
from app.models.dtos import AccountCreate, AccountUpdate
from app.models.schemas import Account, BankProfile, MLTrainingSample, RecurringRule, RuleMapping, Transaction
from app.services.balances import compute_balances
from app.services.exchange_rates import SUPPORTED_CURRENCIES, get_exchange_rate, normalize_currency, resolve_rate

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

# Must match ACCOUNT_TYPES in static/js/app.js
ACCOUNT_TYPES = {"corriente", "vista", "credito", "ahorro", "inversiones", "afp", "efectivo"}
# Older databases and clients use English codes
ACCOUNT_TYPE_ALIASES = {"checking": "corriente", "sight": "vista", "credit": "credito", "savings": "ahorro",
                        "investment": "inversiones", "pension": "afp", "cash": "efectivo"}


def _normalize_type(value: str) -> str:
    code = (value or "").strip().lower()
    code = ACCOUNT_TYPE_ALIASES.get(code, code)
    if code not in ACCOUNT_TYPES:
        raise HTTPException(status_code=400, detail=t("accounts.invalid_type"))
    return code


def _normalize_currency(value: str) -> str:
    code = normalize_currency(value)
    if code not in SUPPORTED_CURRENCIES:
        raise HTTPException(status_code=400, detail=t("common.unsupported_currency"))
    return code


def account_out(acc: Account, balance: Optional[float], db: Session) -> dict:
    """`balance` None leaves both balances out (reference data that does not need them)."""
    return {
        "id": acc.id,
        "name": acc.name,
        "type": acc.type,
        "currency": acc.currency,
        "balance": balance,
        "balance_clp": None if balance is None else round(balance * get_exchange_rate(db, acc.currency), 2),
        "color": acc.color,
        "icon": acc.icon,
        "is_active": bool(acc.is_active),
    }


def _get_or_404(db: Session, account_id: int) -> Account:
    acc = db.query(Account).filter(Account.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail=t("accounts.not_found"))
    return acc


@router.get("")
def list_accounts(include_archived: bool = False, with_balances: bool = True, db: Session = Depends(get_db)):
    """`with_balances=false` skips the balance computation (it walks every movement)."""
    balances = compute_balances(db) if with_balances else None
    q = db.query(Account)
    if not include_archived:
        q = q.filter(Account.is_active == True)
    return [account_out(a, balances.get(a.id, 0.0) if balances is not None else None, db)
            for a in q.order_by(Account.id).all()]


@router.post("")
def create_account(data: AccountCreate, db: Session = Depends(get_db)):
    if not data.name.strip():
        raise HTTPException(status_code=400, detail=t("accounts.name_required"))
    acc = Account(
        name=data.name.strip(), type=_normalize_type(data.type), currency=_normalize_currency(data.currency),
        opening_balance=round(data.balance or 0.0, 2), color=data.color, icon=data.icon, is_active=True,
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return account_out(acc, acc.opening_balance, db)


@router.put("/{account_id}")
def update_account(account_id: int, data: AccountUpdate, db: Session = Depends(get_db)):
    acc = _get_or_404(db, account_id)
    if data.type is not None:
        data.type = _normalize_type(data.type)
    for field in ("name", "type", "color", "icon", "is_active"):
        value = getattr(data, field)
        if value is not None:
            setattr(acc, field, value.strip() if isinstance(value, str) else value)

    balance = compute_balances(db).get(acc.id, 0.0)
    if data.balance is not None:
        delta = round(data.balance - balance, 2)
        if abs(delta) >= 0.01:
            balance = round(balance + delta, 2)
            rate, estimated = resolve_rate(db, acc.currency)
            db.add(Transaction(
                account_id=acc.id, type="adjustment", amount=delta, currency=acc.currency,
                exchange_rate=rate, rate_estimated=estimated, base_amount=round(delta * rate, 2), base_currency="CLP",
                date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), merchant=t("accounts.adjustment"),
                description=(data.adjustment_note or "").strip() or None, source="manual", status="confirmed",
            ))
    db.commit()
    return account_out(acc, balance, db)


@router.delete("/{account_id}")
def delete_account(account_id: int, db: Session = Depends(get_db)):
    """Deletes an empty account; one with history is archived instead. Must have a zero balance."""
    acc = _get_or_404(db, account_id)
    if db.query(RecurringRule.id).filter(
        (RecurringRule.account_id == account_id) | (RecurringRule.destination_account_id == account_id)
    ).first():
        raise HTTPException(status_code=400, detail=t("accounts.has_recurring"))
    if abs(compute_balances(db).get(acc.id, 0.0)) >= 0.01:
        raise HTTPException(status_code=400, detail=t("accounts.has_balance"))
    has_history = db.query(Transaction.id).filter(
        (Transaction.account_id == account_id) | (Transaction.destination_account_id == account_id)
    ).first()
    if has_history:
        acc.is_active = False
        db.commit()
        return {"archived": True, "message": t("common.archived_with_history", name=acc.name)}
    # Drop references so the foreign keys allow the delete
    for model, column in ((BankProfile, BankProfile.default_account_id), (RuleMapping, RuleMapping.account_id),
                          (RuleMapping, RuleMapping.destination_account_id), (MLTrainingSample, MLTrainingSample.account_id),
                          (MLTrainingSample, MLTrainingSample.destination_account_id)):
        db.query(model).filter(column == account_id).update({column: None}, synchronize_session=False)
    db.delete(acc)
    db.commit()
    return {"archived": False, "message": t("common.deleted", name=acc.name)}
