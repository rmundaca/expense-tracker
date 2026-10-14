"""User administration (administrators only). Each user gets their own, fully independent database."""
import logging
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request

from app.core import auth
from app.core.config import DELETED_USERS_DIR, user_db_path
from app.core.database import dispose_user_engine, get_user_engine
from app.i18n import t
from app.models.dtos import UserCreate, UserUpdate
from app.schedulers.tasks import remove_mail_job, reschedule_mail, sync_rates_for_user
from app.services.classifier import classifier_service

logger = logging.getLogger("api.users")


def require_admin(request: Request) -> auth.SessionUser:
    user = request.state.user
    if not user.is_admin:
        raise HTTPException(status_code=403, detail=t("users.admin_only"))
    return user


router = APIRouter(prefix="/api/users", tags=["users"], dependencies=[Depends(require_admin)])


def _get_or_404(user_id: int) -> auth.SessionUser:
    user = auth.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail=t("auth.user_not_found"))
    return user


@router.get("")
def list_users():
    return [u.public() for u in auth.list_users()]


@router.post("")
def create_user(data: UserCreate, background: BackgroundTasks, admin: auth.SessionUser = Depends(require_admin)):
    try:
        user = auth.create_user(data.username, data.password, data.display_name, is_admin=data.is_admin)
    except auth.UserError as e:
        raise HTTPException(status_code=400, detail=str(e))
    get_user_engine(user.id)  # creates and seeds their database now instead of on first login
    reschedule_mail(user.id)
    background.add_task(sync_rates_for_user, user.id)  # exchange rates now, not at the next daily run
    logger.info(f"{admin.username} created user {user.username}")
    return user.public()


@router.patch("/{user_id}")
def update_user(user_id: int, data: UserUpdate, admin: auth.SessionUser = Depends(require_admin)):
    _get_or_404(user_id)
    if user_id == admin.id and (data.is_active is False or data.is_admin is False):
        raise HTTPException(status_code=400, detail=t("users.cannot_demote_self"))
    try:
        user = auth.update_user(user_id, display_name=data.display_name, is_active=data.is_active, is_admin=data.is_admin)
        if data.password:
            auth.set_password(user_id, data.password)
            user = auth.get_user(user_id)
    except auth.UserError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if data.is_active is not None:
        reschedule_mail(user_id)  # removes the job of a deactivated user
    logger.info(f"{admin.username} updated user {user.username}")
    return user.public()


@router.delete("/{user_id}")
def delete_user(user_id: int, confirm: str = Query(""), admin: auth.SessionUser = Depends(require_admin)):
    """
    Deletes a user. Their database is not erased: it is moved to users/deleted/ so an administrator
    can still recover it from the NAS. Requires the username as confirmation.
    """
    user = _get_or_404(user_id)
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail=t("users.cannot_delete_self"))
    if auth.normalize_username(confirm) != user.username:
        raise HTTPException(status_code=400, detail=t("users.type_to_confirm", username=user.username))
    try:
        auth.delete_user(user_id)
    except auth.UserError as e:
        raise HTTPException(status_code=400, detail=str(e))
    remove_mail_job(user_id)
    archived = _archive_user_database(user)
    logger.warning(f"{admin.username} deleted user {user.username} (database archived as: {archived})")
    return {"success": True, "archived_as": archived}


def _archive_user_database(user: auth.SessionUser):
    db_path = user_db_path(user.id)
    classifier_service.forget(f"sqlite:///{db_path}")
    dispose_user_engine(user.id)
    if not db_path.exists():
        return None
    DELETED_USERS_DIR.mkdir(parents=True, exist_ok=True)
    target = DELETED_USERS_DIR / f"{user.id}_{user.username}_{datetime.now().strftime('%Y%m%d%H%M%S')}.db"
    os.replace(db_path, target)
    for suffix in ("-wal", "-shm"):
        side = Path(f"{db_path}{suffix}")
        if side.exists():
            os.replace(side, Path(f"{target}{suffix}"))
    return target.name
