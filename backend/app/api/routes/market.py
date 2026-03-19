from fastapi import APIRouter
from app.data.feed import fetch_live_data, SYMBOL_MAP
import asyncio
from concurrent.futures import ThreadPoolExecutor

router = APIRouter(prefix="/api/market", tags=["market"])
_pool = ThreadPoolExecutor(max_workers=2)

SYMBOLS = {
    "forex":   ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"],
    "metals":  ["XAUUSD", "XAGUSD"],
    "energy":  ["USOIL", "UKOIL", "NATGAS"],
    "crypto":  ["BTCUSD", "ETHUSD"],
    "indices": ["SPX500", "NAS100", "GER40", "UK100", "JPN225"],
    "stocks":  ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META"],
}


@router.get("/symbols")
async def get_symbols():
    return SYMBOLS


@router.get("/price/{symbol}")
async def get_price(symbol: str):
    loop = asyncio.get_event_loop()
    df = await loop.run_in_executor(_pool, fetch_live_data, symbol.upper(), "5m", 50)
    if df is None or df.empty:
        return {"symbol": symbol, "price": None, "error": "No data"}
    return {
        "symbol": symbol,
        "price": round(float(df["close"].iloc[-1]), 5),
        "open": round(float(df["open"].iloc[-1]), 5),
        "high": round(float(df["high"].iloc[-1]), 5),
        "low": round(float(df["low"].iloc[-1]), 5),
        "change_pct": round(
            (float(df["close"].iloc[-1]) - float(df["close"].iloc[-2]))
            / float(df["close"].iloc[-2]) * 100,
            3,
        ) if len(df) > 1 else 0.0,
    }
