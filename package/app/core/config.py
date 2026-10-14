import os
from pathlib import Path

from app import __version__

# Paths
APP_DIR = Path(__file__).resolve().parent.parent
PACKAGE_DIR = APP_DIR.parent
# EXPENSE_TRACKER_DATA_DIR lets tests (or alternate deployments) use an isolated data folder
DATA_DIR = Path(os.environ.get("EXPENSE_TRACKER_DATA_DIR") or (PACKAGE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# app.db holds the users; each user's movements live in their own users/<id>.db
APP_DB_PATH = DATA_DIR / "app.db"
USERS_DIR = DATA_DIR / "users"
DELETED_USERS_DIR = USERS_DIR / "deleted"
# Single-user database of versions <= 2.0.x, moved to users/<id>.db on first start
LEGACY_DB_PATH = DATA_DIR / "expense_tracker.db"
LOG_PATH = DATA_DIR / "app.log"

APP_NAME = "Expense Tracker"
VERSION = __version__
BASE_CURRENCY = "CLP"


def user_db_path(user_id: int) -> Path:
    return USERS_DIR / f"{int(user_id)}.db"
