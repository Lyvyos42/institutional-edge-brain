from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_db
from app.models.user import User
from app.auth.jwt import (
    hash_password, verify_password,
    create_access_token, generate_refresh_token, generate_reset_token,
    hash_token, get_current_user,
)
from app.auth.email import send_password_reset_email, send_magic_link_email

router = APIRouter(prefix="/api/auth", tags=["auth"])

FREE_LIMIT = settings.free_daily_limit


# ── Schemas ───────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    token: str
    new_password: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class MagicRequestSchema(BaseModel):
    email: EmailStr

class MagicVerifySchema(BaseModel):
    email: EmailStr
    token: str

class GoogleAuthSchema(BaseModel):
    credential: str   # Google ID token


# ── Helpers ───────────────────────────────────────────────────────────────────
def _build_auth_response(user: User) -> dict:
    access_token  = create_access_token(user.id, user.email, user.tier)
    refresh_token = generate_refresh_token()

    user.refresh_token         = hash_token(refresh_token)
    user.refresh_token_expires = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days)

    daily_used = user.daily_analyses if user.daily_reset_date == datetime.now(timezone.utc).date() else 0

    return {
        "access_token":  access_token,
        "refresh_token": refresh_token,
        "token_type":    "bearer",
        "tier":          user.tier,
        "email":         user.email,
        "daily_used":    daily_used,
        "daily_limit":   FREE_LIMIT if user.tier == "free" else None,
    }


# ── Register ──────────────────────────────────────────────────────────────────
@router.post("/register")
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Email already registered")
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    user = User(email=body.email, hashed_password=hash_password(body.password))
    db.add(user)
    await db.flush()

    response = _build_auth_response(user)
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    return response


# ── Login (form) ──────────────────────────────────────────────────────────────
@router.post("/token")
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form.username))
    user   = result.scalar_one_or_none()
    if not user or not user.hashed_password or not verify_password(form.password, user.hashed_password):
        raise HTTPException(401, "Invalid credentials")
    if not user.is_active:
        raise HTTPException(403, "Account disabled")

    response = _build_auth_response(user)
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    return response


# ── Login (JSON) ──────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/login")
async def login_json(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user   = result.scalar_one_or_none()
    if not user or not user.hashed_password or not verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "Invalid credentials")
    if not user.is_active:
        raise HTTPException(403, "Account disabled")

    response = _build_auth_response(user)
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    return response


# ── Refresh token ─────────────────────────────────────────────────────────────
@router.post("/refresh")
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    token_hash = hash_token(body.refresh_token)
    result     = await db.execute(select(User).where(User.refresh_token == token_hash))
    user       = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(401, "Invalid refresh token")
    if not user.refresh_token_expires or user.refresh_token_expires < datetime.now(timezone.utc):
        raise HTTPException(401, "Refresh token expired — please log in again")

    response = _build_auth_response(user)
    await db.commit()
    return response


# ── Me ────────────────────────────────────────────────────────────────────────
@router.get("/me")
async def me(payload: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user   = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    today      = datetime.now(timezone.utc).date()
    daily_used = user.daily_analyses if user.daily_reset_date == today else 0

    return {
        "id":           user.id,
        "email":        user.email,
        "tier":         user.tier,
        "is_active":    user.is_active,
        "has_password": bool(user.hashed_password),
        "has_google":   bool(user.google_id),
        "created_at":   user.created_at.isoformat() if user.created_at else None,
        "last_login":   user.last_login.isoformat() if user.last_login else None,
        "daily_used":   daily_used,
        "daily_limit":  FREE_LIMIT if user.tier == "free" else None,
    }


# ── Change password ───────────────────────────────────────────────────────────
@router.put("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    payload: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user   = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    if not user.hashed_password or not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(400, "Current password is incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(400, "New password must be at least 8 characters")

    user.hashed_password       = hash_password(body.new_password)
    user.refresh_token         = None
    user.refresh_token_expires = None
    await db.commit()
    return {"message": "Password changed successfully. Please log in again."}


# ── Forgot password ───────────────────────────────────────────────────────────
@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user   = result.scalar_one_or_none()

    if user and user.is_active:
        token = generate_reset_token()
        user.reset_token         = hash_token(token)
        user.reset_token_expires = datetime.now(timezone.utc) + timedelta(minutes=15)
        await db.commit()

        reset_url = f"{settings.frontend_url}/reset-password?token={token}&email={body.email}"
        send_password_reset_email(body.email, reset_url)

    return {"message": "If that email is registered, you will receive a reset link shortly."}


# ── Reset password ────────────────────────────────────────────────────────────
@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user   = result.scalar_one_or_none()

    if (
        not user
        or not user.reset_token
        or user.reset_token != hash_token(body.token)
        or not user.reset_token_expires
        or user.reset_token_expires < datetime.now(timezone.utc)
    ):
        raise HTTPException(400, "Invalid or expired reset link. Please request a new one.")

    if len(body.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    user.hashed_password       = hash_password(body.new_password)
    user.reset_token           = None
    user.reset_token_expires   = None
    user.refresh_token         = None
    user.refresh_token_expires = None
    await db.commit()
    return {"message": "Password reset successfully. You can now log in."}


# ── Magic link — request ──────────────────────────────────────────────────────
@router.post("/magic-request")
async def magic_request(body: MagicRequestSchema, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user   = result.scalar_one_or_none()

    # Create account automatically if email not seen before
    if not user:
        user = User(email=body.email, hashed_password=None)
        db.add(user)
        await db.flush()

    if not user.is_active:
        # Still return success — don't reveal account status
        return {"message": "If that email is valid, a login link has been sent."}

    token = generate_reset_token()
    user.magic_token         = hash_token(token)
    user.magic_token_expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    await db.commit()

    magic_url = f"{settings.frontend_url}/magic?token={token}&email={body.email}"
    send_magic_link_email(body.email, magic_url)

    return {"message": "If that email is valid, a login link has been sent."}


# ── Magic link — verify ───────────────────────────────────────────────────────
@router.post("/magic-verify")
async def magic_verify(body: MagicVerifySchema, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user   = result.scalar_one_or_none()

    if (
        not user
        or not user.magic_token
        or user.magic_token != hash_token(body.token)
        or not user.magic_token_expires
        or user.magic_token_expires < datetime.now(timezone.utc)
    ):
        raise HTTPException(400, "Invalid or expired magic link. Please request a new one.")

    user.magic_token         = None
    user.magic_token_expires = None
    user.last_login          = datetime.now(timezone.utc)

    response = _build_auth_response(user)
    await db.commit()
    return response


# ── Google OAuth ──────────────────────────────────────────────────────────────
@router.post("/google")
async def google_auth(body: GoogleAuthSchema, db: AsyncSession = Depends(get_db)):
    if not settings.google_client_id:
        raise HTTPException(503, "Google auth is not configured")

    # Verify ID token with Google
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": body.credential},
            timeout=10,
        )

    if resp.status_code != 200:
        raise HTTPException(401, "Invalid Google credential")

    info = resp.json()

    # Verify audience matches our client ID
    if info.get("aud") != settings.google_client_id:
        raise HTTPException(401, "Google credential audience mismatch")

    if info.get("email_verified") not in ("true", True):
        raise HTTPException(400, "Google account email is not verified")

    email     = info["email"]
    google_id = info["sub"]

    # Find existing user by google_id or email
    result = await db.execute(select(User).where(User.google_id == google_id))
    user   = result.scalar_one_or_none()

    if not user:
        result = await db.execute(select(User).where(User.email == email))
        user   = result.scalar_one_or_none()

    if user:
        if not user.is_active:
            raise HTTPException(403, "Account disabled")
        # Link google_id if not already set
        if not user.google_id:
            user.google_id = google_id
    else:
        # New user — create account
        user = User(email=email, google_id=google_id, hashed_password=None)
        db.add(user)
        await db.flush()

    user.last_login = datetime.now(timezone.utc)
    response = _build_auth_response(user)
    await db.commit()
    return response


# ── Google OAuth (access_token flow) ─────────────────────────────────────────
class GoogleTokenSchema(BaseModel):
    access_token: str

@router.post("/google-token")
async def google_token_auth(body: GoogleTokenSchema, db: AsyncSession = Depends(get_db)):
    """Accepts a Google OAuth2 access_token (implicit flow), verifies with Google userinfo."""
    if not settings.google_client_id:
        raise HTTPException(503, "Google auth is not configured")

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {body.access_token}"},
            timeout=10,
        )

    if resp.status_code != 200:
        raise HTTPException(401, "Invalid Google access token")

    info      = resp.json()
    email     = info.get("email")
    google_id = info.get("sub")

    if not email or not google_id:
        raise HTTPException(400, "Google did not return email or user ID")
    if not info.get("email_verified"):
        raise HTTPException(400, "Google account email is not verified")

    result = await db.execute(select(User).where(User.google_id == google_id))
    user   = result.scalar_one_or_none()

    if not user:
        result = await db.execute(select(User).where(User.email == email))
        user   = result.scalar_one_or_none()

    if user:
        if not user.is_active:
            raise HTTPException(403, "Account disabled")
        if not user.google_id:
            user.google_id = google_id
    else:
        user = User(email=email, google_id=google_id, hashed_password=None)
        db.add(user)
        await db.flush()

    user.last_login = datetime.now(timezone.utc)
    response = _build_auth_response(user)
    await db.commit()
    return response
