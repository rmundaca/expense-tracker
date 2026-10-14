"""
Per-user password authentication with a signed session cookie.

Users and the cookie signing secret live in the shared app.db (see core/database.py); each user's
expense data lives in their own database. Only an administrator creates users: there is no
public sign-up, except the very first user (an administrator) on a fresh install.
"""
import hashlib
import hmac
import re
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, List, Optional

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.database import AppSession
from app.i18n import t
from app.models.app_schemas import AppSetting, RevokedSession, User
from app.models.schemas import utcnow

SESSION_COOKIE = "et_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days
MIN_PASSWORD_LENGTH = 6
USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,32}$")

PBKDF2_ITERATIONS = 100_000  # Tuned for the NAS Atom CPU (~0.5 s per verification)
MAX_FAILED_ATTEMPTS = 5  # per (ip, username)
MAX_FAILED_ATTEMPTS_PER_IP = 20  # per ip across usernames, so guessing many usernames also locks out
LOCKOUT_SECONDS = 60
FAILURE_WINDOW = 15 * 60  # failures further apart than this do not add up

_SECRET_KEY = "auth_secret_key"

_lock = threading.Lock()
_cache = {"secret": None, "users": None, "revoked": None, "dummy_hash": None}
_attempts_lock = threading.Lock()
# key -> (count, first failure of the window, locked_until); key is (ip, username) or (ip, None)
_failed_attempts = {}


class UserError(ValueError):
    """Invalid user operation; the message is shown to the user."""


@dataclass(frozen=True)
class SessionUser:
    id: int
    username: str
    display_name: str
    is_admin: bool
    is_active: bool
    fingerprint: str  # changes with the password hash, invalidating older sessions

    def public(self) -> dict:
        return {"id": self.id, "username": self.username, "display_name": self.display_name,
                "is_admin": self.is_admin, "is_active": self.is_active}


def _fingerprint(password_hash: str) -> str:
    return hashlib.sha256((password_hash or "").encode("utf-8")).hexdigest()[:16]


def _to_session_user(u: User) -> SessionUser:
    return SessionUser(id=u.id, username=u.username, display_name=u.display_name, is_admin=bool(u.is_admin),
                       is_active=bool(u.is_active), fingerprint=_fingerprint(u.password_hash))


def _load() -> Dict[int, SessionUser]:
    with _lock:
        if _cache["secret"] is not None and _cache["users"] is not None and _cache["revoked"] is not None:
            return _cache["users"]
        with AppSession() as db:
            if _cache["secret"] is None:
                rec = db.query(AppSetting).filter(AppSetting.key == _SECRET_KEY).first()
                if not rec:
                    rec = AppSetting(key=_SECRET_KEY, value=secrets.token_hex(32))
                    db.add(rec)
                    db.commit()
                _cache["secret"] = rec.value
            _cache["users"] = {u.id: _to_session_user(u) for u in db.query(User).all()}
            if _cache["revoked"] is None:
                now = utcnow()
                _cache["revoked"] = {h for (h,) in db.query(RevokedSession.token_hash).filter(RevokedSession.expires_at > now)}
        return _cache["users"]


def _invalidate_users():
    with _lock:
        _cache["users"] = None


def reset_cache():
    """Forces app.db to be re-read (used by tests and after external DB changes)."""
    with _lock:
        _cache.update({"secret": None, "users": None, "revoked": None})
    with _attempts_lock:
        _failed_attempts.clear()


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt, expected = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations))
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, AttributeError):
        return False


def _dummy_verify(password: str):
    """Spends the same time as a real check, so response times do not reveal which usernames exist."""
    if _cache["dummy_hash"] is None:
        _cache["dummy_hash"] = hash_password(secrets.token_hex(8))
    verify_password(password or "", _cache["dummy_hash"])


def validate_password(password: str):
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise UserError(t("auth.password_too_short", min=MIN_PASSWORD_LENGTH))


def normalize_username(username: Optional[str]) -> str:
    return (username or "").strip().lower()


def validate_username(username: str):
    if not USERNAME_RE.match(username):
        raise UserError(t("auth.invalid_username"))


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def is_configured() -> bool:
    return bool(_load())


def list_users() -> List[SessionUser]:
    return sorted(_load().values(), key=lambda u: u.id)


def get_user(user_id: int) -> Optional[SessionUser]:
    return _load().get(user_id)


def find_user(username: str) -> Optional[SessionUser]:
    username = normalize_username(username)
    return next((u for u in _load().values() if u.username == username), None)


def create_user(username: str, password: Optional[str] = None, display_name: Optional[str] = None,
                is_admin: bool = False, password_hash: Optional[str] = None, only_if_first: bool = False) -> SessionUser:
    """
    Creates a user. `password_hash` reuses an existing hash (legacy migration) instead of a password.
    With `only_if_first`, fails if any user already exists (first-run setup cannot take over an install).
    """
    username = normalize_username(username)
    validate_username(username)
    if password_hash is None:
        validate_password(password)
        password_hash = hash_password(password)
    display_name = (display_name or "").strip()[:80] or username
    with _lock, AppSession() as db:
        if only_if_first and db.query(User.id).first():
            raise UserError(t("auth.admin_exists"))
        if db.query(User.id).filter(User.username == username).first():
            raise UserError(t("auth.username_taken"))
        user = User(username=username, display_name=display_name, password_hash=password_hash,
                    is_admin=is_admin, is_active=True)
        db.add(user)
        db.commit()
        result = _to_session_user(user)
        _cache["users"] = None
    return result


def _active_admin_ids(db) -> set:
    return {uid for (uid,) in db.query(User.id).filter(User.is_admin == True, User.is_active == True)}


def update_user(user_id: int, display_name: Optional[str] = None, is_active: Optional[bool] = None,
                is_admin: Optional[bool] = None) -> SessionUser:
    with _lock, AppSession() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise LookupError(t("auth.user_not_found"))
        loses_admin = (is_admin is False or is_active is False) and user.is_admin and user.is_active
        if loses_admin and _active_admin_ids(db) == {user.id}:
            raise UserError(t("auth.last_admin"))
        if display_name is not None:
            if not display_name.strip():
                raise UserError(t("auth.name_empty"))
            user.display_name = display_name.strip()[:80]
        if is_active is not None:
            user.is_active = is_active
        if is_admin is not None:
            user.is_admin = is_admin
        db.commit()
        result = _to_session_user(user)
        _cache["users"] = None
    return result


def delete_user(user_id: int) -> SessionUser:
    """Removes the user from app.db. Archiving their database file is up to the caller."""
    with _lock, AppSession() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise LookupError(t("auth.user_not_found"))
        if user.is_admin and user.is_active and _active_admin_ids(db) == {user.id}:
            raise UserError(t("auth.last_admin"))
        result = _to_session_user(user)
        db.delete(user)
        db.commit()
        _cache["users"] = None
    return result


def set_password(user_id: int, password: str):
    """Sets a new password; every open session of that user is invalidated."""
    validate_password(password)
    new_hash = hash_password(password)
    with AppSession() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise LookupError(t("auth.user_not_found"))
        user.password_hash = new_hash
        db.commit()
    _invalidate_users()


def check_password(user_id: int, password: str) -> bool:
    with AppSession() as db:
        user = db.query(User).filter(User.id == user_id).first()
        stored = user.password_hash if user else None
    if not stored:
        _dummy_verify(password)
        return False
    return verify_password(password or "", stored)


def authenticate(username: str, password: str) -> Optional[SessionUser]:
    """The active user matching these credentials, or None (without revealing which part failed)."""
    user = find_user(username)
    if not user or not user.is_active:
        _dummy_verify(password)
        return None
    return get_user(user.id) if check_password(user.id, password) else None


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def _serializer() -> URLSafeTimedSerializer:
    _load()
    return URLSafeTimedSerializer(_cache["secret"], salt="et-session")


def create_session_token(user: SessionUser) -> str:
    # "n" makes every token unique, so logging out on one device never revokes another device's session
    return _serializer().dumps({"uid": user.id, "pf": user.fingerprint, "n": secrets.token_hex(8)})


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def revoke_session(token: Optional[str]):
    """Logout: this cookie stops working even if it was copied. Expired entries are purged on the way."""
    if not token:
        return
    _load()
    now = utcnow()
    token_hash = _token_hash(token)
    with _lock, AppSession() as db:
        db.query(RevokedSession).filter(RevokedSession.expires_at <= now).delete(synchronize_session=False)
        if not db.query(RevokedSession.token_hash).filter(RevokedSession.token_hash == token_hash).first():
            db.add(RevokedSession(token_hash=token_hash, expires_at=now + timedelta(seconds=SESSION_MAX_AGE)))
        db.commit()
        _cache["revoked"].add(token_hash)


def get_session_user(token: Optional[str]) -> Optional[SessionUser]:
    """The active user a session cookie belongs to, or None if it is invalid, expired or outdated."""
    if not token:
        return None
    try:
        data = _serializer().loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("uid"), int):
        return None
    if _token_hash(token) in _cache["revoked"]:  # logged out (loaded by _serializer -> _load)
        return None
    user = get_user(data["uid"])
    if not user or not user.is_active:
        return None
    # Bound to the password hash: a password change invalidates every older session
    return user if hmac.compare_digest(str(data.get("pf", "")), user.fingerprint) else None


# ---------------------------------------------------------------------------
# Lockout after repeated failures
# ---------------------------------------------------------------------------

def _lock_keys(ip: str, username: str):
    return (((ip, normalize_username(username)), MAX_FAILED_ATTEMPTS), ((ip, None), MAX_FAILED_ATTEMPTS_PER_IP))


def _prune_attempts(now: float):
    """Drops forgotten failures and finished lockouts, so the table cannot grow without bound."""
    for key in [k for k, (_, since, until) in _failed_attempts.items() if until <= now and now - since > FAILURE_WINDOW]:
        del _failed_attempts[key]


def seconds_locked(ip: str, username: str = "") -> int:
    now = time.time()
    with _attempts_lock:
        remaining = max(_failed_attempts.get(key, (0, 0.0, 0.0))[2] - now for key, _ in _lock_keys(ip, username))
    return int(remaining) + 1 if remaining > 0 else 0


def register_failure(ip: str, username: str = ""):
    """Counts a failure; failures older than FAILURE_WINDOW are forgotten, so rare typos never add up to a lockout."""
    now = time.time()
    with _attempts_lock:
        if len(_failed_attempts) > 1000:
            _prune_attempts(now)
        for key, limit in _lock_keys(ip, username):
            count, since, _ = _failed_attempts.get(key, (0, now, 0.0))
            if now - since > FAILURE_WINDOW:
                count, since = 0, now
            count += 1
            _failed_attempts[key] = (0, now, now + LOCKOUT_SECONDS) if count >= limit else (count, since, 0.0)


def register_success(ip: str, username: str = ""):
    # The per-ip counter is kept: logging into one account must not reset guesses against others
    with _attempts_lock:
        _failed_attempts.pop((ip, normalize_username(username)), None)
