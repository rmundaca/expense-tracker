from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schedulers.tasks import next_rates_run
from app.services.exchange_rates import rates_status, resolve_rate, sync_exchange_rates

router = APIRouter(prefix="/api/exchange-rates", tags=["exchange-rates"])


@router.get("/rate")
def rate(currency: str, date: str = None, db: Session = Depends(get_db)):
    """CLP per unit of `currency` on `date` (used to prefill the rate when entering a foreign movement)."""
    value, estimated = resolve_rate(db, currency, date)
    return {"currency": currency.upper(), "date": date, "rate": value, "estimated": estimated}


@router.get("/status")
def status(db: Session = Depends(get_db)):
    """Current value of each currency, last sync and pending provisional rates (Settings > Exchange rates)."""
    return {**rates_status(db), "next_run": next_rates_run()}


@router.post("/sync")
def sync_now(db: Session = Depends(get_db)):
    """Downloads the rates now for the logged-in user (can take a minute: mindicador is slow at times)."""
    result = sync_exchange_rates(db)
    return {**result, **rates_status(db), "next_run": next_rates_run()}
