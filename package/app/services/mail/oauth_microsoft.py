"""
OAuth2 for Outlook.com / Microsoft 365 IMAP, with the device code flow: the NAS shows a code that the user
enters at microsoft.com/devicelogin, so no redirect URL (impossible on a LAN address) is needed.

Each user registers their own app in Azure (Microsoft Entra > App registrations) with "Allow public client
flows" enabled and the delegated permission IMAP.AccessAsUser.All; only its client id is stored here.
Refresh tokens rotate: every refresh returns a new one that must replace the stored one.
"""
from typing import Any, Dict, Tuple

import httpx

from app.i18n import t

AUTHORITY = "https://login.microsoftonline.com"
SCOPE = "https://outlook.office.com/IMAP.AccessAsUser.All offline_access"
DEFAULT_TENANT = "common"
HTTP_TIMEOUT = 20


class OAuthError(Exception):
    pass


def _endpoint(tenant: str, path: str) -> str:
    return f"{AUTHORITY}/{(tenant or DEFAULT_TENANT).strip()}/oauth2/v2.0/{path}"


def _post(url: str, data: Dict[str, str]) -> Tuple[int, Dict[str, Any]]:
    try:
        res = httpx.post(url, data=data, timeout=HTTP_TIMEOUT)
    except httpx.HTTPError as e:
        raise OAuthError(t("oauth.unreachable", error=e))
    try:
        return res.status_code, res.json()
    except ValueError:
        raise OAuthError(t("oauth.unexpected", status=res.status_code))


def _error_text(body: Dict[str, Any]) -> str:
    # error_description carries Microsoft's AADSTS code and explanation (first line only: the rest is trace ids)
    return (body.get("error_description") or body.get("error") or t("oauth.unknown_error")).splitlines()[0]


def start_device_flow(client_id: str, tenant: str) -> Dict[str, Any]:
    """Returns device_code, user_code, verification_uri, expires_in and interval."""
    status, body = _post(_endpoint(tenant, "devicecode"), {"client_id": client_id, "scope": SCOPE})
    if status != 200 or "device_code" not in body:
        raise OAuthError(t("oauth.request_rejected", error=_error_text(body)))
    return body


def poll_device_flow(client_id: str, tenant: str, device_code: str) -> Tuple[str, Dict[str, Any]]:
    """One token request. Status: 'ok' (body has refresh_token), 'pending', 'slow_down', 'expired' or 'denied'."""
    status, body = _post(_endpoint(tenant, "token"), {
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "client_id": client_id,
        "device_code": device_code,
    })
    if status == 200 and body.get("refresh_token"):
        return "ok", body
    error = body.get("error", "")
    if error == "authorization_pending":
        return "pending", body
    if error == "slow_down":
        return "slow_down", body
    if error in ("expired_token", "code_expired"):
        return "expired", body
    if error in ("authorization_declined", "access_denied"):
        return "denied", body
    if status == 200:
        raise OAuthError(t("oauth.no_refresh_token"))
    raise OAuthError(t("oauth.authorization_rejected", error=_error_text(body)))


def refresh_access_token(client_id: str, tenant: str, refresh_token: str) -> Tuple[str, str]:
    """(access token, refresh token to store: Microsoft rotates it on every use)."""
    status, body = _post(_endpoint(tenant, "token"), {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
        "scope": SCOPE,
    })
    if status != 200 or not body.get("access_token"):
        raise OAuthError(t("oauth.authorization_expired", error=_error_text(body)))
    return body["access_token"], body.get("refresh_token") or refresh_token


def xoauth2_string(user: str, access_token: str) -> bytes:
    return f"user={user}\x01auth=Bearer {access_token}\x01\x01".encode()
