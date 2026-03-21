"""
Server-side data feed.
Priority chain per asset class:
  Crypto  → Binance REST → Kraken REST → ccxt → yfinance
  FX/Metals/Indices → tvDatafeed → yfinance
  Stocks  → yfinance

Binance and Kraken are free public APIs with no key required.
tvDatafeed uses TradingView's WebSocket (no credentials needed).
"""
import time
import json
import urllib.request
import urllib.parse
import pandas as pd
import numpy as np

try:
    from tvDatafeed import TvDatafeed, Interval as TvInterval
    HAS_TV = True
    _TV_INTERVAL: dict[str, TvInterval] = {
        "1m":  TvInterval.in_1_minute,
        "5m":  TvInterval.in_5_minute,
        "15m": TvInterval.in_15_minute,
        "30m": TvInterval.in_30_minute,
        "1h":  TvInterval.in_1_hour,
        "60m": TvInterval.in_1_hour,
        "4h":  TvInterval.in_4_hour,
        "1d":  TvInterval.in_daily,
        "1w":  TvInterval.in_weekly,
    }
except ImportError:
    HAS_TV = False
    _TV_INTERVAL = {}

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


# ── Symbol maps ────────────────────────────────────────────────────────────────

# Maps display symbol → Binance pair (USDT-quoted)
_BINANCE_SYM: dict[str, str] = {
    "BTCUSD":  "BTCUSDT",  "ETHUSD":  "ETHUSDT",
    "BNBUSD":  "BNBUSDT",  "XRPUSD":  "XRPUSDT",
    "SOLUSD":  "SOLUSDT",  "ADAUSD":  "ADAUSDT",
    "DOGEUSD": "DOGEUSDT", "AVAXUSD": "AVAXUSDT",
    "DOTUSD":  "DOTUSDT",  "LINKUSD": "LINKUSDT",
    "LTCUSD":  "LTCUSDT",  "BCHUSD":  "BCHUSDT",
    "NEARUSD": "NEARUSDT", "UNIUSD":  "UNIUSDT",
    "ATOMUSD": "ATOMUSDT", "MATICUSD":"MATICUSDT",
}

# Maps display symbol → Kraken pair
_KRAKEN_SYM: dict[str, str] = {
    "BTCUSD": "XBTUSD", "ETHUSD": "ETHUSD",
    "SOLUSD": "SOLUSD", "XRPUSD": "XRPUSD",
    "ADAUSD": "ADAUSD", "DOTUSD": "DOTUSD",
    "LTCUSD": "XLTCZUSD", "LINKUSD": "LINKUSD",
}

# Kraken interval in minutes
_KRAKEN_INTERVAL: dict[str, int] = {
    "1m": 1, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "60m": 60, "4h": 240, "1d": 1440,
}

# TradingView exchange map for tvDatafeed
_TV_EXCHANGE: dict[str, tuple[str, str]] = {
    # Spot Metals (OANDA)
    "XAUUSD": ("XAUUSD", "OANDA"),  "XAGUSD": ("XAGUSD", "OANDA"),
    "XPTUSD": ("XPTUSD", "OANDA"),  "XPDUSD": ("XPDUSD", "OANDA"),
    # FX Majors (FX_IDC)
    "EURUSD": ("EURUSD", "FX_IDC"), "GBPUSD": ("GBPUSD", "FX_IDC"),
    "USDJPY": ("USDJPY", "FX_IDC"), "AUDUSD": ("AUDUSD", "FX_IDC"),
    "USDCAD": ("USDCAD", "FX_IDC"), "USDCHF": ("USDCHF", "FX_IDC"),
    "NZDUSD": ("NZDUSD", "FX_IDC"),
    # FX Minors (FX_IDC)
    "EURGBP": ("EURGBP", "FX_IDC"), "EURJPY": ("EURJPY", "FX_IDC"),
    "GBPJPY": ("GBPJPY", "FX_IDC"), "EURCHF": ("EURCHF", "FX_IDC"),
    "EURAUD": ("EURAUD", "FX_IDC"), "EURCAD": ("EURCAD", "FX_IDC"),
    "EURNZD": ("EURNZD", "FX_IDC"), "GBPAUD": ("GBPAUD", "FX_IDC"),
    "GBPCAD": ("GBPCAD", "FX_IDC"), "GBPCHF": ("GBPCHF", "FX_IDC"),
    "GBPNZD": ("GBPNZD", "FX_IDC"), "AUDJPY": ("AUDJPY", "FX_IDC"),
    "AUDCAD": ("AUDCAD", "FX_IDC"), "AUDCHF": ("AUDCHF", "FX_IDC"),
    "AUDNZD": ("AUDNZD", "FX_IDC"), "CADJPY": ("CADJPY", "FX_IDC"),
    "CADCHF": ("CADCHF", "FX_IDC"), "CHFJPY": ("CHFJPY", "FX_IDC"),
    "NZDJPY": ("NZDJPY", "FX_IDC"), "NZDCAD": ("NZDCAD", "FX_IDC"),
    "NZDCHF": ("NZDCHF", "FX_IDC"),
    # FX Exotics (FX_IDC)
    "USDTRY": ("USDTRY", "FX_IDC"), "USDZAR": ("USDZAR", "FX_IDC"),
    "USDMXN": ("USDMXN", "FX_IDC"), "USDSEK": ("USDSEK", "FX_IDC"),
    "USDNOK": ("USDNOK", "FX_IDC"), "USDSGD": ("USDSGD", "FX_IDC"),
    "USDHKD": ("USDHKD", "FX_IDC"), "USDCNH": ("USDCNH", "FX_IDC"),
    # Energy CFDs (TVC)
    "USOIL":  ("USOIL",      "TVC"), "UKOIL":  ("UKOIL",      "TVC"),
    "NATGAS": ("NATURALGAS", "TVC"),
    # Commodity CFDs (TVC)
    "CORN":    ("CORN",    "TVC"),   "WHEAT":   ("WHEAT",   "TVC"),
    "SOYBEAN": ("SOYBEAN", "TVC"),   "COFFEE":  ("COFFEE",  "TVC"),
    "SUGAR":   ("SUGAR",   "TVC"),   "COTTON":  ("COTTON",  "TVC"),
    "COCOA":   ("COCOA",   "TVC"),
    # Crypto (BINANCE) — used as TV fallback only; primary is direct REST
    "BTCUSD":  ("BTCUSDT",  "BINANCE"), "ETHUSD":  ("ETHUSDT",  "BINANCE"),
    "BNBUSD":  ("BNBUSDT",  "BINANCE"), "XRPUSD":  ("XRPUSDT",  "BINANCE"),
    "SOLUSD":  ("SOLUSDT",  "BINANCE"), "ADAUSD":  ("ADAUSDT",  "BINANCE"),
    "DOGEUSD": ("DOGEUSDT", "BINANCE"), "AVAXUSD": ("AVAXUSDT", "BINANCE"),
    "DOTUSD":  ("DOTUSDT",  "BINANCE"), "LINKUSD": ("LINKUSDT", "BINANCE"),
    "LTCUSD":  ("LTCUSDT",  "BINANCE"), "BCHUSD":  ("BCHUSDT",  "BINANCE"),
    "NEARUSD": ("NEARUSDT", "BINANCE"), "UNIUSD":  ("UNIUSDT",  "BINANCE"),
    "ATOMUSD": ("ATOMUSDT", "BINANCE"), "MATICUSD":("MATICUSDT","BINANCE"),
    # Equity Indices (TV native)
    "US500":  ("SPX",    "SP"),     "SPX500":  ("SPX",    "SP"),
    "NAS100": ("NDX",    "NASDAQ"), "US100":   ("NDX",    "NASDAQ"),
    "US30":   ("DJI",    "DJ"),
    "UK100":  ("UK100",  "TVC"),
    "GER40":  ("DEU40",  "TVC"),
    "FRA40":  ("CAC40",  "TVC"),
    "JPN225": ("NI225",  "TVC"),
    "HK50":   ("HSI",    "TVC"),
    "AUS200": ("ASX200", "TVC"),
    "STOXX50":("STOXX50","TVC"),
}

# yfinance symbol map (display → yfinance ticker)
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

CRYPTO_SYMBOLS = set(_BINANCE_SYM.keys())

# Lazy singleton — TvDatafeed WebSocket connection, reused across requests
_tv_client: "TvDatafeed | None" = None


def _get_tv_client() -> "TvDatafeed | None":
    """Return shared TvDatafeed instance (no credentials = public/guest access)."""
    global _tv_client
    if _tv_client is None and HAS_TV:
        try:
            _tv_client = TvDatafeed()
        except Exception:
            pass
    return _tv_client


# ── Binance interval string map ────────────────────────────────────────────────
_BINANCE_INTERVAL = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "60m": "1h", "4h": "4h", "1d": "1d", "1w": "1w",
}


def _fetch_binance(symbol: str, timeframe: str, limit: int) -> pd.DataFrame | None:
    """
    Fetch OHLCV from Binance public REST API — no API key required.
    Returns DataFrame[open, high, low, close, volume] or None on failure.
    Endpoint: GET https://api.binance.com/api/v3/klines
    """
    pair = _BINANCE_SYM.get(symbol.upper())
    if not pair:
        return None

    interval = _BINANCE_INTERVAL.get(timeframe, "5m")
    url = (
        "https://api.binance.com/api/v3/klines"
        f"?symbol={pair}&interval={interval}&limit={min(limit, 1000)}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = json.loads(r.read())
        if not raw:
            return None
        # Each row: [openTime, open, high, low, close, volume, closeTime, ...]
        df = pd.DataFrame(raw, columns=[
            "ts", "open", "high", "low", "close", "volume",
            "close_ts", "quote_vol", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore"
        ])
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        return df.tail(limit).reset_index(drop=True)
    except Exception:
        return None


def _fetch_kraken(symbol: str, timeframe: str, limit: int) -> pd.DataFrame | None:
    """
    Fetch OHLCV from Kraken public REST API — no API key required.
    Returns DataFrame[open, high, low, close, volume] or None on failure.
    Endpoint: GET https://api.kraken.com/0/public/OHLC
    """
    pair = _KRAKEN_SYM.get(symbol.upper())
    if not pair:
        return None

    interval = _KRAKEN_INTERVAL.get(timeframe, 5)
    # Kraken returns at most 720 bars; go back enough to cover 'limit'
    since = int(time.time()) - interval * 60 * max(limit + 50, 720)
    url = (
        f"https://api.kraken.com/0/public/OHLC"
        f"?pair={pair}&interval={interval}&since={since}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        if data.get("error"):
            return None
        # Kraken wraps the data under result[pair_name]
        result = data.get("result", {})
        rows = None
        for key, val in result.items():
            if key != "last" and isinstance(val, list):
                rows = val
                break
        if not rows:
            return None
        # Each row: [time, open, high, low, close, vwap, volume, count]
        df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "vwap", "volume", "count"])
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        return df.tail(limit).reset_index(drop=True)
    except Exception:
        return None


def _fetch_tvdatafeed(symbol: str, timeframe: str, limit: int) -> pd.DataFrame | None:
    """Fetch OHLCV from TradingView WebSocket (no API key required)."""
    entry = _TV_EXCHANGE.get(symbol.upper())
    if not entry:
        return None

    tv_symbol, exchange = entry
    tv = _get_tv_client()
    if tv is None:
        return None

    interval = _TV_INTERVAL.get(timeframe, TvInterval.in_5_minute)
    try:
        df = tv.get_hist(
            symbol=tv_symbol,
            exchange=exchange,
            interval=interval,
            n_bars=limit + 10,
        )
    except Exception:
        return None

    if df is None or df.empty:
        return None

    df.columns = [c.lower() for c in df.columns]
    needed = ["open", "high", "low", "close", "volume"]
    if any(c not in df.columns for c in needed):
        return None

    df = df[needed].astype(float).tail(limit).reset_index(drop=True)
    return df


def _fetch_yfinance(ticker: str, timeframe: str, limit: int) -> pd.DataFrame | None:
    if not HAS_YF:
        return None
    interval = TF_MAP.get(timeframe, "5m")
    if interval == "1m":
        period = "7d"
    elif interval in ("5m", "15m", "30m"):
        period = "60d"
    elif interval == "60m":
        period = "730d"
    else:
        period = "5y"

    try:
        data = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
    except Exception:
        return None

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
    if any(c not in data.columns for c in needed):
        return None
    df = data[needed].astype(float).tail(limit).reset_index(drop=True)
    df.columns = ["open", "high", "low", "close", "volume"]
    return df


def _fetch_ccxt_binance(symbol: str, timeframe: str, limit: int) -> pd.DataFrame | None:
    """ccxt Binance fallback — used only if direct REST calls fail."""
    if not HAS_CCXT:
        return None
    try:
        # Direct USDT pair mapping
        pair = _BINANCE_SYM.get(symbol.upper())
        if not pair:
            return None
        # Convert "BTCUSDT" → "BTC/USDT" for ccxt
        base = pair[:-4]  # strip "USDT"
        ccxt_sym = f"{base}/USDT"
        exchange = ccxt.binance({"enableRateLimit": True})
        bars = exchange.fetch_ohlcv(ccxt_sym, timeframe=timeframe, limit=limit)
        if not bars:
            return None
        df = pd.DataFrame(bars, columns=["ts", "open", "high", "low", "close", "volume"])
        return df[["open", "high", "low", "close", "volume"]].astype(float).reset_index(drop=True)
    except Exception:
        return None


def fetch_live_data(symbol: str = "XAUUSD", timeframe: str = "5m", limit: int = 300) -> pd.DataFrame | None:
    """
    Fetch OHLCV data. Returns DataFrame with columns open/high/low/close/volume.

    Priority by asset class:
      Crypto  → Binance REST → Kraken REST → tvDatafeed → ccxt → yfinance
      Others  → tvDatafeed → yfinance
    """
    sym = symbol.upper()

    if sym in CRYPTO_SYMBOLS:
        # 1. Binance direct REST — fastest, no key, real-time
        df = _fetch_binance(sym, timeframe, limit)
        if df is not None and not df.empty:
            return df

        # 2. Kraken REST — different servers, good backup
        df = _fetch_kraken(sym, timeframe, limit)
        if df is not None and not df.empty:
            return df

        # 3. TradingView (Binance feed via TV WebSocket)
        if HAS_TV:
            df = _fetch_tvdatafeed(sym, timeframe, limit)
            if df is not None and not df.empty:
                return df

        # 4. ccxt Binance (last crypto fallback)
        df = _fetch_ccxt_binance(sym, timeframe, limit)
        if df is not None and not df.empty:
            return df

    else:
        # Non-crypto: FX, metals, indices, energy, commodities
        # 1. TradingView (real-time, covers all TV symbols)
        if HAS_TV:
            df = _fetch_tvdatafeed(sym, timeframe, limit)
            if df is not None and not df.empty:
                return df

    # Final fallback: yfinance (delayed but broad coverage)
    if HAS_YF:
        yf_ticker = SYMBOL_MAP.get(sym, sym)
        df = _fetch_yfinance(yf_ticker, timeframe, limit)
        if df is not None and not df.empty:
            return df

    return None
