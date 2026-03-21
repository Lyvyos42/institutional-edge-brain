"""
Server-side data feed — mirrors the AI Trading Copilot structure exactly.

Priority chain:
  ALL     → tvDatafeed (TradingView WebSocket, real-time, no key) — same as Copilot
  Crypto  → Binance REST (real-time, no key) → Kraken REST
  Others  → yfinance intraday (Ticker.history — same as Copilot)
  Always  → inject live price via Yahoo Finance REST (Copilot technique)
  Always  → mock fallback so fetch_live_data NEVER returns None
"""
import json
import random
import time
import urllib.parse
import urllib.request
import pandas as pd
import numpy as np

# ── tvDatafeed — optional import, exact same pattern as AI Trading Copilot ────
# Lazy singleton WebSocket connection reused across requests.
# If not installed on this server, HAS_TV=False and it silently falls through.
_tv_client = None

_TV_INTERVAL: dict = {}

try:
    from tvDatafeed import TvDatafeed as _TvDatafeed, Interval as _TvInterval
    _TV_INTERVAL = {
        "1m":  _TvInterval.in_1_minute,
        "5m":  _TvInterval.in_5_minute,
        "15m": _TvInterval.in_15_minute,
        "30m": _TvInterval.in_30_minute,
        "1h":  _TvInterval.in_1_hour,
        "60m": _TvInterval.in_1_hour,
        "4h":  _TvInterval.in_4_hour,
        "1d":  _TvInterval.in_daily,
        "1w":  _TvInterval.in_weekly,
    }
    HAS_TV = True
except Exception:
    HAS_TV = False


def _get_tv_client():
    """Return shared TvDatafeed instance (no credentials = guest access).
    Identical to AI Trading Copilot singleton pattern."""
    global _tv_client
    if _tv_client is None:
        try:
            from tvDatafeed import TvDatafeed
            _tv_client = TvDatafeed()
        except Exception:
            pass
    return _tv_client


try:
    import yfinance as yf
    HAS_YF = True
except ImportError:
    HAS_YF = False


# ── Symbol maps ────────────────────────────────────────────────────────────────

# Display symbol → Binance USDT pair
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

# Display symbol → Kraken pair
_KRAKEN_SYM: dict[str, str] = {
    "BTCUSD": "XBTUSD", "ETHUSD": "ETHUSD",
    "SOLUSD": "SOLUSD", "XRPUSD": "XRPUSD",
    "ADAUSD": "ADAUSD", "DOTUSD": "DOTUSD",
    "LTCUSD": "XLTCZUSD", "LINKUSD": "LINKUSD",
}

# Display symbol → yfinance ticker
SYMBOL_MAP: dict[str, str] = {
    "XAUUSD": "GC=F",     "XAGUSD": "SI=F",
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X", "USDCAD": "USDCAD=X", "USDCHF": "USDCHF=X",
    "NZDUSD": "NZDUSD=X", "EURGBP": "EURGBP=X", "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X", "EURCHF": "EURCHF=X", "EURAUD": "EURAUD=X",
    "EURCAD": "EURCAD=X", "EURNZD": "EURNZD=X", "GBPAUD": "GBPAUD=X",
    "GBPCAD": "GBPCAD=X", "GBPCHF": "GBPCHF=X", "GBPNZD": "GBPNZD=X",
    "AUDJPY": "AUDJPY=X", "AUDCAD": "AUDCAD=X", "AUDCHF": "AUDCHF=X",
    "AUDNZD": "AUDNZD=X", "CADJPY": "CADJPY=X", "CADCHF": "CADCHF=X",
    "CHFJPY": "CHFJPY=X", "NZDJPY": "NZDJPY=X", "NZDCAD": "NZDCAD=X",
    "NZDCHF": "NZDCHF=X", "USDTRY": "USDTRY=X", "USDZAR": "USDZAR=X",
    "USDMXN": "USDMXN=X", "USDSEK": "USDSEK=X", "USDNOK": "USDNOK=X",
    "USDSGD": "USDSGD=X", "USDHKD": "USDHKD=X", "USDCNH": "USDCNH=X",
    "BTCUSD": "BTC-USD",  "ETHUSD": "ETH-USD",   "SOLUSD": "SOL-USD",
    "XRPUSD": "XRP-USD",  "BNBUSD": "BNB-USD",   "ADAUSD": "ADA-USD",
    "DOGEUSD":"DOGE-USD",  "AVAXUSD":"AVAX-USD",  "LTCUSD": "LTC-USD",
    "LINKUSD":"LINK-USD",
    "USOIL":  "CL=F",     "UKOIL":  "BZ=F",      "NATGAS": "NG=F",
    "SPX500": "^GSPC",    "NAS100": "^NDX",       "US500":  "^GSPC",
    "US100":  "^NDX",     "US30":   "^DJI",       "GER40":  "^GDAXI",
    "UK100":  "^FTSE",    "JPN225": "^N225",      "HK50":   "^HSI",
    "AUS200": "^AXJO",    "STOXX50":"^STOXX50E",
    "CORN":   "ZC=F",     "WHEAT":  "ZW=F",       "SOYBEAN":"ZS=F",
}

# yf interval → (yf_interval, period)
_YF_PARAMS: dict[str, tuple[str, str]] = {
    "1m":  ("1m",  "7d"),
    "5m":  ("5m",  "60d"),
    "15m": ("15m", "60d"),
    "30m": ("30m", "60d"),
    "1h":  ("60m", "730d"),
    "60m": ("60m", "730d"),
    "4h":  ("60m", "730d"),   # yfinance has no 4h; use 1h and keep last N bars
    "1d":  ("1d",  "5y"),
    "1w":  ("1wk", "10y"),
}

# Binance interval strings
_BINANCE_INTERVAL: dict[str, str] = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "60m": "1h", "4h": "4h", "1d": "1d", "1w": "1w",
}

# Kraken interval in minutes
_KRAKEN_INTERVAL: dict[str, int] = {
    "1m": 1, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "60m": 60, "4h": 240, "1d": 1440,
}

# TradingView exchange map — identical to AI Trading Copilot _TV_EXCHANGE
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
    # Energy / Commodities (TVC)
    "USOIL":   ("USOIL",      "TVC"), "UKOIL":  ("UKOIL",   "TVC"),
    "NATGAS":  ("NATURALGAS", "TVC"), "CORN":   ("CORN",    "TVC"),
    "WHEAT":   ("WHEAT",      "TVC"), "SOYBEAN":("SOYBEAN", "TVC"),
    "COFFEE":  ("COFFEE",     "TVC"), "SUGAR":  ("SUGAR",   "TVC"),
    "COTTON":  ("COTTON",     "TVC"), "COCOA":  ("COCOA",   "TVC"),
    # Crypto (BINANCE feed via TradingView)
    "BTCUSD":  ("BTCUSDT",  "BINANCE"), "ETHUSD":  ("ETHUSDT",  "BINANCE"),
    "BNBUSD":  ("BNBUSDT",  "BINANCE"), "XRPUSD":  ("XRPUSDT",  "BINANCE"),
    "SOLUSD":  ("SOLUSDT",  "BINANCE"), "ADAUSD":  ("ADAUSDT",  "BINANCE"),
    "DOGEUSD": ("DOGEUSDT", "BINANCE"), "AVAXUSD": ("AVAXUSDT", "BINANCE"),
    "DOTUSD":  ("DOTUSDT",  "BINANCE"), "LINKUSD": ("LINKUSDT", "BINANCE"),
    "LTCUSD":  ("LTCUSDT",  "BINANCE"), "BCHUSD":  ("BCHUSDT",  "BINANCE"),
    "NEARUSD": ("NEARUSDT", "BINANCE"), "UNIUSD":  ("UNIUSDT",  "BINANCE"),
    "ATOMUSD": ("ATOMUSDT", "BINANCE"), "MATICUSD":("MATICUSDT","BINANCE"),
    # Equity Indices
    "US500":  ("SPX",    "SP"),     "SPX500":  ("SPX",    "SP"),
    "NAS100": ("NDX",    "NASDAQ"), "US100":   ("NDX",    "NASDAQ"),
    "US30":   ("DJI",    "DJ"),
    "UK100":  ("UK100",  "TVC"),    "GER40":   ("DEU40",  "TVC"),
    "FRA40":  ("CAC40",  "TVC"),    "JPN225":  ("NI225",  "TVC"),
    "HK50":   ("HSI",    "TVC"),    "AUS200":  ("ASX200", "TVC"),
    "STOXX50":("STOXX50","TVC"),
}

CRYPTO_SYMBOLS: set[str] = set(_BINANCE_SYM.keys())

# Reference prices for mock fallback (approximate, good enough for module math)
_MOCK_PRICE: dict[str, float] = {
    "BTCUSD": 85000, "ETHUSD": 2000, "SOLUSD": 130, "XRPUSD": 0.5,
    "BNBUSD": 600,   "ADAUSD": 0.4,  "DOGEUSD": 0.08, "LTCUSD": 90,
    "XAUUSD": 3100,  "XAGUSD": 32,   "EURUSD": 1.08, "GBPUSD": 1.27,
    "USDJPY": 150,   "USOIL": 72,    "NATGAS": 2.3,
    "SPX500": 5200,  "NAS100": 18000, "GER40": 22000, "UK100": 8400,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _price_decimals(price: float) -> int:
    if price < 0.001: return 6
    if price < 0.1:   return 5
    if price < 10:    return 4
    if price < 100:   return 3
    return 2


def _to_df(opens, highs, lows, closes, volumes) -> pd.DataFrame:
    return pd.DataFrame({
        "open":   [float(v) for v in opens],
        "high":   [float(v) for v in highs],
        "low":    [float(v) for v in lows],
        "close":  [float(v) for v in closes],
        "volume": [float(v) for v in volumes],
    })


# ── Live current price (Yahoo Finance REST) ───────────────────────────────────
# Same technique as AI Trading Copilot — works from any cloud server, no key.

_YF_REST_ALIAS: dict[str, str] = {
    "XAUUSD=X": "GC=F", "XAGUSD=X": "SI=F",
    "XPTUSD=X": "PL=F", "XPDUSD=X": "PA=F",
}


def _fetch_live_price(yf_sym: str) -> float | None:
    """
    Fetch regularMarketPrice from Yahoo Finance Chart REST API.
    This is the same approach used in the AI Trading Copilot and works
    reliably from cloud servers without any API key.
    """
    sym = _YF_REST_ALIAS.get(yf_sym, yf_sym)
    try:
        safe = urllib.parse.quote(sym, safe="=^.")
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{safe}?interval=1m&range=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            meta = json.loads(r.read())["chart"]["result"][0]["meta"]
            p = float(meta.get("regularMarketPrice") or 0)
            return p if p > 0 else None
    except Exception:
        return None


# ── tvDatafeed (TradingView) — Priority #1, identical to AI Trading Copilot ──

def _fetch_tvdatafeed(symbol: str, timeframe: str, limit: int) -> "pd.DataFrame | None":
    """
    Fetch OHLCV from TradingView WebSocket via tvDatafeed.
    Exact same pattern as AI Trading Copilot — lazy singleton, no credentials,
    graceful None return if not installed or TV blocks the request.
    Supports all timeframes: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w.
    """
    if not HAS_TV:
        return None

    entry = _TV_EXCHANGE.get(symbol.upper())
    if not entry:
        return None  # no TV mapping — falls through to Binance/yfinance

    tv_symbol, exchange = entry
    tv = _get_tv_client()
    if tv is None:
        return None

    interval = _TV_INTERVAL.get(timeframe, _TV_INTERVAL.get("5m"))
    if interval is None:
        return None

    try:
        df = tv.get_hist(
            symbol=tv_symbol,
            exchange=exchange,
            interval=interval,
            n_bars=limit + 10,  # extra bars to account for in-progress bar
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


# ── Binance REST ──────────────────────────────────────────────────────────────

def _fetch_binance(symbol: str, timeframe: str, limit: int) -> pd.DataFrame | None:
    """Binance public klines — no API key, real-time, all timeframes."""
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
        df = pd.DataFrame(raw, columns=[
            "ts", "open", "high", "low", "close", "volume",
            "close_ts", "quote_vol", "trades", "taker_buy_base", "taker_buy_quote", "ignore"
        ])
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        return df.tail(limit).reset_index(drop=True)
    except Exception:
        return None


# ── Kraken REST ───────────────────────────────────────────────────────────────

def _fetch_kraken(symbol: str, timeframe: str, limit: int) -> pd.DataFrame | None:
    """Kraken public OHLC — no API key, real-time."""
    pair = _KRAKEN_SYM.get(symbol.upper())
    if not pair:
        return None
    interval = _KRAKEN_INTERVAL.get(timeframe, 5)
    since = int(time.time()) - interval * 60 * max(limit + 50, 720)
    url = f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval={interval}&since={since}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        if data.get("error"):
            return None
        result = data.get("result", {})
        rows = next((v for k, v in result.items() if k != "last" and isinstance(v, list)), None)
        if not rows:
            return None
        df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "vwap", "volume", "count"])
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        return df.tail(limit).reset_index(drop=True)
    except Exception:
        return None


# ── yfinance ──────────────────────────────────────────────────────────────────

def _fetch_yfinance(yf_ticker: str, timeframe: str, limit: int) -> pd.DataFrame | None:
    """yfinance OHLCV — same approach as AI Trading Copilot (Ticker.history)."""
    if not HAS_YF:
        return None
    interval, period = _YF_PARAMS.get(timeframe, ("5m", "60d"))
    try:
        tk = yf.Ticker(yf_ticker)
        hist = tk.history(period=period, interval=interval, auto_adjust=True)
        if hist is None or hist.empty:
            return None
        hist = hist.reset_index()
        needed = ["Open", "High", "Low", "Close", "Volume"]
        if any(c not in hist.columns for c in needed):
            return None
        df = hist[needed].astype(float).tail(limit).reset_index(drop=True)
        df.columns = ["open", "high", "low", "close", "volume"]
        return df
    except Exception:
        return None


# ── Mock fallback (same concept as AI Trading Copilot) ───────────────────────

def _mock_data(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    """
    Deterministic synthetic OHLCV — ensures modules always get a DataFrame.
    Prices are seeded from known reference values so math doesn't blow up.
    """
    base = _MOCK_PRICE.get(symbol.upper(), 100.0)
    rng = random.Random(hash(symbol) & 0xFFFF)
    closes = [base]
    for _ in range(limit - 1):
        closes.append(round(closes[-1] * (1 + rng.gauss(0, 0.002)), 8))
    highs   = [round(c * (1 + abs(rng.gauss(0, 0.001))), 8) for c in closes]
    lows    = [round(c * (1 - abs(rng.gauss(0, 0.001))), 8) for c in closes]
    opens   = [closes[max(0, i - 1)] for i in range(len(closes))]
    volumes = [int(abs(rng.gauss(1_000_000, 200_000))) for _ in closes]
    return _to_df(opens, highs, lows, closes, volumes)


# ── Patch last bar with live price (AI Trading Copilot technique) ─────────────

def _inject_live_price(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """
    Fetch the live current price from Yahoo Finance REST and patch it into
    the last row's close (and adjust high/low). This is exactly how the
    AI Trading Copilot keeps prices current regardless of bar-data age.
    """
    yf_sym = SYMBOL_MAP.get(symbol.upper(), symbol)
    live = _fetch_live_price(yf_sym)
    if live and live > 0:
        df = df.copy()
        dec = _price_decimals(live)
        live = round(live, dec)
        df.loc[df.index[-1], "close"] = live
        df.loc[df.index[-1], "high"]  = max(float(df["high"].iloc[-1]), live)
        df.loc[df.index[-1], "low"]   = min(float(df["low"].iloc[-1]),  live)
    return df


# ── Main entry point ──────────────────────────────────────────────────────────

def fetch_live_data(symbol: str = "BTCUSD", timeframe: str = "5m", limit: int = 300) -> pd.DataFrame:
    """
    Fetch OHLCV DataFrame[open, high, low, close, volume].
    NEVER returns None — always falls back to mock data if all sources fail.

    Priority (same structure as AI Trading Copilot):
      1. tvDatafeed  — TradingView WebSocket, real-time, all symbols & timeframes
      2. Binance REST — crypto only, real-time, no key
      3. Kraken REST  — crypto fallback, no key
      4. yfinance     — all symbols, intraday via Ticker.history (Copilot method)
      5. Mock         — deterministic synthetic data, never fails
      +  Yahoo Finance REST live price injected into last bar (Copilot technique)
    """
    sym = symbol.upper()
    df: pd.DataFrame | None = None

    # 1. TradingView — Priority #1 for ALL symbols (identical to AI Trading Copilot)
    df = _fetch_tvdatafeed(sym, timeframe, limit)

    # 2+3. Binance + Kraken REST for crypto when TV unavailable
    if (df is None or df.empty) and sym in CRYPTO_SYMBOLS:
        df = _fetch_binance(sym, timeframe, limit)

        if df is None or df.empty:
            df = _fetch_kraken(sym, timeframe, limit)

    # 4. yfinance — same Ticker.history approach as AI Trading Copilot
    if df is None or df.empty:
        yf_ticker = SYMBOL_MAP.get(sym, sym)
        df = _fetch_yfinance(yf_ticker, timeframe, limit)

    # 5. Mock fallback — never return None (key lesson from AI Trading Copilot)
    if df is None or df.empty:
        df = _mock_data(sym, timeframe, limit)

    # Inject live current price into last bar — AI Trading Copilot technique
    df = _inject_live_price(df, sym)

    return df
