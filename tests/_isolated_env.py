"""
Points the app at a throwaway data folder BEFORE any `app.*` import, so tests never
touch the real database or classifier model. Import this first in every test module.
"""
import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

if not os.environ.get("EXPENSE_TRACKER_DATA_DIR"):
    _tmp_dir = tempfile.mkdtemp(prefix="expense_tracker_tests_")
    os.environ["EXPENSE_TRACKER_DATA_DIR"] = _tmp_dir
    atexit.register(shutil.rmtree, _tmp_dir, ignore_errors=True)

if "app.core.config" in sys.modules:
    raise RuntimeError("_isolated_env must be imported before any app module")

_PACKAGE_DIR = str(Path(__file__).resolve().parent.parent / "package")
if _PACKAGE_DIR not in sys.path:
    sys.path.insert(0, _PACKAGE_DIR)

TEST_USERNAME = "admin"
TEST_PASSWORD = "test-password"


def reset_users():
    """Removes every user. Ids are never reused, so the next users get brand-new, empty databases."""
    from app.core import auth
    from app.core.database import AppBase, AppSession, app_engine
    from app.models.app_schemas import User

    AppBase.metadata.create_all(bind=app_engine)
    with AppSession() as s:
        s.query(User).delete()
        s.commit()
    auth.reset_cache()


def authenticate(client, username=TEST_USERNAME, password=TEST_PASSWORD):
    """Logs the TestClient in, so it carries that user's session cookie."""
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
