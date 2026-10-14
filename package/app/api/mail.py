import threading
import time
from typing import Dict, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.crypto import encrypt
from app.core.database import get_db
from app.i18n import t
from app.models.dtos import MailAccountIn, MailSettingsUpdate, MailTestRequest
from app.models.schemas import MailAccount, get_setting, set_setting
from app.schedulers.tasks import MIN_MAIL_INTERVAL, next_mail_run, reschedule_mail
from app.services.mail import oauth_microsoft
from app.services.mail.providers import (
    DEFAULT_PORTS, PRESETS, PROVIDERS, SECURITY_MODES, has_fixed_server, preset_label, protocol_of, uses_oauth
)
from app.services.mail.sync import folder_list, sync_mail_now, test_mailbox

router = APIRouter(prefix="/api/mail", tags=["mail"])

# Device code logins waiting for the user to approve them at microsoft.com/devicelogin
_pending_oauth: Dict[Tuple[int, int], dict] = {}
_pending_guard = threading.Lock()


def settings_out(db: Session, user_id: int) -> dict:
    return {
        "sync_enabled": get_setting(db, "mail_sync_enabled", "false").lower() == "true",
        "interval_mins": int(get_setting(db, "mail_sync_interval_mins", "30") or 30),
        "lookback_days": int(get_setting(db, "mail_lookback_days", "7") or 7),
        "last_sync": get_setting(db, "mail_last_sync") or None,
        "last_result": get_setting(db, "mail_last_result") or None,
        "next_run": next_mail_run(user_id),
    }


def account_out(acc: MailAccount) -> dict:
    return {
        "id": acc.id,
        "name": acc.name,
        "provider": acc.provider,
        "provider_label": preset_label(acc.provider),
        "email": acc.email,
        "host": acc.host,
        "port": acc.port,
        "security": acc.security,
        "folders": folder_list(acc.folders),
        "has_secret": bool(acc.secret),
        "oauth_client_id": acc.oauth_client_id,
        "oauth_tenant": acc.oauth_tenant,
        "is_enabled": bool(acc.is_enabled),
        "last_sync": acc.last_sync,
        "last_result": acc.last_result,
    }


def _get_or_404(db: Session, account_id: int) -> MailAccount:
    acc = db.query(MailAccount).filter(MailAccount.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail=t("mail.not_found"))
    return acc


def _apply(acc: MailAccount, data: MailAccountIn):
    """Validates and copies the form onto a mailbox (new, stored or a throwaway copy for testing)."""
    provider = (data.provider or acc.provider or "").strip().lower()
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=t("mail.invalid_provider"))
    old_login = (acc.provider, acc.email, acc.host, acc.oauth_client_id, acc.oauth_tenant)

    acc.provider = provider
    if data.name is not None:
        acc.name = data.name.strip()[:100]
    if data.email is not None:
        acc.email = data.email.strip()[:255]
    if has_fixed_server(provider):
        preset = PRESETS[provider]
        acc.host, acc.port, acc.security = preset["host"], preset["port"], preset["security"]
    else:
        if data.host is not None:
            acc.host = data.host.strip()[:255]
        if data.security is not None:
            acc.security = data.security
        if data.port is not None:
            acc.port = data.port
        acc.security = acc.security or "ssl"
        acc.port = acc.port or DEFAULT_PORTS.get((protocol_of(provider), acc.security))
    if protocol_of(provider) != "imap":
        acc.folders = ""
    elif data.folders is not None:
        acc.folders = "\n".join(f.strip() for f in data.folders if f.strip())
    if uses_oauth(provider):
        if data.oauth_client_id is not None:
            acc.oauth_client_id = data.oauth_client_id.strip()[:100] or None
        if data.oauth_tenant is not None:
            acc.oauth_tenant = data.oauth_tenant.strip()[:100] or None
        acc.oauth_tenant = acc.oauth_tenant or oauth_microsoft.DEFAULT_TENANT
    else:
        acc.oauth_client_id = acc.oauth_tenant = None
    if data.is_enabled is not None:
        acc.is_enabled = data.is_enabled

    if not acc.name:
        raise HTTPException(status_code=400, detail=t("mail.name_required"))
    if not acc.email:
        raise HTTPException(status_code=400, detail=t("mail.user_required"))
    if has_fixed_server(provider) and "@" not in acc.email:
        raise HTTPException(status_code=400, detail=t("mail.full_address"))
    if not acc.host:
        raise HTTPException(status_code=400, detail=t("mail.host_required"))
    if acc.security not in SECURITY_MODES:
        raise HTTPException(status_code=400, detail=t("mail.invalid_security"))
    if not acc.port or not 0 < acc.port < 65536:
        raise HTTPException(status_code=400, detail=t("mail.invalid_port"))
    if uses_oauth(provider) and not acc.oauth_client_id:
        raise HTTPException(status_code=400, detail=t("mail.client_id_required"))

    # A token belongs to one login, and a stored password is never sent to a server other than the one it
    # was typed for (otherwise editing the host would hand it to any server): changing them discards it
    if acc.secret:
        if uses_oauth(provider):
            changed = (acc.provider, acc.email, acc.oauth_client_id, acc.oauth_tenant) != \
                (old_login[0], old_login[1], old_login[3], old_login[4])
        else:
            changed = (acc.provider, acc.host) != (old_login[0], old_login[2])
        if changed:
            acc.secret = ""
    if data.password and not uses_oauth(provider):
        password = data.password.replace(" ", "") if provider == "gmail" else data.password
        acc.secret = encrypt(password)


@router.get("/providers")
def providers():
    return {"providers": [{"code": code, **PRESETS[code], "label": preset_label(code)} for code in PROVIDERS], "default_ports": [
        {"protocol": proto, "security": sec, "port": port} for (proto, sec), port in DEFAULT_PORTS.items()]}


@router.get("/settings")
def get_settings(request: Request, db: Session = Depends(get_db)):
    return settings_out(db, request.state.user.id)


@router.put("/settings")
def update_settings(data: MailSettingsUpdate, request: Request, db: Session = Depends(get_db)):
    if data.sync_enabled is not None:
        set_setting(db, "mail_sync_enabled", "true" if data.sync_enabled else "false")
    if data.interval_mins is not None:
        if data.interval_mins < MIN_MAIL_INTERVAL:
            raise HTTPException(status_code=400, detail=t("mail.min_interval", minutes=MIN_MAIL_INTERVAL))
        set_setting(db, "mail_sync_interval_mins", data.interval_mins)
    if data.lookback_days is not None:
        set_setting(db, "mail_lookback_days", max(1, min(data.lookback_days, 60)))
    db.commit()
    if data.interval_mins is not None:
        reschedule_mail(request.state.user.id)
    return settings_out(db, request.state.user.id)


@router.get("/accounts")
def list_accounts(db: Session = Depends(get_db)):
    return [account_out(a) for a in db.query(MailAccount).order_by(MailAccount.id).all()]


@router.post("/accounts")
def create_account(data: MailAccountIn, db: Session = Depends(get_db)):
    acc = MailAccount(name="", email="", host="", port=0, security="", folders="", secret="", is_enabled=True)
    _apply(acc, data)
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return account_out(acc)


@router.put("/accounts/{account_id}")
def update_account(account_id: int, data: MailAccountIn, db: Session = Depends(get_db)):
    acc = _get_or_404(db, account_id)
    _apply(acc, data)
    db.commit()
    db.refresh(acc)
    return account_out(acc)


@router.delete("/accounts/{account_id}")
def delete_account(account_id: int, request: Request, db: Session = Depends(get_db)):
    db.delete(_get_or_404(db, account_id))
    db.commit()
    with _pending_guard:
        _pending_oauth.pop((request.state.user.id, account_id), None)
    return {"deleted": True}


@router.post("/test")
def test(data: MailTestRequest, db: Session = Depends(get_db)):
    """Tests the form as typed; for a stored mailbox, the fields left out keep their stored values."""
    probe = MailAccount(name="test", email="", host="", port=0, security="", folders="", secret="")
    if data.account_id:
        stored = _get_or_404(db, data.account_id)
        for col in MailAccount.__table__.columns.keys():
            if col != "id":
                setattr(probe, col, getattr(stored, col))
    _apply(probe, data)
    return test_mailbox(probe)


@router.post("/accounts/{account_id}/oauth/start")
def oauth_start(account_id: int, request: Request, db: Session = Depends(get_db)):
    acc = _get_or_404(db, account_id)
    if not uses_oauth(acc.provider):
        raise HTTPException(status_code=400, detail=t("mail.uses_password"))
    try:
        flow = oauth_microsoft.start_device_flow(acc.oauth_client_id, acc.oauth_tenant)
    except oauth_microsoft.OAuthError as e:
        raise HTTPException(status_code=502, detail=str(e))
    with _pending_guard:
        _pending_oauth[(request.state.user.id, account_id)] = {
            "device_code": flow["device_code"],
            "client_id": acc.oauth_client_id,
            "tenant": acc.oauth_tenant,
            "expires_at": time.time() + int(flow.get("expires_in", 900)),
        }
    return {
        "user_code": flow["user_code"],
        "verification_uri": flow.get("verification_uri") or "https://microsoft.com/devicelogin",
        "interval": int(flow.get("interval", 5)),
        "expires_in": int(flow.get("expires_in", 900)),
    }


@router.post("/accounts/{account_id}/oauth/poll")
def oauth_poll(account_id: int, request: Request, db: Session = Depends(get_db)):
    """One check of a pending Microsoft login. status: pending, slow_down, ok, expired or denied."""
    acc = _get_or_404(db, account_id)
    key = (request.state.user.id, account_id)
    with _pending_guard:
        flow: Optional[dict] = _pending_oauth.get(key)
    if not flow or flow["expires_at"] < time.time():
        with _pending_guard:
            _pending_oauth.pop(key, None)
        return {"status": "expired", "message": t("mail.code_expired")}
    try:
        status, body = oauth_microsoft.poll_device_flow(flow["client_id"], flow["tenant"], flow["device_code"])
    except oauth_microsoft.OAuthError as e:
        with _pending_guard:
            _pending_oauth.pop(key, None)
        raise HTTPException(status_code=502, detail=str(e))
    if status in ("pending", "slow_down"):
        return {"status": status}
    with _pending_guard:
        _pending_oauth.pop(key, None)
    if status == "ok":
        acc.secret = encrypt(body["refresh_token"])
        db.commit()
        return {"status": "ok", "message": t("mail.connected")}
    return {"status": status, "message": t("mail.code_expired") if status == "expired" else t("mail.denied")}


@router.post("/sync")
def sync_now(account_id: Optional[int] = None, db: Session = Depends(get_db)):
    return sync_mail_now(db, account_id)
