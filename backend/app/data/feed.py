"""
Server-side data feed. yfinance primary, ccxt fallback for crypto.
"""
import pandas as pd
import numpy as np

try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False

try:
    import ccxt
    HAS_CCXT = True
except ImportError:
    HAS_CCXT = False

# Map display symbols → yfinance tickers
SYMBOL_MAP = {
    "XAUUSD": "GC=F",    "XAGUSD": "SI=F",
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X", "USDCAD": "USDCAD=X", "USDCHF": "USDCHF=X",
    "NZDUSD": "NZDUSD=X", "EURGBP": "EURGBP=X", "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X",
    "BTCUSD": "BTC-USD",  "ETHUSD": "ETH-USD",
    "USOIL": "CL=F",      "UKOIL": "BZ=F",     "NATGAS": "NG=F",
    "SPX500": "^GSPC",    "NAS100": "^NDX",     "GER40": "^GDAXI",
    "UK100": "^FTSE",     "JPN225": "^N225",
    "CORN": "ZC=F",       "WHEAT": "ZW=F",      "SOYBEAN": "ZS=F",
}

# yfinance interval map
TF_MAP = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "60m", "4h": "60m", "1d": "1d"}

CRYPTO_SYMBOLS = {"BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD", "BNBUSD"}


def fetch_live_data(symbol: str = "XAUUSD", timeframe: str = "5m", limit: int = 300) -> pd.DataFrame | None:
    """Fetch OHLCV data. Returns DataFrame with columns open/high/low/close/volume."""
    yf_ticker = SYMBOL_MAP.get(symbol.upper(), symbol)

    # Crypto: try ccxt first
    if symbol.upper() in CRYPTO_SYMBOLS and HAS_CCXT:
        try:
            df = _fetch_ccxt(symbol, timeframe, limit)
            if df is not None and not df.empty:
                return df
        except Exception:
            pass

    # yfinance for everything else
    if HAS_YF:
        try:
            df = _fetch_yfinance(yf_ticker, timeframe, limit)
            if df is not None and not df.empty:
                return df
        except Exception:
            pass

    return None


def _fetch_yfinance(ticker: str, timeframe: str, limit: int) -> pd.DataFrame | None:
    interval = TF_MAP.get(timeframe, "5m")
    if interval in ("1m",):
        period = "7d"
    elif interval in ("5m", "15m", "30m"):
        period = "60d"
    elif interval == "60m":
        period = "730d"
    else:
        period = "5y"

    data = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
    if data is None or data.empty:
        return None
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data = data.reset_index()
    for col in ["Datetime", "Date"]:
        if col in data.columns:
            data = data.rename(columns={col: "datetime"})
            break
    needed = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in needed if c not in data.columns]
    if missing:
        return None
    df = data[needed].astype(float).tail(limit).reset_index(drop=True)
    df.columns = ["open", "high", "low", "close", "volume"]
    return df


def _fetch_ccxt(symbol: str, timeframe: str, limit: int) -> pd.DataFrame | None:
    ccxt_sym = symbol.replace("USD", "/USDT").upper()
    exchange = ccxt.binance({"enableRateLimit": True})
    bars = exchange.fetch_ohlcv(ccxt_sym, timeframe=timeframe, limit=limit)
    if not bars:
        return None
    df = pd.DataFrame(bars, columns=["ts", "open", "high", "low", "close", "volume"])
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    return df
