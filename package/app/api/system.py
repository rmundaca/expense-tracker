import logging
import os
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.users import require_admin
from app.core import auth
from app.core.config import APP_DB_PATH, VERSION, user_db_path
from app.core.database import get_db, get_user_engine
from app.i18n import LANGUAGES, all_variants, t
from app.models.dtos import CsvImportRequest, LanguageRequest, ResetDataRequest
from app.models.schemas import Account, Transaction, get_setting, set_setting, transaction_tags
from app.schedulers.tasks import sync_rates_for_user
from app.services.csv_import import import_csv

router = APIRouter(prefix="/api/system", tags=["system"])
logger = logging.getLogger("api.system")


@router.get("/info")
def info():
    return {"version": VERSION}


@router.get("/language")
def get_language(db: Session = Depends(get_db)):
    return {"language": get_setting(db, "language") or None, "available": list(LANGUAGES)}


@router.put("/language")
def set_language(req: LanguageRequest, db: Session = Depends(get_db)):
    """The language chosen in Settings, so background jobs (mail sync, exchange rates) write their messages in it."""
    if req.language not in LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {req.language}")
    set_setting(db, "language", req.language)
    db.commit()
    return {"language": req.language}


def _sqlite_copy(src_path: Path, dst_path: Path):
    """Consistent copy of a live SQLite database (includes WAL contents) using SQLite's online backup API."""
    src, dst = sqlite3.connect(str(src_path)), sqlite3.connect(str(dst_path))
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()


def _temp_file(suffix: str) -> Path:
    fd, name = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return Path(name)


@router.get("/backup")
def download_backup(request: Request, background: BackgroundTasks):
    """Backup of the logged-in user's database only."""
    user = request.state.user
    get_user_engine(user.id)  # makes sure the file exists
    tmp = _temp_file(".db")
    _sqlite_copy(user_db_path(user.id), tmp)
    background.add_task(tmp.unlink)
    name = f"expense_tracker_{user.username}_{datetime.now().strftime('%Y%m%d_%H%M')}.db"
    return FileResponse(str(tmp), filename=name, media_type="application/octet-stream")


@router.get("/backup-all", dependencies=[Depends(require_admin)])
def download_full_backup(background: BackgroundTasks):
    """Administrators: zip with app.db (users) and every user's database, as laid out in the data folder."""
    tmp_zip = _temp_file(".zip")
    with tempfile.TemporaryDirectory() as work, zipfile.ZipFile(tmp_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        sources = [(APP_DB_PATH, APP_DB_PATH.name)]
        for u in auth.list_users():
            get_user_engine(u.id)  # a user who never logged in gets their (seeded) database too
            sources.append((user_db_path(u.id), f"users/{u.id}.db"))
        for i, (src, arcname) in enumerate(sources):
            copy = Path(work) / f"{i}.db"
            _sqlite_copy(src, copy)
            zf.write(copy, arcname)
    background.add_task(tmp_zip.unlink)
    name = f"expense_tracker_full_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
    return FileResponse(str(tmp_zip), filename=name, media_type="application/zip")


@router.post("/import-csv")
def import_csv_endpoint(req: CsvImportRequest, request: Request, background: BackgroundTasks,
                        db: Session = Depends(get_db)):
    if not req.csv_content.strip():
        raise HTTPException(status_code=400, detail=t("system.file_empty"))
    try:
        result = import_csv(db, req.csv_content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if result["estimated_rates"]:
        # Old foreign movements got provisional rates: download their years now instead of tomorrow
        background.add_task(sync_rates_for_user, request.state.user.id)
    return result


@router.post("/reset-data")
def reset_data(req: ResetDataRequest, db: Session = Depends(get_db)):
    """Deletes every movement of the logged-in user and zeroes their balances. Accounts, categories, rules and learning are kept."""
    # The confirmation word of any language is accepted (the page may be open in another one)
    if req.confirm.strip().upper() not in all_variants("system.reset_word"):
        raise HTTPException(status_code=400, detail=t("system.reset_type_word", word=t("system.reset_word")))
    db.execute(transaction_tags.delete())
    deleted = db.query(Transaction).delete(synchronize_session=False)
    db.query(Account).update({Account.opening_balance: 0.0}, synchronize_session=False)
    db.commit()
    logger.warning(f"Data reset: {deleted} transactions deleted")
    return {"deleted": deleted}
