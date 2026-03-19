from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.models.signal import BrainSignal
from app.auth.jwt import get_optional_user
from app.brain.runner import analyze_symbol

router = APIRouter(prefix="/api/signals", tags=["signals"])

VALID_TIMEFRAMES = {"1m", "5m", "15m", "30m", "1h", "4h", "1d"}


class AnalyzeRequest(BaseModel):
    symbol: str = "XAUUSD"
    timeframe: str = "5m"


@router.post("/analyze")
async def analyze(
    body: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    user: dict | None = Depends(get_optional_user),
):
    if body.timeframe not in VALID_TIMEFRAMES:
        raise HTTPException(400, f"Invalid timeframe. Choose: {VALID_TIMEFRAMES}")
    symbol = body.symbol.upper().strip()
    if len(symbol) > 20 or not all(c.isalnum() or c in "=-^/" for c in symbol):
        raise HTTPException(400, "Invalid symbol")

    result = await analyze_symbol(symbol, body.timeframe)
    if "error" in result:
        raise HTTPException(503, result["error"])

    levels = result.get("levels", {})
    sig = BrainSignal(
        user_id=user["sub"] if user else None,
        symbol=symbol,
        timeframe=body.timeframe,
        direction=result["signal"],
        confidence=result["confidence"],
        entry_price=levels.get("entry"),
        stop_loss=levels.get("stop_loss"),
        take_profit=levels.get("take_profit"),
        risk_reward=levels.get("risk_reward"),
        module_results=result.get("modules"),
        ensemble_detail=result.get("ensemble"),
    )
    db.add(sig)
    await db.commit()
    await db.refresh(sig)

    return {**result, "signal_id": str(sig.id)}


@router.get("/history")
async def history(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user: dict | None = Depends(get_optional_user),
):
    q = select(BrainSignal).order_by(desc(BrainSignal.created_at)).limit(min(limit, 100))
    if user:
        q = q.where(BrainSignal.user_id == user["sub"])
    result = await db.execute(q)
    signals = result.scalars().all()
    return [
        {
            "id": s.id,
            "symbol": s.symbol,
            "timeframe": s.timeframe,
            "direction": s.direction,
            "confidence": s.confidence,
            "entry_price": s.entry_price,
            "stop_loss": s.stop_loss,
            "take_profit": s.take_profit,
            "risk_reward": s.risk_reward,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in signals
    ]
