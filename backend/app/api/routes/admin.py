from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_db
from app.models.user import User

router = APIRouter(prefix="/api/admin", tags=["admin"])


def check_admin(key: str = Query(..., alias="key")):
    if not settings.admin_secret or key != settings.admin_secret:
        raise HTTPException(401, "Unauthorized")


@router.get("/ieb-users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(check_admin),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users  = result.scalars().all()
    today  = datetime.now(timezone.utc).date()
    return {
        "users": [
            {
                "id":           u.id,
                "email":        u.email,
                "tier":         u.tier,
                "is_active":    u.is_active,
                "has_password": bool(u.hashed_password),
                "has_google":   bool(u.google_id),
                "daily_used":   u.daily_analyses if u.daily_reset_date == today else 0,
                "created_at":   u.created_at.isoformat() if u.created_at else None,
                "last_login":   u.last_login.isoformat() if u.last_login else None,
            }
            for u in users
        ]
    }


class SetTierRequest(BaseModel):
    user_id: str
    tier: str   # "free" | "pro"


@router.post("/ieb-set-tier")
async def set_tier(
    body: SetTierRequest,
    db:   AsyncSession = Depends(get_db),
    key:  str = Query(..., alias="key"),
):
    if not settings.admin_secret or key != settings.admin_secret:
        raise HTTPException(401, "Unauthorized")
    if body.tier not in ("free", "pro"):
        raise HTTPException(400, "Tier must be 'free' or 'pro'")

    result = await db.execute(select(User).where(User.id == body.user_id))
    user   = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    user.tier                  = body.tier
    user.refresh_token         = None   # force re-login so new JWT picks up new tier
    user.refresh_token_expires = None
    await db.commit()
    return {"message": f"{user.email} → {body.tier}", "email": user.email, "tier": body.tier}
