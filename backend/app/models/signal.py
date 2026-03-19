import uuid
from sqlalchemy import Column, String, Float, JSON, DateTime
from sqlalchemy.sql import func
from app.db.database import Base


class BrainSignal(Base):
    __tablename__ = "brain_signals"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=True)
    symbol = Column(String(30), nullable=False)
    timeframe = Column(String(10), nullable=False, default="5m")
    direction = Column(String(10), nullable=False)  # BUY / SELL / HOLD
    confidence = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    risk_reward = Column(Float, nullable=True)
    module_results = Column(JSON, nullable=True)   # all 12 module outputs
    ensemble_detail = Column(JSON, nullable=True)  # short/medium/long model votes
    created_at = Column(DateTime(timezone=True), server_default=func.now())
