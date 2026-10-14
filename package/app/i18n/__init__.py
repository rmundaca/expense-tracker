"""
Translations of every message the server shows to users (API errors, sync results, default data names).

The language of a request comes from the `lang` cookie the web app sets (the language chosen in
Settings), else from the Accept-Language header. Background jobs have no request: they run with
`use(<the user's stored language>)` so what they save (e.g. the last mail sync result) reads in it too.

Messages are looked up by key in the catalog of the current language, falling back to English. A message
may be a {"one": ..., "other": ...} dict, chosen by the `count` argument.
"""
import contextvars
from contextlib import contextmanager
from typing import List, Optional

from app.i18n import en, es

CATALOGS = {"en": en.MESSAGES, "es": es.MESSAGES}
LANGUAGES = tuple(CATALOGS)
DEFAULT_LANGUAGE = "en"
LANGUAGE_COOKIE = "lang"

_current = contextvars.ContextVar("language", default=DEFAULT_LANGUAGE)


def normalize(value: Optional[str]) -> Optional[str]:
    """'es-CL' -> 'es'; None for languages without a catalog."""
    code = (value or "").strip().lower().replace("_", "-").split("-")[0]
    return code if code in CATALOGS else None


def from_accept_language(header: Optional[str]) -> Optional[str]:
    """First supported language of an Accept-Language header, by preference order."""
    ranked = []
    for i, part in enumerate((header or "").split(",")):
        tag, _, params = part.strip().partition(";")
        try:
            q = float(params.strip()[2:]) if params.strip().startswith("q=") else 1.0
        except ValueError:
            q = 0.0
        ranked.append((-q, i, tag))
    return next((code for _, _, tag in sorted(ranked) if (code := normalize(tag))), None)


def resolve(cookie: Optional[str], accept_language: Optional[str]) -> str:
    return normalize(cookie) or from_accept_language(accept_language) or DEFAULT_LANGUAGE


def current() -> str:
    return _current.get()


def set_current(language: Optional[str]):
    """Sets the language of the running request; returns a token for contextvars' reset."""
    return _current.set(normalize(language) or DEFAULT_LANGUAGE)


@contextmanager
def use(language: Optional[str]):
    """Runs a block (a background job) in a language; unknown or empty means the default."""
    token = set_current(language)
    try:
        yield
    finally:
        _current.reset(token)


def _lookup(language: str, key: str):
    message = CATALOGS[language].get(key)
    if message is None:
        message = CATALOGS[DEFAULT_LANGUAGE].get(key, key)
    return message


def _render(message, kwargs) -> str:
    if isinstance(message, dict):
        message = message["one" if kwargs.get("count") == 1 else "other"]
    return message.format(**kwargs) if kwargs else message


def t(key: str, **kwargs) -> str:
    """The message `key` in the current language, with `kwargs` filled into its {placeholders}."""
    return _render(_lookup(current(), key), kwargs)


def t_in(language: str, key: str, **kwargs) -> str:
    return _render(_lookup(normalize(language) or DEFAULT_LANGUAGE, key), kwargs)


def all_variants(key: str) -> List[str]:
    """The message in every language (to recognize data created in any of them, e.g. default category names)."""
    return list(dict.fromkeys(t_in(language, key) for language in LANGUAGES))
