import email
import imaplib
import logging
import poplib
import socket
import ssl
import threading
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.crypto import CredentialError, decrypt, encrypt
from app.i18n import t
from app.models.schemas import (
    Account, BankProfile, Category, IgnoredEmail, MailAccount, Transaction, get_setting, set_setting
)
from app.services.bank_parsers.registry import parser_registry
from app.services.classifier import classifier_service, database_key
from app.services.exchange_rates import normalize_currency, resolve_rate
from app.services.mail import oauth_microsoft
from app.services.mail.providers import protocol_of, uses_oauth
from app.services.mail.sources import UNSEEN_MAX_DAYS, ImapSource, Pop3Source, decode_mime_words

logger = logging.getLogger("mail_sync")

# The scheduler thread and a manual "sync now" must never import the same emails concurrently.
# One lock per user database: different users sync independently.
_sync_locks: Dict[str, threading.Lock] = {}
_sync_locks_guard = threading.Lock()


class MailboxError(Exception):
    """A mailbox could not be read; the message is meant for the user."""


def _sync_lock_for(db: Session) -> threading.Lock:
    key = database_key(db)
    with _sync_locks_guard:
        return _sync_locks.setdefault(key, threading.Lock())


def extract_email_body(msg) -> tuple:
    """Returns (text/plain, text/html) payloads of an email.message object."""
    body_text, body_html = "", ""
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        if part.is_multipart() or "attachment" in str(part.get("Content-Disposition") or ""):
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        try:
            decoded = payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
        except LookupError:
            decoded = payload.decode("utf-8", errors="ignore")
        if part.get_content_type() == "text/html":
            body_html = body_html or decoded
        else:
            body_text = body_text or decoded
    return body_text, body_html


def email_local_datetime(header_value: str) -> Optional[str]:
    """Email 'Date' header converted to local time, as 'YYYY-MM-DD HH:MM:SS'."""
    try:
        dt = parsedate_to_datetime(header_value)
    except (TypeError, ValueError):
        return None
    if dt is None:
        return None
    if dt.tzinfo:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def find_bank_for_sender(sender: str, banks: List[BankProfile]) -> Optional[BankProfile]:
    sender_l = sender.lower()
    return next((b for b in banks if any(addr in sender_l for addr in b.sender_list)), None)


def resolve_account(accounts: List[Account], currency: str, account_hint: Optional[str],
                    bank: Optional[BankProfile]) -> Optional[int]:
    """Picks the account for an imported movement: same currency first, then product type, then bank default."""
    same_currency = [a for a in accounts if normalize_currency(a.currency) == currency]
    hint_types = {
        "credito": ("credito", "credit"),
        "corriente": ("corriente", "checking"),
        "vista": ("vista", "sight"),
    }.get(account_hint or "", ())
    bank_default = bank.default_account_id if bank else None

    # Prefer the bank's default account when it fits both currency and product type
    for acc in same_currency:
        if acc.id == bank_default and (not hint_types or acc.type in hint_types):
            return acc.id
    for acc in same_currency:
        if acc.type in hint_types:
            return acc.id
    for acc in same_currency:
        if acc.id == bank_default:
            return acc.id
    if same_currency:
        return same_currency[0].id
    # No account in that currency: the bank default (balances convert currencies), else the first account
    if bank_default and any(a.id == bank_default for a in accounts):
        return bank_default
    return accounts[0].id if accounts else None


def _same_operation(db: Session, reference: Optional[str]) -> Optional[int]:
    """Id of the movement already imported for this bank operation (e.g. the sender's notice of a transfer
    whose recipient notice just arrived). Emails imported before references were stored only have it in raw_text."""
    if not reference:
        return None
    row = db.query(Transaction.id).filter(Transaction.bank_reference == reference).first() or \
        db.query(Transaction.id).filter(Transaction.bank_reference.is_(None), Transaction.source == "email",
                                        Transaction.raw_text.contains(reference)).first()
    return row[0] if row else None


# ---------------------------------------------------------------------------
# Opening a mailbox
# ---------------------------------------------------------------------------

def folder_list(text: str) -> List[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def open_source(db: Optional[Session], acc: MailAccount):
    """Source for a mailbox (still to be entered with `with`). For outlook the stored refresh token is
    exchanged for an access token, and the rotated refresh token is saved (needs db; None skips saving)."""
    try:
        secret = decrypt(acc.secret)
    except CredentialError as e:
        raise MailboxError(t("mail.credential_error", error=e))
    if not secret:
        raise MailboxError(t("mail.connect_microsoft") if uses_oauth(acc.provider) else t("mail.missing_password"))
    if protocol_of(acc.provider) == "pop3":
        return Pop3Source(acc.host, acc.port, acc.security, acc.email, secret)
    if not uses_oauth(acc.provider):
        return ImapSource(acc.host, acc.port, acc.security, acc.email, password=secret, folders=folder_list(acc.folders))
    try:
        access_token, new_refresh = oauth_microsoft.refresh_access_token(acc.oauth_client_id, acc.oauth_tenant, secret)
    except oauth_microsoft.OAuthError as e:
        raise MailboxError(str(e))
    if db is not None and new_refresh != secret:
        acc.secret = encrypt(new_refresh)
        db.commit()
    return ImapSource(acc.host, acc.port, acc.security, acc.email, access_token=access_token, folders=folder_list(acc.folders))


def connection_error_message(acc: MailAccount, e: Exception) -> str:
    if isinstance(e, MailboxError):
        return str(e)
    if isinstance(e, (imaplib.IMAP4.error, poplib.error_proto)):
        hint = t(f"mail.hint.{acc.provider}" if acc.provider in ("gmail", "outlook") else "mail.hint.default")
        return t("mail.server_rejected", error=e, hint=hint)
    if isinstance(e, ssl.SSLError):
        return t("mail.tls_error", host=acc.host, port=acc.port, error=e)
    if isinstance(e, socket.gaierror):
        return t("mail.host_not_found", host=acc.host)
    if isinstance(e, OSError):
        return t("mail.cannot_connect", host=acc.host, port=acc.port, error=e)
    return t("mail.read_error", error=e)


def test_mailbox(acc: MailAccount) -> Dict[str, Any]:
    """Connects and logs in without importing (the account may be unsaved: rotated tokens are not stored)."""
    try:
        with open_source(None, acc):
            pass
    except Exception as e:
        return {"success": False, "message": connection_error_message(acc, e)}
    return {"success": True, "message": t("mail.test_ok", email=acc.email)}


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def sync_mail_now(db: Session, account_id: Optional[int] = None) -> Dict[str, Any]:
    """Imports from every enabled mailbox (or only `account_id`)."""
    lock = _sync_lock_for(db)
    if not lock.acquire(blocking=False):
        return {"success": False, "message": t("mail.already_running")}
    try:
        result = _sync(db, account_id)
    finally:
        lock.release()
    set_setting(db, "mail_last_result", result["message"])
    if result["success"]:
        set_setting(db, "mail_last_sync", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    db.commit()
    return result


def _sync(db: Session, account_id: Optional[int]) -> Dict[str, Any]:
    q = db.query(MailAccount)
    q = q.filter(MailAccount.id == account_id) if account_id else q.filter(MailAccount.is_enabled == True)
    mailboxes = q.order_by(MailAccount.id).all()
    if not mailboxes:
        return {"success": False, "message": t("mail.add_mailbox") if not account_id else t("mail.not_found")}

    banks = db.query(BankProfile).filter(BankProfile.is_enabled == True).all()
    senders = sorted({addr for b in banks for addr in b.sender_list})
    if not senders:
        return {"success": False, "message": t("mail.no_banks")}
    accounts = db.query(Account).filter(Account.is_active == True).order_by(Account.id).all()
    if not accounts:
        return {"success": False, "message": t("mail.create_account_first")}

    ctx = _ImportContext(db, banks, accounts)
    lookback_days = int(get_setting(db, "mail_lookback_days", "7") or 7)
    imported = found = 0
    errors = []
    for acc in mailboxes:
        res = _sync_mailbox(ctx, acc, senders, lookback_days)
        acc.last_result = res["message"]
        if res["success"]:
            acc.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            imported += res["imported"]
            found += res["found"]
        else:
            errors.append(f"{acc.name}: {res['message']}")
        db.commit()

    message = _result_message(imported, found)
    if errors:
        message += t("mail.with_errors", errors=" · ".join(errors))
    logger.info(f"Mail sync: {imported} new transaction(s) from {found} email(s), {len(errors)} mailbox error(s)")
    # Partial success counts as success: the mailboxes that answered were imported
    return {"success": len(errors) < len(mailboxes), "message": message, "new_transactions": imported}


def _result_message(imported: int, found: int) -> str:
    return t("mail.result", transactions=t("mail.new_transactions", count=imported), emails=t("mail.emails_checked", count=found))


def _pop3_lookback(acc: MailAccount, lookback_days: int) -> int:
    """POP3 has no unread flag to catch up after the NAS was off: reach back to the last successful sync."""
    if not acc.last_sync:
        return lookback_days
    try:
        days_off = (datetime.now() - datetime.strptime(acc.last_sync, "%Y-%m-%d %H:%M:%S")).days + 1
    except ValueError:
        return lookback_days
    return max(lookback_days, min(days_off, UNSEEN_MAX_DAYS))


def _sync_mailbox(ctx: "_ImportContext", acc: MailAccount, senders: List[str], lookback_days: int) -> Dict[str, Any]:
    db = ctx.db
    if protocol_of(acc.provider) == "pop3":
        lookback_days = _pop3_lookback(acc, lookback_days)
    imported = 0
    source = None
    try:
        source = open_source(db, acc)
        with source:
            seen_ids = set()
            for msg_id, load in source.candidates(senders, lookback_days):
                if msg_id in seen_ids:
                    continue
                seen_ids.add(msg_id)
                if db.query(Transaction.id).filter(Transaction.email_message_id == msg_id).first() or \
                        db.query(IgnoredEmail.id).filter(IgnoredEmail.email_message_id == msg_id).first():
                    continue
                raw = load()
                if raw and ctx.import_message(msg_id, raw):
                    imported += 1
    except Exception as e:
        db.rollback()
        if isinstance(e, (MailboxError, imaplib.IMAP4.error, poplib.error_proto, OSError)):
            logger.warning(f"Error reading mailbox '{acc.name}': {e}")
        else:
            logger.exception(f"Error reading mailbox '{acc.name}'")
        return {"success": False, "message": connection_error_message(acc, e)}
    found = source.found
    return {"success": True, "imported": imported, "found": found,
            "message": _result_message(imported, found)}


class _ImportContext:
    """Reference data shared by every mailbox of one sync."""

    def __init__(self, db: Session, banks: List[BankProfile], accounts: List[Account]):
        self.db = db
        self.banks = banks
        self.accounts = accounts
        self.category_types = {c.id: c.type for c in db.query(Category).all()}

    def _ignore(self, msg_id: str, subject: str, sender: str, reason: str):
        self.db.add(IgnoredEmail(email_message_id=msg_id, subject=subject[:250], sender=sender[:250], reason=reason))
        self.db.commit()

    def import_message(self, msg_id: str, raw: bytes) -> bool:
        """Creates the pending movement of one bank email. False when the email is skipped."""
        db, accounts = self.db, self.accounts
        msg = email.message_from_bytes(raw)
        subject = decode_mime_words(msg.get("Subject", ""))
        sender = decode_mime_words(msg.get("From", ""))

        # IMAP FROM is a substring match: only accept explicitly declared bank addresses
        bank = find_bank_for_sender(sender, self.banks)
        if not bank:
            return False

        body_text, body_html = extract_email_body(msg)
        parsed = parser_registry.parse_email(sender, subject, body_text, body_html,
                                             fallback_date=email_local_datetime(msg.get("Date", "")))
        if not parsed or parsed.amount <= 0:
            self._ignore(msg_id, subject, sender, "unparseable")
            logger.info(f"Unparseable email ignored: '{subject[:60]}' from {sender[:50]}")
            return False

        duplicate = _same_operation(db, parsed.reference)
        if duplicate:
            self._ignore(msg_id, subject, sender, "duplicate")
            logger.info(f"Email of an operation already recorded (transaction {duplicate}) ignored: '{subject[:60]}'")
            return False

        currency = normalize_currency(parsed.currency)
        account_id = resolve_account(accounts, currency, parsed.account_hint, bank)
        suggestion = classifier_service.classify(db, merchant=parsed.merchant, description=parsed.description, sender=sender)

        # A learned/rule account only wins when it holds the same currency as the movement
        if suggestion.account_id:
            suggested = next((a for a in accounts if a.id == suggestion.account_id), None)
            if suggested and normalize_currency(suggested.currency) == currency:
                account_id = suggested.id

        tx_type = parsed.tx_type
        if suggestion.source != "none":
            tx_type = suggestion.tx_type
        if tx_type != "transfer" and suggestion.category_id:
            tx_type = self.category_types.get(suggestion.category_id, tx_type)

        if currency != "CLP" and parsed.clp_amount:
            # The bank said what it charged in pesos: its own rate, not the official one
            rate, rate_estimated = round(parsed.clp_amount / parsed.amount, 6), False
        else:
            rate, rate_estimated = resolve_rate(db, currency, parsed.date)
        db.add(Transaction(
            account_id=account_id,
            destination_account_id=suggestion.destination_account_id if tx_type == "transfer" else None,
            category_id=suggestion.category_id if tx_type != "transfer" else None,
            type=tx_type,
            amount=parsed.amount,
            currency=currency,
            exchange_rate=rate,
            rate_estimated=rate_estimated,
            base_amount=round(parsed.amount * rate, 2),
            base_currency="CLP",
            date=parsed.date,
            merchant=(parsed.merchant or "")[:150],
            description=parsed.description,
            raw_text=f"{t('mail.raw_header', sender=sender, subject=subject)}\n\n{parsed.raw_text}",
            source="email",
            email_message_id=msg_id,
            bank_reference=parsed.reference,
            status="pending_review",
            ai_confidence=suggestion.confidence,
            ai_source=suggestion.source,
        ))
        db.commit()
        return True

