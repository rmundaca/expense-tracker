"""
Imports a Toshl Finance CSV export (or any CSV with the same columns in Spanish/English).
Missing accounts and categories are created; every imported row also teaches the classifier.
"""
import csv
import io
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.i18n import t
from app.models.schemas import Account, Category, Tag, Transaction, default_category_names
from app.services.classifier import classifier_service
from app.services.exchange_rates import SUPPORTED_CURRENCIES, RateCache, normalize_currency

logger = logging.getLogger("csv_import")

# Toshl's English default categories -> this app's default categories (keys of models/schemas.DEFAULT_CATEGORIES)
TOSHL_CATEGORY_MAP = {
    "food & drinks": "groceries",
    "home & utilities": "home",
    "health & personal care": "health",
    "transport": "transport",
    "transportation": "transport",
    "leisure": "leisure",
    "clothing & footwear": "shopping",
    "education": "education",
    "salary": "salary",
    "reimbursements": "other_income",
    "grants": "other_income",
    "loans": "other_income",
    "bank": "other_expense",
    "other": "other_expense",
    "gifts": "other_expense",
    "charity": "other_expense",
}

# (toshl category, tag) -> more specific default category
TAG_CATEGORY_OVERRIDES = {
    ("food & drinks", "restaurants"): "restaurants",
    ("food & drinks", "restaurant"): "restaurants",
    ("food & drinks", "almuerzo"): "restaurants",
    ("leisure", "streaming"): "leisure",
    ("health & personal care", "gym"): "health",
}

COLOR_PALETTE = ["#ff5252", "#ff793f", "#ffb142", "#34ace0", "#33d9b2", "#706fd3", "#778beb", "#e056fd", "#22a6b3", "#6ab04c"]

TRANSFER_CATEGORY_NAMES = ("transfer", "transferencia", "transferencias")


def parse_date(value: str) -> Optional[str]:
    """DD-MM-YY, DD-MM-YYYY, DD/MM/YYYY or YYYY-MM-DD -> YYYY-MM-DD."""
    value = value.strip()
    patterns = [
        (r"^(\d{1,2})[-/](\d{1,2})[-/](\d{2})$", lambda d, m, y: (2000 + int(y), int(m), int(d))),
        (r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$", lambda d, m, y: (int(y), int(m), int(d))),
        (r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", lambda y, m, d: (int(y), int(m), int(d))),
    ]
    for regex, build in patterns:
        match = re.match(regex, value)
        if match:
            year, month, day = build(*match.groups())
            try:
                return datetime(year, month, day).strftime("%Y-%m-%d")
            except ValueError:
                return None
    return None


def parse_amount(value: str) -> float:
    """'6.990' -> 6990, '14.000.000' -> 14000000, '45,00' -> 45, '1.250,50' -> 1250.5."""
    cleaned = re.sub(r"[^\d.,-]", "", value or "")
    if not cleaned or cleaned in ("0", "-"):
        return 0.0
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    elif "." in cleaned:
        parts = cleaned.split(".")
        if len(parts) > 2 or len(parts[-1]) == 3:
            cleaned = cleaned.replace(".", "")
    try:
        return abs(float(cleaned))
    except ValueError:
        return 0.0


class _Row:
    def __init__(self, date, account, category_name, tags, amount, is_income, currency, description):
        self.date, self.account, self.category_name = date, account, category_name
        self.tags, self.amount, self.is_income = tags, amount, is_income
        self.currency, self.description = currency, description

    @property
    def is_transfer(self) -> bool:
        return self.category_name.lower() in TRANSFER_CATEGORY_NAMES


def import_csv(db: Session, content) -> Dict:
    text = content.decode("utf-8-sig", errors="ignore") if isinstance(content, bytes) else content.lstrip("﻿")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError(t("csv.no_headers"))
    fields = {f.strip().lower(): f for f in reader.fieldnames if f}

    def field(row, *names) -> str:
        for name in names:
            if name in fields and row.get(fields[name]) is not None:
                return str(row[fields[name]]).strip()
        return ""

    accounts = {a.name.lower(): a for a in db.query(Account).all()}
    categories = {c.name.lower(): c for c in db.query(Category).all()}
    tags_cache = {tag.name: tag for tag in db.query(Tag).all()}
    created = {"accounts": 0, "categories": 0}

    def get_account(name: str, currency: str) -> Account:
        name = (name or "").strip() or t("csv.imported_account")
        key = name.lower()
        if key not in accounts:
            acc = Account(name=name, type="corriente", currency=currency,
                          opening_balance=0.0, color="#1976d2", icon="building-columns")
            db.add(acc)
            db.flush()
            accounts[key] = acc
            created["accounts"] += 1
        return accounts[key]

    def default_category(key: str) -> Optional[Category]:
        return next((categories[n.lower()] for n in default_category_names(key) if n.lower() in categories), None)

    def get_category(name: str, tags: List[str], tx_type: str, default_key: Optional[str] = None) -> Optional[Category]:
        key = name.strip().lower()
        if not key:
            return None
        target = next((TAG_CATEGORY_OVERRIDES[(key, tag)] for tag in tags if (key, tag) in TAG_CATEGORY_OVERRIDES), None)
        target = target or TOSHL_CATEGORY_MAP.get(key) or default_key
        if target and default_category(target):
            return default_category(target)
        if key in categories:
            return categories[key]
        cat = Category(name=name.strip(), type=tx_type,
                       color=COLOR_PALETTE[len(categories) % len(COLOR_PALETTE)], icon="tag")
        db.add(cat)
        db.flush()
        categories[key] = cat
        created["categories"] += 1
        return cat

    rows: List[_Row] = []
    for raw in reader:
        date = parse_date(field(raw, "date", "fecha"))
        expense = parse_amount(field(raw, "expense amount", "monto gasto", "gasto"))
        income = parse_amount(field(raw, "income amount", "monto ingreso", "ingreso"))
        if not date or (expense <= 0 and income <= 0):
            continue
        tags = [tag.strip().lower() for tag in field(raw, "tags", "etiquetas").split(",") if tag.strip()]
        rows.append(_Row(
            date=date, account=field(raw, "account", "cuenta"),
            category_name=field(raw, "category", "categoria", "categoría"), tags=tags,
            amount=income if income > 0 and expense <= 0 else expense, is_income=income > 0 and expense <= 0,
            currency=normalize_currency(field(raw, "currency", "moneda") or "CLP"),
            description=field(raw, "description", "descripcion", "descripción", "detalle"),
        ))

    unsupported = sorted({r.currency for r in rows} - set(SUPPORTED_CURRENCIES))
    if unsupported:
        raise ValueError(t("csv.unsupported_currencies", found=", ".join(unsupported), supported=", ".join(SUPPORTED_CURRENCIES)))

    # Toshl exports a transfer as two rows (out of one account, into another): pair them
    incoming = [r for r in rows if r.is_transfer and r.is_income]
    pairs = {}
    for out in (r for r in rows if r.is_transfer and not r.is_income):
        match = next((r for r in incoming if r.date == out.date and abs(r.amount - out.amount) < 0.01
                      and r.account != out.account and id(r) not in pairs), None)
        if match:
            pairs[id(match)] = out
            pairs[id(out)] = match

    existing = {
        (d[:10], round(a, 2), acc, (m or "")[:20].lower())
        for d, a, acc, m in db.query(Transaction.date, Transaction.amount, Transaction.account_id, Transaction.merchant)
    }
    imported = duplicates = estimated_rates = 0
    handled = set()
    rates = RateCache(db)
    for row in rows:
        if id(row) in handled:
            continue
        handled.add(id(row))
        account = get_account(row.account, row.currency)
        merchant = row.description or row.category_name or t("csv.imported_merchant")
        tx = Transaction(account_id=account.id, amount=row.amount, currency=row.currency, date=row.date,
                         merchant=merchant[:150], source="csv_import", status="confirmed")

        partner = pairs.get(id(row))
        if row.is_transfer and partner:
            handled.add(id(partner))
            out, into = (partner, row) if row.is_income else (row, partner)
            tx.account_id = get_account(out.account, out.currency).id
            tx.destination_account_id = get_account(into.account, into.currency).id
            tx.type = "transfer"
            tx.currency, tx.amount = out.currency, out.amount
        elif row.is_transfer and not row.is_income:
            # Money left to an account that is not in the export
            tx.type, tx.destination_account_id = "transfer", None
        else:
            tx.type = "income" if row.is_income else "expense"
            name, default_key = row.category_name, None
            if row.is_transfer:  # money received from outside the export
                name, default_key = t("seed.category.transfers_in"), "transfers_in"
            category = get_category(name, row.tags, tx.type, default_key)
            if category and category.type != tx.type:
                suffix = "csv.category_income_suffix" if tx.type == "income" else "csv.category_expense_suffix"
                category = get_category(t(suffix, name=name), [], tx.type)
            tx.category_id = category.id if category else None

        signature = (tx.date, round(tx.amount, 2), tx.account_id, merchant[:20].lower())
        if signature in existing:
            duplicates += 1
            continue
        existing.add(signature)

        tx.exchange_rate, tx.rate_estimated = rates.resolve(tx.currency, tx.date)
        estimated_rates += tx.rate_estimated
        tx.base_amount = round(tx.amount * tx.exchange_rate, 2)
        tx.base_currency = "CLP"
        db.add(tx)
        for name in row.tags:
            if name not in tags_cache:
                tags_cache[name] = Tag(name=name[:60])
                db.add(tags_cache[name])
            tx.tags.append(tags_cache[name])
        if tx.type in ("expense", "income") and tx.category_id:
            classifier_service.learn(db, tx.merchant, None, category_id=tx.category_id,
                                     account_id=tx.account_id, tx_type=tx.type, source="csv_import")
        imported += 1

    db.commit()
    message = t("csv.result", imported=imported, duplicates=duplicates,
                accounts=created["accounts"], categories=created["categories"])
    logger.info(f"CSV import: {imported} imported, {duplicates} duplicates, "
                f"{created['accounts']} accounts and {created['categories']} categories created")
    if estimated_rates:
        message += t("csv.estimated_rates", count=estimated_rates)
    return {"imported": imported, "duplicates": duplicates, "estimated_rates": estimated_rates,
            "accounts_created": created["accounts"],
            "categories_created": created["categories"], "message": message}
