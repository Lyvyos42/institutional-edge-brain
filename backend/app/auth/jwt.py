import asyncio
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import httpx
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.config import settings

log = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)

ALGORITHM  = settings.jwt_algorithm
SECRET_KEY = settings.jwt_secret

# ── Supabase JWKS cache ────────────────────────────────────────────────────────
_jwks_cache: list[dict] | None = None
_jwks_lock = asyncio.Lock()


async def _get_jwks() -> list[dict]:
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    if not settings.supabase_url:
        return []
    async with _jwks_lock:
        if _jwks_cache:
            return _jwks_cache
        try:
            url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(url)
                r.raise_for_status()
                _jwks_cache = r.json().get("keys", [])
                log.info("Loaded %d Supabase JWKS keys", len(_jwks_cache))
        except Exception as e:
            log.warning("Could not fetch Supabase JWKS: %s", e)
            _jwks_cache = []
    return _jwks_cache or []


def _try_supabase_jwks(token: str, jwks: list[dict]) -> dict | None:
    for key in jwks:
        try:
            return jwt.decode(
                token, key,
                algorithms=["ES256", "RS256", "HS256"],
                options={"verify_aud": False},
            )
        except JWTError:
            continue
    return None


def _try_legacy_supabase(token: str) -> dict | None:
    if not settings.supabase_jwt_secret:
        return None
    try:
        return jwt.decode(
            token, settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except JWTError:
        return None


def _try_custom(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ── Public decode functions ────────────────────────────────────────────────────
def decode_token(token: str, _jwks: list[dict] | None = None) -> dict[str, Any]:
    jwks = _jwks or []

    # 1. Supabase JWKS (ECC / RSA)
    if jwks:
        result = _try_supabase_jwks(token, jwks)
        if result:
            return result

    # 2. Supabase legacy HS256 secret
    result = _try_legacy_supabase(token)
    if result:
        return result

    # 3. Custom JWT (local dev)
    result = _try_custom(token)
    if result:
        return result

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def decode_token_async(token: str) -> dict[str, Any]:
    jwks = await _get_jwks()
    return decode_token(token, jwks)


# ── FastAPI dependencies ──────────────────────────────────────────────────────
async def get_current_user(
    token: str = Depends(oauth2_scheme),
) -> dict:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return await decode_token_async(token)


async def get_optional_user(
    token: str = Depends(oauth2_scheme),
) -> Optional[dict]:
    if not token:
        return None
    try:
        return await decode_token_async(token)
    except HTTPException:
        return None


# ── Password helpers ──────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── Token helpers ─────────────────────────────────────────────────────────────
def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user_id: str, email: str, tier: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode(
        {"sub": user_id, "email": email, "tier": tier, "exp": expire},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


# Backward-compat alias
create_token = create_access_token


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)
