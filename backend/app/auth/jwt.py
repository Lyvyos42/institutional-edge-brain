import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.db.database import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


# ── Password helpers ──────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── Token hashing (SHA-256 for fast DB lookup) ────────────────────────────────
def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ── Access token (JWT, 15 min) ────────────────────────────────────────────────
def create_access_token(user_id: str, email: str, tier: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode(
        {"sub": user_id, "email": email, "tier": tier, "exp": expire},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


# Backward-compat alias
create_token = create_access_token


# ── Refresh token (opaque random, 30 days) ────────────────────────────────────
def generate_refresh_token() -> str:
    """Returns a raw random token (stored hashed in DB, sent raw to client)."""
    return secrets.token_urlsafe(48)


# ── Password reset token (opaque random, 15 min via DB expiry) ───────────────
def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


# ── FastAPI dependencies ──────────────────────────────────────────────────────
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_optional_user(
    token: str = Depends(oauth2_scheme),
) -> Optional[dict]:
    if not token:
        return None
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
