"""
Where bank emails come from. Every source yields, for each candidate email, its Message-ID and a loader
for the full message, so the import loop (sync.py) never knows which protocol is behind it.

Sources only read: IMAP folders are opened read-only with BODY.PEEK (nothing is marked as read) and POP3
never sends DELE.
"""
import base64
import email
import imaplib
import logging
import poplib
import re
import ssl
import time
from datetime import datetime, timedelta
from email.header import decode_header
from email.utils import parsedate_to_datetime
from typing import Callable, Iterator, List, Optional, Tuple

from app.services.mail.oauth_microsoft import xoauth2_string

logger = logging.getLogger("mail_sync")

TIMEOUT = 30
# Unread bank emails older than the lookback are still picked up (e.g. after the NAS was off), up to this age
UNSEEN_MAX_DAYS = 60
ENGLISH_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
# Archive folders of Gmail when the server does not flag its "All Mail" folder with \All
GMAIL_ALL_MAIL = ("[Gmail]/Todos", "[Gmail]/All Mail")
# POP3 has no search: headers are read from the newest message backwards until this many in a row are
# older than the lookback (arrival order and Date headers do not always agree), or MAX_SCAN were read
POP3_OLDER_STREAK_STOP = 10
POP3_MAX_SCAN = 2000

Candidate = Tuple[str, Callable[[], bytes]]


def decode_mime_words(s: str) -> str:
    """Decodes MIME encoded-words headers (e.g. =?UTF-8?B?...?=)."""
    if not s:
        return ""
    parts = []
    for fragment, encoding in decode_header(s):
        if isinstance(fragment, bytes):
            try:
                parts.append(fragment.decode(encoding or "utf-8", errors="ignore"))
            except LookupError:
                parts.append(fragment.decode("utf-8", errors="ignore"))
        else:
            parts.append(fragment)
    return "".join(parts)


def _tls_context() -> ssl.SSLContext:
    return ssl.create_default_context()


# ---------------------------------------------------------------------------
# IMAP
# ---------------------------------------------------------------------------

def _imap_since(days: int) -> str:
    since = datetime.now() - timedelta(days=days)
    return f"{since.day:02d}-{ENGLISH_MONTHS[since.month - 1]}-{since.year}"


def _search_message_numbers(mail, senders: List[str], lookback_days: int) -> set:
    since, unseen_since = _imap_since(lookback_days), _imap_since(max(lookback_days, UNSEEN_MAX_DAYS))
    found = set()
    for sender in senders:
        for criteria in (f'(SINCE "{since}" FROM "{sender}")', f'(UNSEEN SINCE "{unseen_since}" FROM "{sender}")'):
            status, data = mail.search(None, criteria)
            if status == "OK" and data and data[0]:
                found.update(data[0].split())
    return found


def imap_utf7(name: str) -> str:
    """Folder name in IMAP's modified UTF-7 (RFC 3501), e.g. 'Notificación' -> 'Notificaci&APM-n'."""
    out, pending = [], []

    def flush():
        if pending:
            encoded = base64.b64encode("".join(pending).encode("utf-16-be")).decode("ascii")
            out.append("&" + encoded.rstrip("=").replace("/", ",") + "-")
            pending.clear()

    for ch in name:
        if 0x20 <= ord(ch) <= 0x7E:
            flush()
            out.append("&-" if ch == "&" else ch)
        else:
            pending.append(ch)
    flush()
    return "".join(out)


def quote_mailbox(name: str) -> str:
    return '"' + imap_utf7(name).replace("\\", "\\\\").replace('"', '\\"') + '"'


_LIST_LINE = re.compile(rb'^\((?P<flags>[^)]*)\)\s+(?:"(?:[^"\\]|\\.)*"|NIL)\s+(?P<name>.+)$')


def find_all_mail_folder(list_lines) -> Optional[str]:
    """Quoted name of the folder flagged \\All (RFC 6154) in a LIST response, as sent back to SELECT."""
    for line in list_lines or []:
        if not isinstance(line, bytes):
            continue
        m = _LIST_LINE.match(line)
        if m and b"\\all" in m.group("flags").lower().split():
            name = m.group("name").strip().decode("ascii", errors="ignore")
            return name if name.startswith('"') else f'"{name}"'
    return None


def _connect_imap(host: str, port: int, security: str, timeout: int):
    if security == "starttls":
        mail = imaplib.IMAP4(host, port, timeout=timeout)
        mail.starttls(_tls_context())
        return mail
    return imaplib.IMAP4_SSL(host, port, ssl_context=_tls_context(), timeout=timeout)


class ImapSource:
    def __init__(self, host: str, port: int, security: str, user: str, password: str = "",
                 access_token: str = "", folders: Optional[List[str]] = None, timeout: int = TIMEOUT):
        self.host, self.port, self.security = host, port, security
        self.user, self.password, self.access_token = user, password, access_token
        self.folders = [f for f in (folders or []) if f.strip()]
        self.timeout = timeout
        self.found = 0  # candidate emails seen by the last candidates() run
        self.mail = None

    def __enter__(self):
        self.mail = _connect_imap(self.host, self.port, self.security, self.timeout)
        try:
            if self.access_token:
                self.mail.authenticate("XOAUTH2", lambda _: xoauth2_string(self.user, self.access_token))
            else:
                self.mail.login(self.user, self.password)
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *exc):
        if self.mail is not None:
            try:
                self.mail.logout()
            except Exception:
                pass
            self.mail = None

    def _select(self, quoted_box: str) -> bool:
        return self.mail.select(quoted_box, readonly=True)[0] == "OK"

    def _all_mail_folder(self) -> Optional[str]:
        status, data = self.mail.list()
        box = find_all_mail_folder(data) if status == "OK" else None
        if box:
            return box
        return next((quote_mailbox(name) for name in GMAIL_ALL_MAIL if self._select(quote_mailbox(name))), None)

    def candidates(self, senders: List[str], lookback_days: int) -> Iterator[Candidate]:
        self.found = 0
        if self.folders:
            boxes = [quote_mailbox(f) for f in self.folders]
        else:
            boxes = ["INBOX"]
        for box in boxes:
            if not self._select(box):
                logger.warning(f"IMAP folder not found in {self.user}: {box}")
                continue
            numbers = _search_message_numbers(self.mail, senders, lookback_days)
            if not numbers and not self.folders:
                # Bank emails may be auto-archived by a filter: look in the "All Mail" folder
                archive = self._all_mail_folder()
                if archive and self._select(archive):
                    numbers = _search_message_numbers(self.mail, senders, lookback_days)
            yield from self._fetch(numbers)

    def _fetch(self, numbers) -> Iterator[Candidate]:
        # Message numbers belong to the selected folder: each loader runs before the next folder is selected
        for num in sorted(numbers, key=int):
            self.found += 1
            status, header_data = self.mail.fetch(num, "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])")
            if status != "OK" or not header_data or not isinstance(header_data[0], tuple):
                continue
            msg_id = email.message_from_bytes(header_data[0][1]).get("Message-ID", "").strip()
            if msg_id:
                yield msg_id, (lambda n=num: self._load(n))

    def _load(self, num) -> bytes:
        status, body_data = self.mail.fetch(num, "(BODY.PEEK[])")
        if status != "OK" or not body_data or not isinstance(body_data[0], tuple):
            return b""
        return body_data[0][1]


# ---------------------------------------------------------------------------
# POP3
# ---------------------------------------------------------------------------

def _connect_pop3(host: str, port: int, security: str, timeout: int):
    if security == "starttls":
        mail = poplib.POP3(host, port, timeout=timeout)
        mail.stls(_tls_context())
        return mail
    return poplib.POP3_SSL(host, port, context=_tls_context(), timeout=timeout)


def _timestamp(date_header: str) -> Optional[float]:
    try:
        dt = parsedate_to_datetime(date_header)
    except (TypeError, ValueError):
        return None
    return dt.timestamp() if dt else None


class Pop3Source:
    """POP3 only sees the inbox, cannot search on the server and has no read/unread state."""

    def __init__(self, host: str, port: int, security: str, user: str, password: str, timeout: int = TIMEOUT):
        self.host, self.port, self.security = host, port, security
        self.user, self.password = user, password
        self.timeout = timeout
        self.found = 0
        self.mail = None

    def __enter__(self):
        self.mail = _connect_pop3(self.host, self.port, self.security, self.timeout)
        try:
            self.mail.user(self.user)
            self.mail.pass_(self.password)
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *exc):
        if self.mail is not None:
            try:
                self.mail.quit()  # nothing was marked for deletion: QUIT deletes nothing
            except Exception:
                pass
            self.mail = None

    def candidates(self, senders: List[str], lookback_days: int) -> Iterator[Candidate]:
        self.found = 0
        count = self.mail.stat()[0]
        cutoff = time.time() - lookback_days * 86400
        older_streak = 0
        for num in range(count, max(0, count - POP3_MAX_SCAN), -1):
            headers = email.message_from_bytes(b"\r\n".join(self.mail.top(num, 0)[1]))
            sent = _timestamp(headers.get("Date", ""))
            if sent is not None and sent < cutoff:
                older_streak += 1
                if older_streak >= POP3_OLDER_STREAK_STOP:
                    break
                continue
            older_streak = 0
            sender = decode_mime_words(headers.get("From", "")).lower()
            if not any(addr in sender for addr in senders):
                continue
            self.found += 1
            msg_id = (headers.get("Message-ID") or "").strip()
            if msg_id:
                yield msg_id, (lambda n=num: b"\r\n".join(self.mail.retr(n)[1]))
