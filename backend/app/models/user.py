import uuid
from sqlalchemy import Boolean, Column, String, DateTime, Integer, Date
from sqlalchemy.sql import func
from app.db.database import Base


class User(Base):
    __tablename__ = "users"
    id                    = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email                 = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password       = Column(String, nullable=True)   # nullable for OAuth/magic-link users
    tier                  = Column(String(20), nullable=False, default="free")
    is_active             = Column(Boolean, nullable=False, default=True)
    created_at            = Column(DateTime(timezone=True), server_default=func.now())
    last_login            = Column(DateTime(timezone=True), nullable=True)
    # Refresh token (stored as SHA-256 hash)
    refresh_token         = Column(String, nullable=True)
    refresh_token_expires = Column(DateTime(timezone=True), nullable=True)
    # Password reset token (stored as SHA-256 hash)
    reset_token           = Column(String, nullable=True)
    reset_token_expires   = Column(DateTime(timezone=True), nullable=True)
    # Daily usage tracking for free tier
    daily_analyses        = Column(Integer, nullable=False, default=0)
    daily_reset_date      = Column(Date, nullable=True)
    # OAuth / passwordless
    google_id             = Column(String, nullable=True, index=True)
    magic_token           = Column(String, nullable=True)
    magic_token_expires   = Column(DateTime(timezone=True), nullable=True)
