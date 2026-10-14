from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response

import logging

from app.core import auth
from app.core.app_setup import adopt_legacy_database
from app.i18n import t
from app.models.dtos import AuthChangePasswordRequest, AuthLoginRequest, AuthSetupRequest
from app.schedulers.tasks import sync_rates_for_user

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger("auth")


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _set_session_cookie(response: Response, user: auth.SessionUser):
    response.set_cookie(
        auth.SESSION_COOKIE,
        auth.create_session_token(user),
        max_age=auth.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )


def _check_lockout(ip: str, username: str):
    wait = auth.seconds_locked(ip, username)
    if wait:
        raise HTTPException(status_code=429, detail=t("auth.locked", seconds=wait))


@router.get("/status")
def auth_status(request: Request):
    user = auth.get_session_user(request.cookies.get(auth.SESSION_COOKIE))
    return {
        "configured": auth.is_configured(),
        "authenticated": user is not None,
        "user": user.public() if user else None,
    }


@router.post("/setup")
def auth_setup(data: AuthSetupRequest, response: Response, background: BackgroundTasks):
    """Creates the first user (an administrator) on a fresh install. Disabled once any user exists."""
    if auth.is_configured():
        raise HTTPException(status_code=409, detail=t("auth.already_configured"))
    try:
        user = auth.create_user(data.username, data.password, data.display_name, is_admin=True, only_if_first=True)
    except auth.UserError as e:
        status = 409 if auth.is_configured() else 400
        raise HTTPException(status_code=status, detail=str(e))
    adopt_legacy_database(user.id)  # a single-user install that never had a password
    background.add_task(sync_rates_for_user, user.id)  # the boot-time download ran before this user existed
    _set_session_cookie(response, user)
    logger.info(f"Initial administrator created: {user.username}")
    return {"success": True, "user": user.public()}


@router.post("/login")
def auth_login(data: AuthLoginRequest, request: Request, response: Response):
    ip = _client_ip(request)
    _check_lockout(ip, data.username)
    if not auth.is_configured():
        raise HTTPException(status_code=409, detail=t("auth.not_configured"))
    user = auth.authenticate(data.username, data.password)
    if not user:
        auth.register_failure(ip, data.username)
        logger.warning(f"Failed sign-in from {ip} (user '{auth.normalize_username(data.username)[:32]}')")
        raise HTTPException(status_code=401, detail=t("auth.bad_credentials"))
    auth.register_success(ip, data.username)
    _set_session_cookie(response, user)
    return {"success": True, "user": user.public()}


@router.post("/logout")
def auth_logout(request: Request, response: Response):
    auth.revoke_session(request.cookies.get(auth.SESSION_COOKIE))
    response.delete_cookie(auth.SESSION_COOKIE)
    return {"success": True}


@router.post("/change-password")
def auth_change_password(data: AuthChangePasswordRequest, request: Request, response: Response):
    """Changes the logged-in user's password; their other open sessions are invalidated."""
    user = auth.get_session_user(request.cookies.get(auth.SESSION_COOKIE))
    if not user:
        raise HTTPException(status_code=401, detail=t("common.not_authenticated"))
    ip = _client_ip(request)
    _check_lockout(ip, user.username)
    if not auth.check_password(user.id, data.current_password):
        auth.register_failure(ip, user.username)
        raise HTTPException(status_code=400, detail=t("auth.wrong_current_password"))
    try:
        auth.set_password(user.id, data.new_password)
    except auth.UserError as e:
        raise HTTPException(status_code=400, detail=str(e))
    auth.register_success(ip, user.username)
    _set_session_cookie(response, auth.get_user(user.id))
    logger.info(f"Password changed: {user.username}")
    return {"success": True}
