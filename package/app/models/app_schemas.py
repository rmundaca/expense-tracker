"""Tables of the shared app.db: users and app-wide settings (never expense data)."""
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.core.database import AppBase
from app.models.schemas import utcnow


class User(AppBase):
    __tablename__ = "users"
    # Ids are never reused: a deleted user's archived database must not be mistaken for a new user's
    __table_args__ = {"sqlite_autoincrement": True}

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(32), unique=True, index=True, nullable=False)  # lowercase
    display_name = Column(String(80), nullable=False)
    password_hash = Column(String(200), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)


class AppSetting(AppBase):
    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)


class RevokedSession(AppBase):
    """Session cookies closed with "Sign out"; kept until they would have expired anyway."""
    __tablename__ = "revoked_sessions"

    token_hash = Column(String(64), primary_key=True)  # sha256 of the cookie value
    expires_at = Column(DateTime, nullable=False, index=True)
