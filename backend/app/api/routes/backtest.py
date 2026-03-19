"""
Backtest OHLCV endpoint.
Returns candlestick data for the chart — real data where available,
synthetic intraday (Brownian bridge from daily) for long 5m/15m periods.
"""
import asyncio
import random
import math
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Query, HTTPException

router = APIRouter(prefix="/api/backtest", tags=["backtest"])
_pool = ThreadPoolExecutor(max_workers=2)

# Max bars yfinance can return per timeframe
_YF_LIMITS = {
    "5m":  "60d",
    "15m": "60d",
    "1h":  "730d",
    "4h":  "730d",   # fetch hourly then resample
    "1d":  "5y",
    "1w":  "5y",
}

_YF_INTERVALS = {
    "5m":  "5m",
    "15m": "15m",
    "1h":  "60m",
    "4h":  "60m",   # resample from hourly
    "1d":  "1d",
    "1w":  "1wk",
}

# Bars per day for synthetic intraday generation
_BARS_PER_DAY = {"5m": 288, "15m": 96}

# Trading sessions (forex trades 5 days/week, equities ~252 days/year)
_FOREX  = {"EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD",
           "EURGBP","EURJPY","GBPJPY","XAUUSD","XAGUSD","USOIL","UKOIL","NATGAS"}


def _fetch_real(symbol: str, timeframe: str):
    """Fetch OHLCV from yfinance. Returns list of {time, open, high, low, close, volume}."""
    try:
        import yfinance as yf
        from app.data.feed import SYMBOL_MAP
    except ImportError:
        return []

    yf_sym   = SYMBOL_MAP.get(symbol.upper(), symbol)
    interval = _YF_INTERVALS.get(timeframe, "1d")
    period   = _YF_LIMITS.get(timeframe, "5y")

    try:
        df = yf.download(yf_sym, period=period, interval=interval,
                         progress=False, auto_adjust=True)
        if df is None or df.empty:
            return []
        if hasattr(df.columns, "get_level_values"):
            df.columns = df.columns.get_level_values(0)
        df = df.reset_index()

        # Rename datetime column
        for col in ("Datetime", "Date"):
            if col in df.columns:
                df = df.rename(columns={col: "dt"})
                break

        if timeframe == "4h":
            df = df.set_index("dt").resample("4h").agg(
                {"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}
            ).dropna().reset_index().rename(columns={"dt":"dt"})

        rows = []
        for _, r in df.iterrows():
            try:
                ts = int(r["dt"].timestamp()) if hasattr(r["dt"], "timestamp") else int(r["dt"])
                rows.append({
                    "time":   ts,
                    "open":   round(float(r["Open"]),  6),
                    "high":   round(float(r["High"]),  6),
                    "low":    round(float(r["Low"]),   6),
                    "close":  round(float(r["Close"]), 6),
                    "volume": int(float(r["Volume"]) if not math.isnan(float(r["Volume"])) else 0),
                })
            except Exception:
                continue
        return rows
    except Exception:
        return []


def _synthetic_daily(symbol: str, days: int = 730) -> list[dict]:
    """Generate synthetic daily OHLCV using GBM seeded from the symbol name."""
    from app.data.feed import SYMBOL_MAP
    import yfinance as yf

    # Try to get a real starting price
    price = 1.0
    yf_sym = SYMBOL_MAP.get(symbol.upper(), symbol)
    try:
        tk = yf.Ticker(yf_sym)
        hist = tk.history(period="5d", interval="1d")
        if not hist.empty:
            price = float(hist["Close"].iloc[-1])
    except Exception:
        pass

    # Fallback known prices
    _SEED_PRICES = {
        "EURUSD": 1.085, "GBPUSD": 1.295, "USDJPY": 148.5,
        "XAUUSD": 3100,  "XAGUSD": 34.5,  "BTCUSD": 83000,
        "ETHUSD": 2000,  "USOIL": 68.0,   "SPX500": 5700,
        "NAS100": 20100, "GER40": 22500,   "UK100": 8250,
    }
    if price <= 0:
        price = _SEED_PRICES.get(symbol.upper(), 100.0)

    rng  = random.Random(sum(ord(c) for c in symbol))
    vol  = 0.012   # daily volatility ~1.2%
    rows = []
    from datetime import date, timedelta
    day = date.today() - timedelta(days=days)

    current = price / (1 + rng.gauss(0, vol)) ** days  # walk backward to seed
    for i in range(days):
        day += timedelta(days=1)
        if day.weekday() >= 5 and symbol.upper() not in _FOREX:
            continue  # skip weekends for equities
        ret   = rng.gauss(0.0001, vol)
        close = max(current * (1 + ret), current * 0.001)
        high  = close * (1 + abs(rng.gauss(0, vol * 0.6)))
        low   = close * (1 - abs(rng.gauss(0, vol * 0.6)))
        open_ = current
        rows.append({
            "time":   int(date(day.year, day.month, day.day).strftime("%s") if hasattr(date, "strftime") else
                         (day - date(1970,1,1)).days * 86400),
            "open":   round(open_, 6),
            "high":   round(max(open_, high, close), 6),
            "low":    round(min(open_, low,  close), 6),
            "close":  round(close, 6),
            "volume": rng.randint(100_000, 50_000_000),
        })
        current = close

    return rows


def _expand_to_intraday(daily_rows: list[dict], bars_per_day: int, symbol: str) -> list[dict]:
    """Synthesize intraday bars from daily OHLCV using a Brownian bridge."""
    rng  = random.Random(sum(ord(c) for c in symbol) + bars_per_day)
    rows = []
    bar_seconds = 86400 // bars_per_day

    for day in daily_rows:
        o, h, l, c = day["open"], day["high"], day["low"], day["close"]
        base_ts = day["time"]
        vol = (h - l) / bars_per_day if h > l else abs(c) * 0.0002

        # Brownian bridge: open → close, clipped to [l, h]
        prices = [o]
        for i in range(1, bars_per_day):
            remaining = bars_per_day - i
            target = c
            drift  = (target - prices[-1]) / remaining
            step   = drift + rng.gauss(0, vol * 0.5)
            p      = max(l, min(h, prices[-1] + step))
            prices.append(p)

        # Build OHLCV bars
        for i in range(bars_per_day):
            p_open  = prices[i - 1] if i > 0 else o
            p_close = prices[i]
            p_high  = max(p_open, p_close) * (1 + abs(rng.gauss(0, 0.0003)))
            p_low   = min(p_open, p_close) * (1 - abs(rng.gauss(0, 0.0003)))
            rows.append({
                "time":   base_ts + i * bar_seconds,
                "open":   round(p_open,  6),
                "high":   round(min(h, p_high),  6),
                "low":    round(max(l, p_low),   6),
                "close":  round(p_close, 6),
                "volume": int((day["volume"] / bars_per_day) * rng.uniform(0.4, 1.8)),
            })
    return rows


def _build_ohlcv(symbol: str, timeframe: str, years: int) -> list[dict]:
    """Full data-building pipeline: real → synthetic fallback."""
    rows = _fetch_real(symbol, timeframe)

    if timeframe in ("5m", "15m"):
        # Real data only covers 60 days — extend to `years` with synthetic
        bars_per_day = _BARS_PER_DAY[timeframe]
        target_days  = years * 365

        # Generate synthetic daily for the full period
        daily = _synthetic_daily(symbol, days=target_days)

        # If real data exists, drop synthetic days that overlap
        if rows:
            cutoff = rows[0]["time"] - 86400
            daily  = [d for d in daily if d["time"] < cutoff]

        synth_intraday = _expand_to_intraday(daily, bars_per_day, symbol)
        rows = synth_intraday + rows

    elif not rows:
        # Fallback: fully synthetic daily/weekly
        daily = _synthetic_daily(symbol, days=years * 365)
        if timeframe == "1w":
            # Resample daily → weekly
            weekly, week_o, week_h, week_l, week_c, week_v, week_ts = [], None, 0, 1e18, 0, 0, 0
            for d in daily:
                if week_o is None:
                    week_o, week_h, week_l, week_ts = d["open"], d["high"], d["low"], d["time"]
                week_h = max(week_h, d["high"])
                week_l = min(week_l, d["low"])
                week_c = d["close"]
                week_v += d["volume"]
                if d["time"] >= week_ts + 5 * 86400:
                    weekly.append({"time":week_ts,"open":week_o,"high":week_h,
                                   "low":week_l,"close":week_c,"volume":week_v})
                    week_o = None; week_h = 0; week_l = 1e18; week_v = 0
            rows = weekly
        else:
            rows = daily

    # Deduplicate & sort
    seen = set()
    out  = []
    for r in sorted(rows, key=lambda x: x["time"]):
        if r["time"] not in seen:
            seen.add(r["time"])
            out.append(r)
    return out


@router.get("/ohlcv")
async def get_ohlcv(
    symbol:    str = Query("EURUSD", description="Display symbol (e.g. EURUSD, XAUUSD)"),
    timeframe: str = Query("1d",     description="5m, 15m, 1h, 4h, 1d, 1w"),
    years:     int = Query(2,        description="Years of history (1–5)", ge=1, le=5),
):
    """Return OHLCV candlestick data for the backtest chart.
    Real data from yfinance where the API supports the period,
    synthetic (Brownian bridge from daily) for long intraday periods.
    """
    tf = timeframe.lower()
    if tf not in _YF_LIMITS:
        raise HTTPException(400, f"Unsupported timeframe. Use: {list(_YF_LIMITS.keys())}")

    loop = asyncio.get_event_loop()
    rows = await loop.run_in_executor(_pool, _build_ohlcv, symbol, tf, years)

    return {
        "symbol":    symbol.upper(),
        "timeframe": tf,
        "years":     years,
        "bars":      len(rows),
        "data":      rows,
    }
