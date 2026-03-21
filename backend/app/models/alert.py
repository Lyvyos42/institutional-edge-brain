import uuid
from sqlalchemy import Boolean, Column, String, Float, DateTime
from sqlalchemy.sql import func
from app.db.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id             = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id        = Column(String, nullable=False, index=True)
    symbol         = Column(String(20), nullable=False)
    timeframe      = Column(String(5), nullable=False, default="5m")
    # condition: "signal_is_buy" | "signal_is_sell" | "confidence_above" | "any_signal"
    condition      = Column(String(30), nullable=False)
    threshold      = Column(Float, nullable=True)   # used for confidence_above (0-1)
    is_active      = Column(Boolean, nullable=False, default=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    last_triggered = Column(DateTime(timezone=True), nullable=True)
