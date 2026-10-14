"""
Encryption of stored credentials (mailbox passwords, OAuth refresh tokens).

The key lives in data/secret.key, outside every database: a downloaded backup (.db or .zip) carries the
credentials encrypted, useless without this NAS's key. Only the standard library is used because the NAS
installs 32-bit dependencies and `cryptography` ships no i686 wheels. The construction is encrypt-then-MAC:
  - keystream: HMAC-SHA256(enc_key, nonce || counter) blocks (HMAC as a PRF in counter mode)
  - tag: HMAC-SHA256(mac_key, version || nonce || ciphertext)
with enc_key and mac_key derived from the master key, and a random 16-byte nonce per value.
"""
import base64
import hashlib
import hmac
import os
import secrets
import threading
from typing import Optional

from app.core.config import DATA_DIR
from app.i18n import t

KEY_PATH = DATA_DIR / "secret.key"
PREFIX = "enc1:"
_NONCE_LEN = 16
_TAG_LEN = 32

_key_lock = threading.Lock()
_master_key: Optional[bytes] = None


class CredentialError(Exception):
    """A stored credential cannot be decrypted (e.g. a database restored on another NAS)."""


def _load_master_key() -> bytes:
    global _master_key
    if _master_key is not None:
        return _master_key
    with _key_lock:
        if _master_key is None:
            if KEY_PATH.exists():
                key = KEY_PATH.read_bytes()
            else:
                key = secrets.token_bytes(32)
                fd = os.open(str(KEY_PATH), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as f:
                    f.write(key)
            if len(key) < 32:
                raise CredentialError(t("crypto.invalid_key", path=KEY_PATH))
            _master_key = key
    return _master_key


def _subkey(label: bytes) -> bytes:
    return hmac.new(_load_master_key(), label, hashlib.sha256).digest()


def _keystream(nonce: bytes, length: int) -> bytes:
    enc_key = _subkey(b"credentials-encryption")
    blocks = (hmac.new(enc_key, nonce + i.to_bytes(8, "big"), hashlib.sha256).digest()
              for i in range((length + 31) // 32))
    return b"".join(blocks)[:length]


def _tag(nonce: bytes, ciphertext: bytes) -> bytes:
    return hmac.new(_subkey(b"credentials-authentication"), PREFIX.encode() + nonce + ciphertext, hashlib.sha256).digest()


def encrypt(plaintext: str) -> str:
    """Encrypted, printable form of a credential ('' stays '')."""
    if not plaintext:
        return ""
    data = plaintext.encode("utf-8")
    nonce = secrets.token_bytes(_NONCE_LEN)
    ciphertext = bytes(a ^ b for a, b in zip(data, _keystream(nonce, len(data))))
    return PREFIX + base64.urlsafe_b64encode(nonce + ciphertext + _tag(nonce, ciphertext)).decode("ascii")


def decrypt(token: str) -> str:
    if not token:
        return ""
    if not token.startswith(PREFIX):
        raise CredentialError(t("crypto.not_encrypted"))
    try:
        raw = base64.urlsafe_b64decode(token[len(PREFIX):].encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        raise CredentialError(t("crypto.damaged"))
    if len(raw) < _NONCE_LEN + _TAG_LEN:
        raise CredentialError(t("crypto.damaged"))
    nonce, ciphertext, tag = raw[:_NONCE_LEN], raw[_NONCE_LEN:-_TAG_LEN], raw[-_TAG_LEN:]
    if not hmac.compare_digest(tag, _tag(nonce, ciphertext)):
        raise CredentialError(t("crypto.wrong_key"))
    return bytes(a ^ b for a, b in zip(ciphertext, _keystream(nonce, len(ciphertext)))).decode("utf-8")
