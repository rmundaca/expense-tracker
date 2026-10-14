"""v1 -> v2 migration: balances must be preserved exactly while moving to derived balances."""
import os
import sqlite3
import tempfile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

V1_SCHEMA = """
CREATE TABLE accounts (id INTEGER PRIMARY KEY, name VARCHAR(120) NOT NULL, type VARCHAR(50) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'CLP', balance FLOAT, color VARCHAR(20), icon VARCHAR(50),
    is_active BOOLEAN, created_at DATETIME);
CREATE TABLE categories (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, type VARCHAR(20) NOT NULL,
    color VARCHAR(20), icon VARCHAR(50), parent_id INTEGER, is_active BOOLEAN);
CREATE TABLE transactions (id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL, category_id INTEGER,
    type VARCHAR(20) NOT NULL, amount FLOAT NOT NULL, currency VARCHAR(10) NOT NULL DEFAULT 'CLP',
    exchange_rate FLOAT NOT NULL DEFAULT 1.0, base_amount FLOAT, base_currency VARCHAR(10) NOT NULL DEFAULT 'CLP',
    date VARCHAR(30) NOT NULL, merchant VARCHAR(150), description TEXT, raw_text TEXT, source VARCHAR(30),
    email_message_id VARCHAR(150) UNIQUE, status VARCHAR(30), destination_account_id INTEGER,
    ai_confidence FLOAT, created_at DATETIME);
CREATE TABLE ml_training_samples (id INTEGER PRIMARY KEY, text TEXT NOT NULL, category_id INTEGER,
    account_id INTEGER, destination_account_id INTEGER, tx_type VARCHAR(20), source VARCHAR(40), created_at DATETIME);
CREATE TABLE settings (key VARCHAR(100) PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE system_events (id INTEGER PRIMARY KEY, message VARCHAR(255));
CREATE TABLE currency_series (id INTEGER PRIMARY KEY, code VARCHAR(10));
"""


def build_v1_db(path):
    con = sqlite3.connect(path)
    con.executescript(V1_SCHEMA)
    con.executescript("""
        INSERT INTO accounts VALUES (1, 'Corriente', 'checking', 'CLP', 150000, NULL, NULL, 1, NULL);
        INSERT INTO accounts VALUES (2, 'Tarjeta USD', 'credit', 'USD', -40, NULL, NULL, 1, NULL);
        INSERT INTO accounts VALUES (3, 'Importada sin ajustar', 'checking', 'CLP', 0, NULL, NULL, 1, NULL);
        INSERT INTO categories VALUES (1, 'Supermercado', 'expense', NULL, NULL, NULL, 1);
        INSERT INTO categories VALUES (2, 'Ajustes y Reconciliación', 'expense', NULL, NULL, NULL, 1);
        -- running balance of account 1 = 200000 (initial reconciliation) - 50000 (expense)
        INSERT INTO transactions (id, account_id, category_id, type, amount, date, merchant, status)
            VALUES (1, 1, 2, 'income', 200000, '2026-09-01', 'Reconciliación de Saldo', 'confirmed');
        INSERT INTO transactions (id, account_id, category_id, type, amount, date, merchant, status)
            VALUES (2, 1, 1, 'expense', 50000, '2026-09-02', 'Jumbo', 'confirmed');
        -- US$ 40 charge on the USD card
        INSERT INTO transactions (id, account_id, category_id, type, amount, currency, exchange_rate, date, merchant, status)
            VALUES (3, 2, 1, 'expense', 40, 'USD', 950, '2026-09-03', 'Amazon', 'confirmed');
        -- CSV history imported WITHOUT adjusting the stored balance (v1 allowed it)
        INSERT INTO transactions (id, account_id, category_id, type, amount, date, merchant, status)
            VALUES (4, 3, 1, 'expense', 99999, '2022-01-01', 'Antiguo', 'confirmed');
        -- pending movements never touched balances
        INSERT INTO transactions (id, account_id, category_id, type, amount, date, merchant, status)
            VALUES (5, 1, 1, 'expense', 777, '2026-09-04', 'Pendiente', 'pending_review');
        INSERT INTO ml_training_samples (text, category_id, source) VALUES ('test sample', 1, 'unit_test');
        INSERT INTO ml_training_samples (text, category_id, source) VALUES ('jumbo', 1, 'user_feedback');
        INSERT INTO settings VALUES ('bcch_password', 'secret'), ('pref_theme', 'dark'), ('gmail_email', 'me@gmail.com');
        INSERT INTO system_events (message) VALUES ('old log');
    """)
    con.commit()
    con.close()


def test_v1_database_is_migrated_without_changing_balances():
    from app.models.schemas import MailAccount, Setting, Transaction, MLTrainingSample, run_migrations, get_setting
    from app.services.balances import compute_balances

    path = os.path.join(tempfile.mkdtemp(), "v1.db")
    build_v1_db(path)
    engine = create_engine(f"sqlite:///{path}")
    run_migrations(engine)
    run_migrations(engine)  # idempotent

    db = sessionmaker(bind=engine)()
    assert compute_balances(db) == {1: 150000.0, 2: -40.0, 3: 0.0}

    recon = db.get(Transaction, 1)
    assert (recon.type, recon.amount, recon.category_id) == ("adjustment", 200000, None)
    assert db.query(Transaction).filter(Transaction.category_id == 2).count() == 0

    keys = {s.key for s in db.query(Setting).all()}
    assert "bcch_password" not in keys and "pref_theme" not in keys and "gmail_email" not in keys
    assert [(m.provider, m.email) for m in db.query(MailAccount).all()] == [("gmail", "me@gmail.com")]
    assert get_setting(db, "schema_version") == "4"
    assert [s.source for s in db.query(MLTrainingSample).all()] == ["user_feedback"]

    tables = {r[0] for r in sqlite3.connect(path).execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "system_events" not in tables and "currency_series" not in tables
    db.close()


def test_imported_emails_get_their_suggestion_source(tmp_path):
    import sqlite3
    from app.core.database import make_engine
    from app.models.schemas import run_migrations

    path = tmp_path / "old.db"
    engine = make_engine(path)
    run_migrations(engine)
    con = sqlite3.connect(str(path))
    for i, (conf, source) in enumerate([(1.0, "email"), (0.95, "email"), (0.5, "email"), (0.0, "email"), (None, "manual")]):
        con.execute("INSERT INTO transactions (account_id, type, amount, currency, exchange_rate, base_currency, date, "
                    "source, status, ai_confidence) VALUES (1, 'expense', 1, 'CLP', 1, 'CLP', '2026-09-01', ?, 'pending_review', ?)",
                    (source, conf))
    con.commit()
    run_migrations(engine)  # an upgrade: rows imported before ai_source existed
    got = [r[0] for r in con.execute("SELECT ai_source FROM transactions ORDER BY id")]
    con.close()
    engine.dispose()
    assert got == ["rule", "memory", "ml", "none", None]


def test_imported_movements_with_wrong_rates_become_provisional(tmp_path):
    import sqlite3
    from app.core.database import make_engine
    from app.models.schemas import run_migrations

    path = tmp_path / "v2.db"
    engine = make_engine(path)
    run_migrations(engine)
    con = sqlite3.connect(str(path))
    con.execute("UPDATE settings SET value = '2' WHERE key = 'schema_version'")
    con.execute("INSERT INTO exchange_rate_history (currency_code, date, series_id, raw_value, rate_to_clp) "
                "VALUES ('USD', '2026-09-01', 't', 950, 950)")
    rows = [("csv_import", "2022-03-10", 950.0), ("csv_import", "2026-09-01", 950.0), ("manual", "2022-03-10", 950.0)]
    for source, day, rate in rows:
        con.execute("INSERT INTO transactions (account_id, type, amount, currency, exchange_rate, base_currency, date, "
                    "source, status) VALUES (1, 'expense', 1, 'USD', ?, 'CLP', ?, ?, 'confirmed')", (rate, day, source))
    con.commit()
    run_migrations(engine)
    got = [bool(r[0]) for r in con.execute("SELECT rate_estimated FROM transactions ORDER BY id")]
    con.close()
    engine.dispose()
    # 2022 had no official value (got the oldest one); 2026-09-01 is right; manual rates may be typed: untouched
    assert got == [True, False, False]
