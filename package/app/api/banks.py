import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.i18n import t
from app.models.dtos import BankUpdate, to_dict
from app.models.schemas import BankProfile

router = APIRouter(prefix="/api/banks", tags=["banks"])


def _clean_senders(items: List[str]) -> str:
    cleaned = sorted({s.strip().strip("\"'").lower() for s in items if s and "@" in s})
    return json.dumps(cleaned)


def bank_out(bank: BankProfile) -> dict:
    return {
        "id": bank.id,
        "bank_code": bank.bank_code,
        "bank_name": bank.bank_name,
        "sender_emails": bank.sender_list,
        "default_account_id": bank.default_account_id,
        "is_enabled": bool(bank.is_enabled),
    }


def _get_or_404(db: Session, bank_id: int) -> BankProfile:
    bank = db.query(BankProfile).filter(BankProfile.id == bank_id).first()
    if not bank:
        raise HTTPException(status_code=404, detail=t("banks.not_found"))
    return bank


@router.get("")
def list_banks(db: Session = Depends(get_db)):
    return [bank_out(b) for b in db.query(BankProfile).order_by(BankProfile.bank_name).all()]


@router.put("/{bank_id}")
def update_bank(bank_id: int, data: BankUpdate, db: Session = Depends(get_db)):
    bank = _get_or_404(db, bank_id)
    if data.bank_name is not None and data.bank_name.strip():
        bank.bank_name = data.bank_name.strip()
    if data.sender_emails is not None:
        bank.sender_emails = _clean_senders(data.sender_emails)
    if data.is_enabled is not None:
        bank.is_enabled = data.is_enabled
    if "default_account_id" in to_dict(data, exclude_unset=True):  # null clears it
        bank.default_account_id = data.default_account_id
    db.commit()
    db.refresh(bank)
    return bank_out(bank)
