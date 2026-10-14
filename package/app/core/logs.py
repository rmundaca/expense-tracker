"""Application logging to a size-capped file in the data folder (replaces the old system_events table)."""
import logging
from logging.handlers import RotatingFileHandler

from app.core.config import LOG_PATH

_configured = False


def setup_logging():
    global _configured
    if _configured:
        return
    handler = RotatingFileHandler(LOG_PATH, maxBytes=512 * 1024, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    _configured = True
