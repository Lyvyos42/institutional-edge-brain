from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.alert import Alert
from app.auth.jwt import get_current_user

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

VALID_CONDITIONS = {"signal_is_buy", "signal_is_sell", "confidence_above", "any_signal"}
VALID_TIMEFRAMES = {"1m", "5m", "15m", "30m", "1h", "4h", "1d"}


class AlertCreate(BaseModel):
    symbol: str
    timeframe: str = "5m"
    condition: str
    threshold: float | None = None   # required for confidence_above


class CheckRequest(BaseModel):
    symbol: str
    timeframe: str
    signal: str
    confidence: float


# ── List ──────────────────────────────────────────────────────────────────────
@router.get("")
async def list_alerts(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Alert)
        .where(Alert.user_id == user["sub"], Alert.is_active == True)
        .order_by(Alert.created_at.desc())
    )
    alerts = result.scalars().all()
    return [_serialize(a) for a in alerts]


# ── Create ────────────────────────────────────────────────────────────────────
@router.post("", status_code=201)
async def create_alert(
    body: AlertCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    symbol = body.symbol.upper().strip()
    if len(symbol) > 20:
        raise HTTPException(400, "Invalid symbol")
    if body.timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(400, f"Invalid timeframe. Choose: {VALID_TIMEFRAMES}")
    if body.condition not in VALID_CONDITIONS:
        raise HTTPException(400, f"Invalid condition. Choose: {VALID_CONDITIONS}")
    if body.condition == "confidence_above":
        if body.threshold is None or not (0 < body.threshold <= 1):
            raise HTTPException(400, "confidence_above requires threshold between 0 and 1")

    # Limit to 20 active alerts per user
    count_result = await db.execute(
        select(Alert).where(Alert.user_id == user["sub"], Alert.is_active == True)
    )
    if len(count_result.scalars().all()) >= 20:
        raise HTTPException(400, "Maximum 20 active alerts allowed")

    alert = Alert(
        user_id=user["sub"],
        symbol=symbol,
        timeframe=body.timeframe,
        condition=body.condition,
        threshold=body.threshold,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return _serialize(alert)


# ── Delete ────────────────────────────────────────────────────────────────────
@router.delete("/{alert_id}", status_code=204)
async def delete_alert(
    alert_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Alert).where(Alert.id == alert_id, Alert.user_id == user["sub"]))
    alert  = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(404, "Alert not found")
    alert.is_active = False
    await db.commit()


# ── Check ─────────────────────────────────────────────────────────────────────
@router.post("/check")
async def check_alerts(
    body: CheckRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check if any active alerts match the latest analysis result. Returns triggered alerts."""
    result = await db.execute(
        select(Alert).where(
            Alert.user_id == user["sub"],
            Alert.is_active == True,
            Alert.symbol == body.symbol.upper(),
        )
    )
    alerts    = result.scalars().all()
    triggered = []

    for alert in alerts:
        matched = False
        if alert.condition == "signal_is_buy" and body.signal in ("BUY", "STRONG_BUY"):
            matched = True
        elif alert.condition == "signal_is_sell" and body.signal in ("SELL", "STRONG_SELL"):
            matched = True
        elif alert.condition == "any_signal" and body.signal not in ("HOLD", "NEUTRAL"):
            matched = True
        elif alert.condition == "confidence_above" and alert.threshold is not None:
            if body.confidence >= alert.threshold:
                matched = True

        if matched:
            alert.last_triggered = datetime.now(timezone.utc)
            triggered.append(_serialize(alert))

    if triggered:
        await db.commit()

    return {"triggered": triggered}


def _serialize(a: Alert) -> dict:
    return {
        "id":             a.id,
        "symbol":         a.symbol,
        "timeframe":      a.timeframe,
        "condition":      a.condition,
        "threshold":      a.threshold,
        "is_active":      a.is_active,
        "created_at":     a.created_at.isoformat() if a.created_at else None,
        "last_triggered": a.last_triggered.isoformat() if a.last_triggered else None,
    }
