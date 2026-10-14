"""Kinds of mailbox. gmail and outlook fix their server; imap and pop3 take whatever the user types."""
from app.i18n import t

PROVIDERS = ("gmail", "outlook", "imap", "pop3")
SECURITY_MODES = ("ssl", "starttls")

PRESETS = {
    "gmail": {"label": "Gmail", "protocol": "imap", "auth": "password", "host": "imap.gmail.com", "port": 993, "security": "ssl"},
    # Microsoft turned off password logins for IMAP: OAuth2 (device code) with the user's own Azure app
    "outlook": {"label": "Outlook / Microsoft 365", "protocol": "imap", "auth": "oauth", "host": "outlook.office365.com",
                "port": 993, "security": "ssl"},
    "imap": {"label": "Other IMAP server", "protocol": "imap", "auth": "password", "host": "", "port": 993, "security": "ssl"},
    "pop3": {"label": "POP3 server", "protocol": "pop3", "auth": "password", "host": "", "port": 995, "security": "ssl"},
}

DEFAULT_PORTS = {("imap", "ssl"): 993, ("imap", "starttls"): 143, ("pop3", "ssl"): 995, ("pop3", "starttls"): 110}


def preset_label(provider: str) -> str:
    """Name shown for a kind of mailbox; the generic ones are translated."""
    if provider in ("imap", "pop3"):
        return t(f"mail.provider.{provider}")
    return PRESETS.get(provider, {}).get("label", provider)


def protocol_of(provider: str) -> str:
    return PRESETS[provider]["protocol"]


def uses_oauth(provider: str) -> bool:
    return PRESETS[provider]["auth"] == "oauth"


def has_fixed_server(provider: str) -> bool:
    return provider in ("gmail", "outlook")
