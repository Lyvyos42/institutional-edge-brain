from datetime import datetime, timedelta, timezone

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
from app.auth.email import send_password_reset_email

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


# ── Helpers ───────────────────────────────────────────────────────────────────
def _build_auth_response(user: User, include_refresh: bool = True) -> dict:
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
    if not user or not verify_password(form.password, user.hashed_password):
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
    if not user or not verify_password(body.password, user.hashed_password):
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

    # Rotate refresh token
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
        "id":         user.id,
        "email":      user.email,
        "tier":       user.tier,
        "is_active":  user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "daily_used": daily_used,
        "daily_limit": FREE_LIMIT if user.tier == "free" else None,
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
    if not user or not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(400, "Current password is incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(400, "New password must be at least 8 characters")

    user.hashed_password       = hash_password(body.new_password)
    user.refresh_token         = None  # invalidate all sessions
    user.refresh_token_expires = None
    await db.commit()
    return {"message": "Password changed successfully. Please log in again."}


# ── Forgot password ───────────────────────────────────────────────────────────
@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user   = result.scalar_one_or_none()

    # Always return success — don't reveal if email exists
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
    user.refresh_token         = None  # invalidate all sessions
    user.refresh_token_expires = None
    await db.commit()
    return {"message": "Password reset successfully. You can now log in."}
