"""
Two kinds of SQLite databases:
  - app.db (AppBase): users and app-wide settings.
  - users/<id>.db (Base): one per user with the whole expense schema. Keeping each user in their
    own file isolates their data without having to filter every query by user.
"""
import threading
from pathlib import Path
from typing import Dict

from fastapi import Request
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import APP_DB_PATH, USERS_DIR, user_db_path

Base = declarative_base()
AppBase = declarative_base()


def make_engine(path: Path) -> Engine:
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False, "timeout": 30})

    # Enable WAL mode and foreign keys automatically on connection
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.close()

    return engine


app_engine = make_engine(APP_DB_PATH)
AppSession = sessionmaker(autocommit=False, autoflush=False, bind=app_engine)

_user_engines: Dict[int, Engine] = {}
_user_lock = threading.Lock()


def get_user_engine(user_id: int) -> Engine:
    """Engine of a user's database; the first time it is opened, it is created, migrated and seeded."""
    user_id = int(user_id)
    engine = _user_engines.get(user_id)
    if engine is not None:
        return engine
    with _user_lock:
        engine = _user_engines.get(user_id)
        if engine is None:
            from app.models.schemas import run_migrations, seed_initial_data

            USERS_DIR.mkdir(parents=True, exist_ok=True)
            engine = make_engine(user_db_path(user_id))
            run_migrations(engine)
            with Session(bind=engine, autoflush=False) as db:
                seed_initial_data(db)
            _user_engines[user_id] = engine
        return engine


def user_session(user_id: int) -> Session:
    """New session on a user's database (for background jobs and scripts). Caller closes it."""
    return Session(bind=get_user_engine(user_id), autocommit=False, autoflush=False)


def dispose_user_engine(user_id: int):
    """Closes a user's connections (before moving or deleting their database file)."""
    with _user_lock:
        engine = _user_engines.pop(int(user_id), None)
    if engine is not None:
        engine.dispose()


def get_db(request: Request):
    """Session on the database of the logged-in user (set by the session middleware)."""
    db = user_session(request.state.user.id)
    try:
        yield db
    finally:
        db.close()
