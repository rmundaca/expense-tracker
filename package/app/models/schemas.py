import json
import logging
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey, Table, text
)
from sqlalchemy.orm import relationship

from app import i18n
from app.core.database import Base

logger = logging.getLogger("schemas")

def utcnow():
    """Returns naive UTC datetime compatible with SQLite and SQLAlchemy DateTime."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


transaction_tags = Table(
    "transaction_tags",
    Base.metadata,
    Column("transaction_id", Integer, ForeignKey("transactions.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    type = Column(String(50), nullable=False)  # corriente, vista, credito, inversiones, afp, efectivo, ahorro
    currency = Column(String(10), default="CLP", nullable=False)
    # Balance before the first recorded transaction. The current balance is always
    # opening_balance + effect of confirmed transactions (see services/balances.py).
    opening_balance = Column(Float, default=0.0, nullable=False)
    color = Column(String(20), default="#00c853")
    icon = Column(String(50), default="wallet")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    transactions = relationship("Transaction", back_populates="account", cascade="all, delete-orphan", foreign_keys="[Transaction.account_id]")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String(20), nullable=False)  # expense, income
    color = Column(String(20), default="#ff5252")
    icon = Column(String(50), default="tag")
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    is_active = Column(Boolean, default=True)

    transactions = relationship("Transaction", back_populates="category")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(60), unique=True, index=True, nullable=False)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    # expense, income, transfer, adjustment (a signed balance correction, never counted as income/expense)
    type = Column(String(20), nullable=False)
    amount = Column(Float, nullable=False)  # positive, except signed adjustments
    currency = Column(String(10), default="CLP", nullable=False)
    exchange_rate = Column(Float, default=1.0, nullable=False)  # CLP per unit of `currency` on `date`
    # No official value covered `date` when the rate was set: replaced after the next rates sync
    rate_estimated = Column(Boolean, default=False, server_default=text("0"), nullable=False)
    base_amount = Column(Float, nullable=True)  # amount in CLP
    base_currency = Column(String(10), default="CLP", nullable=False)
    date = Column(String(30), nullable=False)  # YYYY-MM-DD or YYYY-MM-DD HH:MM:SS
    merchant = Column(String(150), nullable=True)
    description = Column(Text, nullable=True)
    raw_text = Column(Text, nullable=True)
    source = Column(String(30), default="manual")  # manual, email, csv_import, transfer, recurring
    email_message_id = Column(String(150), unique=True, index=True, nullable=True)
    # The bank's operation id: the sender's and the recipient's notices of one transfer share it
    bank_reference = Column(String(80), index=True, nullable=True)
    status = Column(String(30), default="confirmed")  # confirmed, pending_review
    destination_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    recurring_id = Column(Integer, ForeignKey("recurring_rules.id"), nullable=True)  # occurrence of a RecurringRule
    ai_confidence = Column(Float, nullable=True)
    ai_source = Column(String(20), nullable=True)  # who suggested an imported movement: rule, memory, ml, none
    created_at = Column(DateTime, default=utcnow)

    account = relationship("Account", foreign_keys=[account_id], back_populates="transactions")
    destination_account = relationship("Account", foreign_keys=[destination_account_id])
    category = relationship("Category", back_populates="transactions")
    tags = relationship("Tag", secondary=transaction_tags, backref="transactions")


class RecurringRule(Base):
    """A movement that repeats. Each occurrence becomes a Transaction on its date (services/recurrence.py)."""
    __tablename__ = "recurring_rules"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(20), nullable=False)  # expense, income, transfer
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="CLP", nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    destination_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    merchant = Column(String(150), nullable=True)
    description = Column(Text, nullable=True)
    frequency = Column(String(10), nullable=False)  # day, week, month, year
    start_date = Column(String(10), nullable=False)  # YYYY-MM-DD, first occurrence
    end_date = Column(String(10), nullable=True)  # last possible occurrence; none = forever
    last_date = Column(String(10), nullable=True)  # latest occurrence already created
    auto_confirm = Column(Boolean, default=True, nullable=False)  # false: occurrences wait in Review
    created_at = Column(DateTime, default=utcnow)


class Budget(Base):
    """A spending limit that repeats every `period_count` periods from start_date (or covers one range)."""
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    scope = Column(String(10), default="all", nullable=False)  # all, include (these categories), exclude (all but these)
    category_ids = Column(Text, default="[]", nullable=False)  # JSON array
    amount_type = Column(String(10), default="fixed", nullable=False)  # fixed, income_pct
    amount = Column(Float, nullable=False)  # money, or % of the expected monthly income
    period = Column(String(10), default="month", nullable=False)  # day, week, month, year, once
    period_count = Column(Integer, default=1, nullable=False)
    start_date = Column(String(10), nullable=False)
    end_date = Column(String(10), nullable=True)  # only for period "once"
    created_at = Column(DateTime, default=utcnow)

    @property
    def category_list(self):
        try:
            return [int(x) for x in json.loads(self.category_ids or "[]")]
        except (ValueError, TypeError):
            return []


class RuleMapping(Base):
    __tablename__ = "rule_mappings"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=True)
    pattern = Column(Text, nullable=False)
    match_field = Column(String(30), default="any")  # merchant, description, sender, any
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    destination_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    tx_type = Column(String(20), default="expense", nullable=False)  # expense, income, transfer
    is_regex = Column(Boolean, default=False)
    priority = Column(Integer, default=10)
    is_active = Column(Boolean, default=True)

    category = relationship("Category")
    account = relationship("Account", foreign_keys=[account_id])
    destination_account = relationship("Account", foreign_keys=[destination_account_id])


class MLTrainingSample(Base):
    """What the user confirmed for a given merchant/text; feeds the classifier's memory and Naive Bayes."""
    __tablename__ = "ml_training_samples"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    merchant_key = Column(String(150), index=True, nullable=True)  # normalized merchant for exact recall
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    destination_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    tx_type = Column(String(20), default="expense", nullable=False)
    source = Column(String(40), default="user_correction")
    created_at = Column(DateTime, default=utcnow)


class IgnoredEmail(Base):
    __tablename__ = "ignored_emails"

    id = Column(Integer, primary_key=True, index=True)
    email_message_id = Column(String(150), unique=True, index=True, nullable=False)
    subject = Column(String(255), nullable=True)
    sender = Column(String(255), nullable=True)
    reason = Column(String(100), default="user_discarded")  # user_discarded, user_deleted, unparseable
    created_at = Column(DateTime, default=utcnow)


class MailAccount(Base):
    """A mailbox whose bank emails are imported. A user may have several (services/mail/)."""
    __tablename__ = "mail_accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    provider = Column(String(20), nullable=False)  # gmail, outlook, imap, pop3
    email = Column(String(255), nullable=False)  # login user (and XOAUTH2 user for outlook)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False)
    security = Column(String(10), default="ssl", nullable=False)  # ssl, starttls
    folders = Column(Text, default="", nullable=False)  # IMAP folders, one per line; empty = inbox (+ All Mail)
    # Encrypted (core/crypto.py): the password, or the OAuth refresh token for outlook
    secret = Column(Text, default="", nullable=False)
    oauth_client_id = Column(String(100), nullable=True)  # the user's own Azure app registration
    oauth_tenant = Column(String(100), nullable=True)  # common, consumers, organizations or a tenant id
    is_enabled = Column(Boolean, default=True, nullable=False)
    last_sync = Column(String(30), nullable=True)  # last successful sync
    last_result = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class BankProfile(Base):
    __tablename__ = "bank_profiles"

    id = Column(Integer, primary_key=True, index=True)
    bank_code = Column(String(50), unique=True, nullable=False)
    bank_name = Column(String(100), nullable=False)
    sender_emails = Column(Text, nullable=False)  # JSON array
    subject_keywords = Column(Text, nullable=False)  # JSON array
    default_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    is_enabled = Column(Boolean, default=True)

    default_account = relationship("Account")

    @property
    def sender_list(self):
        try:
            items = json.loads(self.sender_emails or "[]")
        except ValueError:
            items = []
        return [str(x).strip().lower() for x in items if str(x).strip()]


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)


class ExchangeRateHistory(Base):
    __tablename__ = "exchange_rate_history"

    id = Column(Integer, primary_key=True, index=True)
    currency_code = Column(String(10), index=True, nullable=False)  # USD, UF, EUR
    date = Column(String(30), index=True, nullable=False)  # YYYY-MM-DD
    series_id = Column(String(100), nullable=False)
    raw_value = Column(Float, nullable=False)
    rate_to_clp = Column(Float, nullable=False)
    created_at = Column(DateTime, default=utcnow)


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------

def get_setting(db, key: str, default: str = "") -> str:
    rec = db.query(Setting).filter(Setting.key == key).first()
    return rec.value if rec and rec.value is not None else default


def set_setting(db, key: str, value) -> None:
    rec = db.query(Setting).filter(Setting.key == key).first()
    if rec:
        rec.value = str(value)
    else:
        db.add(Setting(key=key, value=str(value)))


# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 4

OBSOLETE_SETTINGS = (
    "app_name", "currency", "base_currency", "pref_theme", "pref_language", "pref_records_per_page",
    "bcch_user", "bcch_password", "bcch_wsdl_url", "exchange_rate_auto_sync",
    "exchange_rate_sync_interval_mins", "gmail_sync_task_last_manual_run",
    "exchange_rates_sync_task_last_manual_run",
)

# Merchant and category names that v1 (Spanish only) used for balance corrections
RECONCILIATION_MERCHANT = "Reconciliación de Saldo"


def _columns(conn, table: str) -> set:
    return {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()}


def _add_missing_columns(conn, table: str, expected: dict):
    existing = _columns(conn, table)
    if not existing:
        return
    for name, ddl in expected.items():
        if name not in existing:
            conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def run_migrations(engine):
    """Creates tables, adds columns missing from older databases and applies versioned data migrations."""
    from sqlalchemy.orm import Session

    with engine.connect() as conn:
        fresh = not _columns(conn, "accounts")  # new database: already at the current schema
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        _add_missing_columns(conn, "transactions", {
            "currency": "VARCHAR(10) DEFAULT 'CLP'",
            "exchange_rate": "FLOAT DEFAULT 1.0",
            "base_amount": "FLOAT",
            "base_currency": "VARCHAR(10) DEFAULT 'CLP'",
            "ai_confidence": "FLOAT",
            "ai_source": "VARCHAR(20)",
            "rate_estimated": "BOOLEAN DEFAULT 0 NOT NULL",
            "destination_account_id": "INTEGER",
            "recurring_id": "INTEGER",
            "bank_reference": "VARCHAR(80)",
        })
        _add_missing_columns(conn, "accounts", {"opening_balance": "FLOAT DEFAULT 0.0 NOT NULL"})
        _add_missing_columns(conn, "ml_training_samples", {
            "account_id": "INTEGER",
            "destination_account_id": "INTEGER",
            "tx_type": "VARCHAR(20) DEFAULT 'expense'",
            "merchant_key": "VARCHAR(150)",
        })
        _add_missing_columns(conn, "rule_mappings", {
            "destination_account_id": "INTEGER",
            "tx_type": "VARCHAR(20) DEFAULT 'expense'",
        })
        conn.exec_driver_sql("UPDATE transactions SET exchange_rate = 1.0 WHERE exchange_rate IS NULL OR exchange_rate <= 0")
        conn.exec_driver_sql("UPDATE transactions SET base_amount = ROUND(amount * exchange_rate, 2) WHERE base_amount IS NULL")
        # Emails imported before ai_source existed: the classifier's confidence tells which source it was
        conn.exec_driver_sql(
            "UPDATE transactions SET ai_source = CASE WHEN ai_confidence >= 1 THEN 'rule' "
            "WHEN ai_confidence >= 0.95 THEN 'memory' WHEN ai_confidence > 0 THEN 'ml' ELSE 'none' END "
            "WHERE ai_source IS NULL AND source = 'email'"
        )
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_transactions_date_status ON transactions(date, status)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_transactions_account_date ON transactions(account_id, date)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_transactions_category_date ON transactions(category_id, date)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_transactions_bank_reference ON transactions(bank_reference)")

    with Session(bind=engine) as db:
        version = SCHEMA_VERSION if fresh else int(get_setting(db, "schema_version", "1") or 1)
        if version < 2:
            _migrate_to_v2(engine, db)
        if version < 3:
            _migrate_to_v3(db)
        if version < 4:
            _migrate_to_v4(db)
        if version < SCHEMA_VERSION:
            set_setting(db, "schema_version", SCHEMA_VERSION)
            db.commit()


def _migrate_to_v2(engine, db):
    """
    v1 stored a running `accounts.balance` mutated on every change, and recorded balance corrections
    as income/expense ("Reconciliación de Saldo"). v2 derives balances from transactions:
      1. Reconciliation rows become signed `adjustment` transactions (no longer counted as income/expense).
      2. opening_balance is set so every account keeps exactly the balance v1 was showing.
      3. Obsolete settings (incl. stored BCCh credentials) and tables are removed.
    """
    from app.services.balances import compute_balances

    recon_cat_ids = [c.id for c in db.query(Category).filter(
        (Category.name == "Ajustes y Reconciliación") | (Category.name.ilike("%reconcilia%"))
    ).all()]
    recon_q = db.query(Transaction).filter(Transaction.merchant == RECONCILIATION_MERCHANT)
    if recon_cat_ids:
        recon_q = db.query(Transaction).filter(
            (Transaction.merchant == RECONCILIATION_MERCHANT) | (Transaction.category_id.in_(recon_cat_ids))
        )
    converted = 0
    for tx in recon_q.all():
        if tx.type not in ("income", "expense"):
            continue
        sign = 1 if tx.type == "income" else -1
        tx.amount = sign * abs(tx.amount or 0.0)
        tx.base_amount = round(tx.amount * (tx.exchange_rate or 1.0), 2)
        tx.type = "adjustment"
        tx.category_id = None
        tx.merchant = i18n.t("accounts.adjustment")
        converted += 1
    db.flush()
    for cat_id in recon_cat_ids:
        if not db.query(Transaction.id).filter(Transaction.category_id == cat_id).first():
            db.query(Category).filter(Category.id == cat_id).delete(synchronize_session=False)

    # Same connection as the session: a second connection would block on the session's open write
    has_legacy_balance = any(row[1] == "balance" for row in db.execute(text("PRAGMA table_info(accounts)")))
    legacy = dict(db.execute(text("SELECT id, COALESCE(balance, 0) FROM accounts")).fetchall()) if has_legacy_balance else {}
    if legacy:
        for acc in db.query(Account).all():
            acc.opening_balance = 0.0
        db.flush()
        effects = compute_balances(db)
        for acc in db.query(Account).all():
            acc.opening_balance = round(float(legacy.get(acc.id, 0.0)) - effects.get(acc.id, 0.0), 2)

    # Samples written by old test suites that ran against the real database
    db.query(MLTrainingSample).filter(MLTrainingSample.source.in_(("test", "unit_test"))).delete(synchronize_session=False)
    db.query(Setting).filter(Setting.key.in_(OBSOLETE_SETTINGS)).delete(synchronize_session=False)
    db.flush()
    db.execute(text("DROP TABLE IF EXISTS system_events"))
    db.execute(text("DROP TABLE IF EXISTS currency_series"))

    from app.core.config import DATA_DIR
    legacy_model = DATA_DIR / "classifier_model.json"
    if legacy_model.exists():
        legacy_model.unlink()
    logger.info(f"Migration v2 applied: {converted} adjustments converted, opening balances computed for {len(legacy)} accounts")


def _migrate_to_v3(db):
    """
    Movements imported (CSV, email) before provisional rates existed may carry a wrong rate: an old CSV
    got the oldest rate stored at the time, an offline install the hard-coded one. Those whose rate
    differs from the official value of their date (or has none yet) become provisional, so the next
    rates sync corrects them. Manual movements are left alone: their rate may have been typed.
    """
    from app.services.exchange_rates import RateCache

    rates = RateCache(db)
    marked = 0
    for tx in db.query(Transaction).filter(
        Transaction.currency != "CLP", Transaction.source.in_(("csv_import", "email"))
    ):
        rate, estimated = rates.resolve(tx.currency, tx.date)
        if estimated or abs(rate - (tx.exchange_rate or 0)) > 1e-9:
            tx.rate_estimated = True
            marked += 1
    db.flush()
    logger.info(f"Migration v3 applied: {marked} imported transactions marked with a provisional rate")


# v3 kept a single Gmail mailbox in settings; v4 moves it to mail_accounts and renames the sync settings
GMAIL_SETTINGS_V3 = {
    "gmail_sync_enabled": "mail_sync_enabled",
    "gmail_sync_interval_mins": "mail_sync_interval_mins",
    "gmail_lookback_days": "mail_lookback_days",
    "gmail_last_sync": "mail_last_sync",
    "gmail_last_result": "mail_last_result",
}


def _migrate_to_v4(db):
    """The Gmail mailbox becomes the first MailAccount, its app password now encrypted (core/crypto.py)."""
    from app.core.crypto import encrypt
    from app.services.mail.providers import PRESETS

    email_user = get_setting(db, "gmail_email").strip()
    app_pwd = get_setting(db, "gmail_app_password").strip()
    if email_user and not db.query(MailAccount.id).first():
        preset = PRESETS["gmail"]
        db.add(MailAccount(name="Gmail", provider="gmail", email=email_user, host=preset["host"], port=preset["port"],
                           security=preset["security"], secret=encrypt(app_pwd), last_sync=get_setting(db, "gmail_last_sync") or None))
    for old, new in GMAIL_SETTINGS_V3.items():
        rec = db.query(Setting).filter(Setting.key == old).first()
        if rec is not None:
            set_setting(db, new, rec.value)
            db.delete(rec)
    db.query(Setting).filter(Setting.key.in_(("gmail_email", "gmail_app_password"))).delete(synchronize_session=False)
    db.flush()
    logger.info(f"Migration v4 applied: {'Gmail mailbox migrated' if email_user else 'no Gmail mailbox configured'}")


# ---------------------------------------------------------------------------
# Seed data (fresh databases only)
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS = {
    "mail_sync_enabled": "false",
    "mail_sync_interval_mins": "30",
    "mail_lookback_days": "7",
    "mail_last_sync": "",
    "mail_last_result": "",
}


# Default data, named in the language of whoever opens the database first. Keys index app/i18n "seed.*".
DEFAULT_ACCOUNTS = [  # key, type, currency, color, icon
    ("checking", "corriente", "CLP", "#1976d2", "building-columns"),
    ("credit_card", "credito", "CLP", "#d32f2f", "credit-card"),
    ("credit_card_usd", "credito", "USD", "#2e7d32", "credit-card"),
    ("cash", "efectivo", "CLP", "#388e3c", "money-bill-wave"),
]
DEFAULT_CATEGORIES = [  # key, type, color, icon
    ("groceries", "expense", "#ff7043", "basket-shopping"),
    ("restaurants", "expense", "#ff5722", "utensils"),
    ("transport", "expense", "#42a5f5", "car"),
    ("home", "expense", "#26a69a", "house"),
    ("health", "expense", "#ec407a", "heart-pulse"),
    ("leisure", "expense", "#ab47bc", "gamepad"),
    ("shopping", "expense", "#5c6bc0", "bag-shopping"),
    ("education", "expense", "#29b6f6", "graduation-cap"),
    ("other_expense", "expense", "#78909c", "tags"),
    ("salary", "income", "#00e676", "money-check-dollar"),
    ("freelance", "income", "#69f0ae", "briefcase"),
    ("returns", "income", "#00b0ff", "arrow-trend-up"),
    ("transfers_in", "income", "#b388ff", "arrows-rotate"),
    ("other_income", "income", "#a7ffeb", "circle-dollar-to-slot"),
]
# Patterns match Chilean merchants as they appear in bank emails
DEFAULT_RULES = [  # key, pattern, category key
    ("supermarkets", "jumbo OR lider OR santa isabel OR unimarc OR tottus OR ok market OR oxxo", "groceries"),
    ("restaurants", "starbucks OR pedidosya OR uber eats OR rappi OR mcdonalds OR burger king", "restaurants"),
    ("transport", "copec OR shell OR petrobras OR metro de santiago OR didi OR cabify OR recarga bip OR uber", "transport"),
    ("utilities", "enel OR cge OR aguas andinas OR vtr OR entel OR movistar OR wom OR gasto comun", "home"),
    ("health", "cruz verde OR salcobrand OR ahumada OR dr simi OR integramedica", "health"),
    ("subscriptions", "netflix OR spotify OR youtube premium OR steam OR amazon prime OR disney", "leisure"),
    ("salary", "sueldo OR remuneracion OR pago nomina OR aguinaldo OR bono", "salary"),
]


def default_category_names(key: str) -> list:
    """Every name a default category may have (it was named in the language of its first use)."""
    return i18n.all_variants(f"seed.category.{key}")


def seed_initial_data(db):
    """Seeds default accounts, categories, rules and Chilean bank profiles into an empty database."""
    fresh = db.query(Account).count() == 0
    if fresh:
        db.add_all([
            Account(name=i18n.t(f"seed.account.{key}"), type=acc_type, currency=currency, color=color, icon=icon)
            for key, acc_type, currency, color, icon in DEFAULT_ACCOUNTS
        ])
        db.commit()

    if db.query(Category).count() == 0:
        db.add_all([
            Category(name=i18n.t(f"seed.category.{key}"), type=cat_type, color=color, icon=icon)
            for key, cat_type, color, icon in DEFAULT_CATEGORIES
        ])
        db.commit()

    if db.query(RuleMapping).count() == 0:
        cats = {c.name: c for c in db.query(Category).all()}
        rules = []
        for key, pattern, cat_key in DEFAULT_RULES:
            cat = cats.get(i18n.t(f"seed.category.{cat_key}"))
            if cat:
                rules.append(RuleMapping(name=i18n.t(f"seed.rule.{key}"), pattern=pattern, match_field="any",
                                         category_id=cat.id, priority=10, tx_type=cat.type))
        db.add_all(rules)
        db.commit()

    if db.query(BankProfile).count() == 0:
        first_acc = db.query(Account).first()
        acc_id = first_acc.id if first_acc else None
        banks = [
            ("bchile", "Banco de Chile / Edwards", ["enviodigital@bancochile.cl", "serviciodetransferencias@bancochile.cl", "envios@bancoedwards.cl"]),
            ("santander", "Banco Santander Chile", ["santanderinforma@santander.cl", "notificaciones@santander.cl"]),
            ("bci", "Banco BCI", ["notificaciones@bci.cl", "bcinforma@bci.cl"]),
            ("falabella", "Banco Falabella", ["notificaciones@bancofalabella.cl", "bancofalabella@bancofalabella.cl"]),
            ("bancoestado", "BancoEstado", ["notificaciones@bancoestado.cl", "contacto@bancoestado.cl"]),
            ("scotiabank", "Scotiabank Chile", ["notificaciones@scotiabank.cl", "informacion@scotiabank.cl"]),
            ("itau", "Banco Itaú Chile", ["notificaciones@itau.cl", "itauinforma@itau.cl"]),
        ]
        db.add_all([
            BankProfile(bank_code=code, bank_name=name, sender_emails=json.dumps(senders),
                        subject_keywords="[]", default_account_id=acc_id, is_enabled=True)
            for code, name, senders in banks
        ])
        db.commit()

    existing_keys = {s.key for s in db.query(Setting).all()}
    for k, v in DEFAULT_SETTINGS.items():
        if k not in existing_keys:
            db.add(Setting(key=k, value=v))
    if fresh and "language" not in existing_keys:
        # Background jobs write their messages in it until the user picks another one in Settings
        db.add(Setting(key="language", value=i18n.current()))
    if "schema_version" not in existing_keys:
        db.add(Setting(key="schema_version", value=str(SCHEMA_VERSION)))
    db.commit()
