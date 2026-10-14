"""
Exchange rates (CLP per unit) from mindicador.cl, a free public API that republishes the official
Banco Central de Chile values. No credentials required.

A movement keeps the rate it was saved with. When no official value covered its date yet (offline,
the API was down, an old CSV imported before its year was downloaded), the rate is marked provisional
(`Transaction.rate_estimated`) and replaced by the official one after the next successful sync.
"""
import logging
import threading
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

import httpx
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.i18n import t
from app.models.schemas import ExchangeRateHistory, Transaction, get_setting, set_setting

logger = logging.getLogger("exchange_rates")

API_URL = "https://mindicador.cl/api"
# mindicador is slow at times (15-30 s for a yearly series was measured), and sometimes drops the connection
HTTP_TIMEOUT = 60.0
FETCH_ATTEMPTS = 2

# Supported foreign currencies -> mindicador indicator code
CURRENCIES = {"USD": "dolar", "EUR": "euro", "UF": "uf"}
SUPPORTED_CURRENCIES = ("CLP", *CURRENCIES)

# Used only when the database has no rate at all for a currency (fresh install without internet)
FALLBACK_RATES = {"CLP": 1.0, "USD": 950.0, "EUR": 1100.0, "UF": 40000.0}

# An official value older than this (days before the movement) is not trusted as the movement's rate.
# Covers weekends and long holidays, when there is no new value.
MAX_RATE_GAP_DAYS = 5

# One sync at a time (scheduler, "Update now" and post-CSV backfill), so rows are never inserted twice
_sync_lock = threading.Lock()


def normalize_currency(currency: Optional[str]) -> str:
    curr = (currency or "CLP").upper().strip()
    if curr in ("PESO", "PESOS", "$"):
        return "CLP"
    if curr == "CLF":
        return "UF"
    return curr


def _fetch_series(client: httpx.Client, indicator: str, year: Optional[int] = None) -> List[Dict]:
    url = f"{API_URL}/{indicator}" + (f"/{year}" if year else "")
    res = client.get(url)
    res.raise_for_status()
    points = []
    for item in res.json().get("serie", []):
        # "fecha" is Chilean midnight expressed in UTC (e.g. 2026-09-22T03:00:00.000Z) -> date part is correct
        day = str(item.get("fecha", ""))[:10]
        value = item.get("valor")
        if len(day) == 10 and isinstance(value, (int, float)) and value > 0:
            points.append({"date": day, "value": float(value)})
    return points


def _fetch_with_retry(client: httpx.Client, indicator: str, year: int) -> List[Dict]:
    for attempt in range(1, FETCH_ATTEMPTS + 1):
        try:
            return _fetch_series(client, indicator, year)
        except Exception:
            if attempt == FETCH_ATTEMPTS:
                raise
            logger.info(f"Retrying {indicator} {year} after an error")


def _years_to_backfill(db: Session, code: str) -> List[int]:
    """Past years that have transactions but no stored rates (e.g. after importing an old CSV)."""
    first_tx = db.query(func.min(Transaction.date)).scalar()
    if not first_tx:
        return []
    current_year = datetime.now().year
    years = []
    for year in range(int(first_tx[:4]), current_year):
        has_rates = db.query(ExchangeRateHistory.id).filter(
            ExchangeRateHistory.currency_code == code,
            ExchangeRateHistory.date.like(f"{year}-%")
        ).first()
        if not has_rates:
            years.append(year)
    return years


def sync_exchange_rates(db: Session, fetched: Optional[Dict] = None) -> Dict:
    """
    Downloads the current year's rates (plus any missing past years), upserts them and replaces the
    provisional rates of movements that now have an official value.
    `fetched` caches downloads across calls: syncing every user's database hits the API once per series.
    """
    with _sync_lock:
        return _sync(db, {} if fetched is None else fetched)


def _sync(db: Session, fetched: Dict) -> Dict:
    inserted = updated = 0
    errors = []
    current_year = datetime.now().year
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        for code, indicator in CURRENCIES.items():
            for year in [current_year] + _years_to_backfill(db, code):
                key = (indicator, year)
                if key not in fetched:
                    try:
                        fetched[key] = _fetch_with_retry(client, indicator, year)
                    except Exception as e:
                        fetched[key] = e
                points = fetched[key]
                if isinstance(points, Exception):
                    errors.append(f"{code} {year}: {points or type(points).__name__}")
                    continue
                existing = {
                    r.date: r for r in db.query(ExchangeRateHistory).filter(
                        ExchangeRateHistory.currency_code == code,
                        ExchangeRateHistory.date.like(f"{year}-%")
                    )
                }
                for p in points:
                    row = existing.get(p["date"])
                    if row:
                        if abs(row.rate_to_clp - p["value"]) > 1e-9:
                            row.raw_value = row.rate_to_clp = p["value"]
                            updated += 1
                    else:
                        db.add(ExchangeRateHistory(
                            currency_code=code, date=p["date"], series_id=f"mindicador:{indicator}",
                            raw_value=p["value"], rate_to_clp=p["value"]
                        ))
                        inserted += 1
                db.commit()

    fixed = refresh_estimated_rates(db)
    msg = t("rates.result", inserted=inserted, updated=updated)
    if fixed:
        msg += t("rates.fixed", count=fixed)
    if errors:
        msg += t("rates.errors", count=len(errors), details="; ".join(errors)[:300])
        logger.warning(f"Exchange rates: {inserted} new, {updated} updated, {fixed} fixed; errors: {'; '.join(errors)[:300]}")
    else:
        logger.info(f"Exchange rates: {inserted} new, {updated} updated, {fixed} fixed")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_setting(db, "exchange_rate_last_attempt", now_str)
    set_setting(db, "exchange_rate_last_result", msg)
    if not errors:
        set_setting(db, "exchange_rate_last_sync", now_str)
    db.commit()
    return {"success": not errors, "message": msg, "inserted": inserted, "updated": updated, "fixed": fixed}


def resolve_rate(db: Session, currency: str, date_str: Optional[str] = None) -> Tuple[float, bool]:
    """
    (CLP per unit of `currency` on `date_str`, provisional?). The value is the latest one on or before
    that day, since there are none on weekends/holidays; without a date, today's (the UF series already
    holds the coming days' values, which must not be used yet).
    Provisional means no official value covers the day yet: none that recent, none at all (fallback),
    or only an older one while newer values may still be published.
    """
    curr = normalize_currency(currency)
    if curr == "CLP":
        return 1.0, False
    day = (date_str or date.today().isoformat())[:10]
    q = db.query(ExchangeRateHistory.date, ExchangeRateHistory.rate_to_clp).filter(ExchangeRateHistory.currency_code == curr)
    row = q.filter(ExchangeRateHistory.date <= day).order_by(desc(ExchangeRateHistory.date)).first()
    if not row:
        # Date earlier than any stored rate: the oldest one we have, else a hard-coded approximation
        oldest = q.order_by(ExchangeRateHistory.date).first()
        return (oldest[1] if oldest else FALLBACK_RATES.get(curr, 1.0)), True
    rate_day, rate = row
    if rate_day == day:
        return rate, False
    if _days_between(rate_day, day) > MAX_RATE_GAP_DAYS:
        return rate, True
    # A gap of a few days is a weekend or holiday, unless nothing newer is stored yet (not synced yet)
    newest = db.query(func.max(ExchangeRateHistory.date)).filter(ExchangeRateHistory.currency_code == curr).scalar()
    return rate, newest == rate_day


def _days_between(earlier: str, later: str) -> int:
    try:
        return (date.fromisoformat(later) - date.fromisoformat(earlier)).days
    except ValueError:
        return 0


def get_exchange_rate(db: Session, currency: str, date_str: Optional[str] = None) -> float:
    """CLP per unit of `currency` on `date_str` (see resolve_rate)."""
    return resolve_rate(db, currency, date_str)[0]


def refresh_estimated_rates(db: Session) -> int:
    """Re-resolves provisional rates. Returns how many became official. Rates typed by the user are never marked."""
    fixed = 0
    for tx in db.query(Transaction).filter(Transaction.rate_estimated == True).all():
        rate, estimated = resolve_rate(db, tx.currency, tx.date)
        if abs(rate - (tx.exchange_rate or 0)) > 1e-9:
            tx.exchange_rate = rate
            tx.base_amount = round((tx.amount or 0.0) * rate, 2)
        tx.rate_estimated = estimated
        fixed += not estimated
    db.commit()
    return fixed


def rates_status(db: Session) -> Dict:
    """Today's value of every supported currency and how the last sync went (Settings > Exchange rates)."""
    currencies = []
    for code in CURRENCIES:
        row = db.query(ExchangeRateHistory.date, ExchangeRateHistory.rate_to_clp).filter(
            ExchangeRateHistory.currency_code == code, ExchangeRateHistory.date <= date.today().isoformat()
        ).order_by(desc(ExchangeRateHistory.date)).first()
        currencies.append({"code": code, "name": t(f"rates.currency.{code}"),
                           "rate": row[1] if row else None, "date": row[0] if row else None})
    return {
        "currencies": currencies,
        "last_sync": get_setting(db, "exchange_rate_last_sync") or None,
        "last_attempt": get_setting(db, "exchange_rate_last_attempt") or None,
        "last_result": get_setting(db, "exchange_rate_last_result") or None,
        "estimated_count": db.query(Transaction.id).filter(Transaction.rate_estimated == True).count(),
    }


class RateCache:
    """Memoizes resolve_rate for bulk computations (balances over many transactions, CSV imports)."""

    def __init__(self, db: Session):
        self.db = db
        self._cache = {}

    def resolve(self, currency: str, date_str: Optional[str] = None) -> Tuple[float, bool]:
        key = (normalize_currency(currency), (date_str or "")[:10])
        if key not in self._cache:
            self._cache[key] = resolve_rate(self.db, key[0], key[1] or None)
        return self._cache[key]

    def get(self, currency: str, date_str: Optional[str] = None) -> float:
        return self.resolve(currency, date_str)[0]
