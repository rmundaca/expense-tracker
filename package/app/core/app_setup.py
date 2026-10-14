"""
Startup of the shared app.db and the one-time move from the single-user layout (<= 2.0.x):

  data/expense_tracker.db  ->  data/users/<id>.db  (owned by LEGACY_ADMIN_USERNAME, an administrator)

The existing password hash is kept, so the owner logs in with their username and their current password.
If the old install never had a password, the database waits and is adopted by the first user created
through the first-run setup.
"""
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from app.core import auth
from app.core.config import LEGACY_DB_PATH, USERS_DIR, user_db_path
from app.core.database import AppBase, app_engine, dispose_user_engine
from app.models import app_schemas  # noqa: F401  (registers the app.db tables)

logger = logging.getLogger("app_setup")

LEGACY_ADMIN_USERNAME = "admin"
_LEGACY_AUTH_KEYS = ("auth_password_hash", "auth_secret_key")
_SQLITE_SIDE_FILES = ("-wal", "-shm")


def init_app_database():
    """Creates app.db and migrates a single-user install. Safe to run on every start."""
    AppBase.metadata.create_all(bind=app_engine)
    if not LEGACY_DB_PATH.exists():
        return
    if auth.is_configured():
        logger.warning(f"{LEGACY_DB_PATH.name} is still present but users already exist; left untouched")
        return
    password_hash = _read_legacy_password_hash()
    if not password_hash:
        logger.info("Previous database without a password: the first user created will adopt it")
        return
    user = auth.create_user(LEGACY_ADMIN_USERNAME, display_name=LEGACY_ADMIN_USERNAME,
                            is_admin=True, password_hash=password_hash)
    adopt_legacy_database(user.id)


def adopt_legacy_database(user_id: int) -> bool:
    """Moves the single-user database (if any) to this user, keeping a backup copy. Returns True if moved."""
    if not LEGACY_DB_PATH.exists():
        return False
    target = user_db_path(user_id)
    if target.exists():
        raise RuntimeError(f"{target} already exists; not overwriting it with {LEGACY_DB_PATH.name}")
    USERS_DIR.mkdir(parents=True, exist_ok=True)
    dispose_user_engine(user_id)

    backup = LEGACY_DB_PATH.with_name(f"{LEGACY_DB_PATH.name}.pre-multiuser-{datetime.now().strftime('%Y%m%d%H%M%S')}")
    src = sqlite3.connect(str(LEGACY_DB_PATH))
    try:
        # Full copy including the WAL contents, then fold the WAL into the main file before moving it
        dst = sqlite3.connect(str(backup))
        try:
            src.backup(dst)
        finally:
            dst.close()
        src.execute(f"DELETE FROM settings WHERE key IN ({','.join('?' * len(_LEGACY_AUTH_KEYS))})", _LEGACY_AUTH_KEYS)
        src.commit()
        src.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        src.close()

    os.replace(LEGACY_DB_PATH, target)
    for suffix in _SQLITE_SIDE_FILES:
        side = Path(f"{LEGACY_DB_PATH}{suffix}")
        if side.exists():
            side.unlink()
    logger.info(f"Single-user database moved to {target.name} (backup: {backup.name})")
    return True


def _read_legacy_password_hash():
    con = sqlite3.connect(str(LEGACY_DB_PATH))
    try:
        row = con.execute("SELECT value FROM settings WHERE key = 'auth_password_hash'").fetchone()
    except sqlite3.OperationalError:  # no settings table
        row = None
    finally:
        con.close()
    return row[0] if row and row[0] else None
