"""
Server-side data feed.
Priority chain: TradingView (tvDatafeed) → yfinance → ccxt (crypto) → None
"""
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


# Maps display symbols → (TradingView symbol, exchange) for tvDatafeed.
_TV_EXCHANGE: dict[str, tuple[str, str]] = {
    # ── Spot Metals (OANDA) ──────────────────────────────────────────────────
    "XAUUSD": ("XAUUSD", "OANDA"),  "XAGUSD": ("XAGUSD", "OANDA"),
    "XPTUSD": ("XPTUSD", "OANDA"),  "XPDUSD": ("XPDUSD", "OANDA"),
    # ── FX Majors (FX_IDC) ───────────────────────────────────────────────────
    "EURUSD": ("EURUSD", "FX_IDC"), "GBPUSD": ("GBPUSD", "FX_IDC"),
    "USDJPY": ("USDJPY", "FX_IDC"), "AUDUSD": ("AUDUSD", "FX_IDC"),
    "USDCAD": ("USDCAD", "FX_IDC"), "USDCHF": ("USDCHF", "FX_IDC"),
    "NZDUSD": ("NZDUSD", "FX_IDC"),
    # ── FX Minors (FX_IDC) ───────────────────────────────────────────────────
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
    # ── FX Exotics (FX_IDC) ──────────────────────────────────────────────────
    "USDTRY": ("USDTRY", "FX_IDC"), "USDZAR": ("USDZAR", "FX_IDC"),
    "USDMXN": ("USDMXN", "FX_IDC"), "USDSEK": ("USDSEK", "FX_IDC"),
    "USDNOK": ("USDNOK", "FX_IDC"), "USDSGD": ("USDSGD", "FX_IDC"),
    "USDHKD": ("USDHKD", "FX_IDC"), "USDCNH": ("USDCNH", "FX_IDC"),
    # ── Energy CFDs (TVC) ────────────────────────────────────────────────────
    "USOIL":  ("USOIL",      "TVC"), "UKOIL":  ("UKOIL",      "TVC"),
    "NATGAS": ("NATURALGAS", "TVC"),
    # ── Commodity CFDs (TVC) ─────────────────────────────────────────────────
    "CORN":    ("CORN",    "TVC"),   "WHEAT":   ("WHEAT",   "TVC"),
    "SOYBEAN": ("SOYBEAN", "TVC"),   "COFFEE":  ("COFFEE",  "TVC"),
    "SUGAR":   ("SUGAR",   "TVC"),   "COTTON":  ("COTTON",  "TVC"),
    "COCOA":   ("COCOA",   "TVC"),
    # ── Crypto (BINANCE) ─────────────────────────────────────────────────────
    "BTCUSD":  ("BTCUSDT",  "BINANCE"), "ETHUSD":  ("ETHUSDT",  "BINANCE"),
    "BNBUSD":  ("BNBUSDT",  "BINANCE"), "XRPUSD":  ("XRPUSDT",  "BINANCE"),
    "SOLUSD":  ("SOLUSDT",  "BINANCE"), "ADAUSD":  ("ADAUSDT",  "BINANCE"),
    "DOGEUSD": ("DOGEUSDT", "BINANCE"), "AVAXUSD": ("AVAXUSDT", "BINANCE"),
    "DOTUSD":  ("DOTUSDT",  "BINANCE"), "LINKUSD": ("LINKUSDT", "BINANCE"),
    "LTCUSD":  ("LTCUSDT",  "BINANCE"), "BCHUSD":  ("BCHUSDT",  "BINANCE"),
    "NEARUSD": ("NEARUSDT", "BINANCE"), "UNIUSD":  ("UNIUSDT",  "BINANCE"),
    "ATOMUSD": ("ATOMUSDT", "BINANCE"), "MATICUSD":("MATICUSDT","BINANCE"),
    # ── Equity Indices (TV native) ────────────────────────────────────────────
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

CRYPTO_SYMBOLS = {"BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD", "BNBUSD"}

# Lazy singleton — TvDatafeed WebSocket connection, reused across requests
_tv_client: "TvDatafeed | None" = None


def _get_tv_client() -> "TvDatafeed | None":
    """Return shared TvDatafeed instance (no credentials = public/guest access)."""
    global _tv_client
    if _tv_client is None and HAS_TV:
        try:
            _tv_client = TvDatafeed()  # no username/password
        except Exception:
            pass
    return _tv_client


def fetch_live_data(symbol: str = "XAUUSD", timeframe: str = "5m", limit: int = 300) -> pd.DataFrame | None:
    """Fetch OHLCV data. Returns DataFrame with columns open/high/low/close/volume.
    Priority: TradingView → ccxt (crypto) → yfinance → None
    """
    # 1. TradingView (real-time, all TV symbols — FX, metals, indices, crypto, commodities)
    if HAS_TV:
        try:
            df = _fetch_tvdatafeed(symbol, timeframe, limit)
            if df is not None and not df.empty:
                return df
        except Exception:
            pass

    # 2. ccxt for crypto (near real-time, direct exchange feed)
    if symbol.upper() in CRYPTO_SYMBOLS and HAS_CCXT:
        try:
            df = _fetch_ccxt(symbol, timeframe, limit)
            if df is not None and not df.empty:
                return df
        except Exception:
            pass

    # 3. yfinance (15-min delayed, reliable for stocks/ETFs)
    if HAS_YF:
        try:
            yf_ticker = SYMBOL_MAP.get(symbol.upper(), symbol)
            df = _fetch_yfinance(yf_ticker, timeframe, limit)
            if df is not None and not df.empty:
                return df
        except Exception:
            pass

    return None


def _fetch_tvdatafeed(symbol: str, timeframe: str, limit: int) -> pd.DataFrame | None:
    """Fetch OHLCV from TradingView WebSocket (no API key required)."""
    entry = _TV_EXCHANGE.get(symbol.upper())
    if not entry:
        return None  # no exchange mapping — fall through to yfinance

    tv_symbol, exchange = entry
    tv = _get_tv_client()
    if tv is None:
        return None

    interval = _TV_INTERVAL.get(timeframe, TvInterval.in_5_minute)
    df = tv.get_hist(
        symbol=tv_symbol,
        exchange=exchange,
        interval=interval,
        n_bars=limit + 10,  # extra bars to account for incomplete current bar
    )
    if df is None or df.empty:
        return None

    df.columns = [c.lower() for c in df.columns]

    needed = ["open", "high", "low", "close", "volume"]
    if any(c not in df.columns for c in needed):
        return None

    df = df[needed].astype(float).tail(limit).reset_index(drop=True)
    return df


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
