"""
Brain Runner — orchestrates all 12 institutional modules + ensemble model.
Returns a unified signal dict for the API.
"""
import asyncio
import time
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Optional
import structlog

log = structlog.get_logger()

_executor = ThreadPoolExecutor(max_workers=4)

MODULE_TIMEOUT = 8.0  # seconds per module


def _run_with_timeout(fn, *args, timeout=MODULE_TIMEOUT):
    """Run fn(*args) in thread pool with timeout. Returns (result, error_str)."""
    future = _executor.submit(fn, *args)
    try:
        return future.result(timeout=timeout), None
    except FuturesTimeout:
        return None, "timeout"
    except Exception as e:
        return None, str(e)


def _price_decimals(price: float) -> int:
    if price < 0.01:
        return 5
    if price < 10:
        return 4
    if price < 100:
        return 3
    return 2


def run_all_modules(df: pd.DataFrame, symbol: str) -> dict:
    """
    Run all 12 institutional detection modules.
    Returns dict of {module_name: {signal, value, label, detail}}.
    """
    from app.core.entropy_analyzer import EntropyAnalyzer
    from app.core.vpin_calculator import VPINCalculator
    from app.core.volume_accumulation import VolumeAccumulation
    from app.core.fix_time_filter import FixTimeFilter
    from app.core.month_end_flow import MonthEndFlow
    from app.core.iceberg_detector import IcebergDetector
    from app.core.cot_analyzer import COTAnalyzer
    from app.core.correlation_breakdown import CorrelationBreakdown
    from app.core.volume_profile import VolumeProfileAnalyzer
    from app.core.stop_run_profiler import StopRunProfiler
    from app.core.sweep_detector import SweepDetector
    from app.core.volatility_structure import VolatilityStructure

    modules = {
        "entropy":     (EntropyAnalyzer,      "analyze"),
        "vpin":        (VPINCalculator,        "analyze"),
        "vol_accum":   (VolumeAccumulation,    "analyze"),
        "fix_time":    (FixTimeFilter,         "analyze"),
        "month_flow":  (MonthEndFlow,          "analyze"),
        "iceberg":     (IcebergDetector,       "analyze"),
        "cot":         (COTAnalyzer,           "analyze"),
        "correlation": (CorrelationBreakdown,  "analyze_vs_benchmark"),
        "vol_profile": (VolumeProfileAnalyzer, "analyze"),
        "stop_run":    (StopRunProfiler,       "analyze"),
        "sweep":       (SweepDetector,         "analyze"),
        "volatility":  (VolatilityStructure,   "analyze"),
    }

    # Core modules expect uppercase OHLCV columns — normalize once here
    col_map = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    # Modules that require symbol string instead of df, or need both
    COT_MODULES = {"cot"}
    DUAL_ARG_MODULES = {"correlation"}  # (df, symbol)

    results = {}
    for name, (cls, method) in modules.items():
        try:
            instance = cls()
            fn = getattr(instance, method)
            if name in COT_MODULES:
                raw, err = _run_with_timeout(fn, symbol)
            elif name in DUAL_ARG_MODULES:
                raw, err = _run_with_timeout(fn, df, symbol)
            else:
                raw, err = _run_with_timeout(fn, df)
            if err:
                results[name] = {
                    "signal": "NEUTRAL", "value": 0.0, "label": "—",
                    "detail": f"error: {err}", "error": True,
                }
            else:
                results[name] = _normalize_module_result(name, raw)
        except Exception as e:
            results[name] = {
                "signal": "NEUTRAL", "value": 0.0, "label": "—",
                "detail": str(e), "error": True,
            }

    return results


def _normalize_module_result(name: str, raw) -> dict:
    """Normalize any module output format into {signal, value, label, detail}."""
    if raw is None:
        return {"signal": "NEUTRAL", "value": 0.0, "label": "—", "detail": "no data"}

    if isinstance(raw, dict):
        signal = str(raw.get("signal", raw.get("direction", raw.get("bias", "NEUTRAL")))).upper()
        if signal not in ("BUY", "SELL", "BULLISH", "BEARISH", "LONG", "SHORT", "NEUTRAL", "WAIT", "AVOID"):
            signal = "NEUTRAL"
        if signal in ("BULLISH", "LONG"):
            signal = "BUY"
        if signal in ("BEARISH", "SHORT"):
            signal = "SELL"
        if signal in ("WAIT", "AVOID"):
            signal = "NEUTRAL"

        value = float(raw.get("value", raw.get("score", raw.get("strength", raw.get("level", 0.0))) or 0.0))
        label = str(raw.get("label", raw.get("status", raw.get("regime", signal))))
        detail = str(raw.get("detail", raw.get("reason", raw.get("message", raw.get("interpretation", "")))))
        return {"signal": signal, "value": round(value, 4), "label": label, "detail": detail[:200]}

    if isinstance(raw, (tuple, list)) and len(raw) >= 2:
        return {
            "signal": str(raw[0]).upper(),
            "value": float(raw[1]) if isinstance(raw[1], (int, float)) else 0.0,
            "label": str(raw[0]),
            "detail": "",
        }

    if isinstance(raw, (int, float)):
        signal = "BUY" if raw > 0.3 else ("SELL" if raw < -0.3 else "NEUTRAL")
        return {"signal": signal, "value": float(raw), "label": signal, "detail": ""}

    return {"signal": "NEUTRAL", "value": 0.0, "label": str(raw)[:50], "detail": ""}


def run_ensemble(df: pd.DataFrame, module_results: dict) -> dict:
    """Run the ensemble brain model. Returns {signal, confidence, models}."""
    try:
        import torch
        from app.brain.feature_engine import InstitutionalFeatureEngine

        # Feature engine's core modules expect uppercase columns
        col_map = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        from app.brain.model import InstitutionalBrain, TransformerBrain, LiteBrain
        import os

        feature_engine = InstitutionalFeatureEngine()
        features_raw = feature_engine.extract_features(df)
        if features_raw is None:
            raise ValueError("No features extracted")

        # feature_engine returns a dict with 'features' key
        if isinstance(features_raw, dict):
            features_arr = features_raw.get("features")
            if features_arr is None:
                raise ValueError("No features key in result")
        else:
            features_arr = features_raw

        features = np.array(features_arr, dtype=np.float32)
        if features.ndim == 1:
            features = features.reshape(1, 1, -1)
        elif features.ndim == 2:
            features = features.reshape(features.shape[0], 1, features.shape[1])

        weights_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "weights"
        )
        best_model_path = os.path.join(weights_dir, "best_model.pth")

        input_size = features.shape[-1]
        models = {
            "short":  InstitutionalBrain(input_size=input_size),
            "medium": TransformerBrain(input_size=input_size),
            "long":   LiteBrain(input_size=input_size),
        }

        if os.path.exists(best_model_path):
            try:
                state = torch.load(best_model_path, map_location="cpu")
                models["short"].load_state_dict(state)
            except Exception:
                pass

        x = torch.tensor(features, dtype=torch.float32)
        results = {}
        labels = ["SELL", "HOLD", "BUY"]

        for name, model in models.items():
            model.eval()
            with torch.no_grad():
                try:
                    out = model(x)
                    # Some models return (logits, hidden) tuples
                    logits = out[0] if isinstance(out, (tuple, list)) else out
                    probs = torch.softmax(logits, dim=-1)[0]
                    idx = int(probs.argmax().item())
                    conf = float(probs[idx])
                    results[name] = {"signal": labels[idx], "confidence": round(conf, 3)}
                except Exception:
                    results[name] = {"signal": "HOLD", "confidence": 0.33}

        # Weighted vote
        votes = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
        weights = {"short": 0.4, "medium": 0.35, "long": 0.25}
        for name, res in results.items():
            votes[res["signal"]] += weights[name] * res["confidence"]

        final = max(votes, key=votes.get)
        total = sum(votes.values()) or 1
        confidence = round(votes[final] / total, 3)

        return {"signal": final, "confidence": confidence, "models": results}

    except Exception as e:
        log.warning("ensemble_failed", error=str(e))
        return _module_vote_fallback(module_results)


def _module_vote_fallback(module_results: dict) -> dict:
    """Simple vote fallback when ensemble model is unavailable."""
    buy = sum(1 for m in module_results.values() if m.get("signal") == "BUY")
    sell = sum(1 for m in module_results.values() if m.get("signal") == "SELL")
    total = len(module_results) or 1
    if buy > sell:
        return {"signal": "BUY", "confidence": round(buy / total, 2), "models": {}}
    elif sell > buy:
        return {"signal": "SELL", "confidence": round(sell / total, 2), "models": {}}
    return {"signal": "HOLD", "confidence": 0.33, "models": {}}


def compute_levels(df: pd.DataFrame, signal: str, confidence: float) -> dict:
    """Compute entry, SL, TP from recent price action."""
    if df is None or df.empty:
        return {}

    price = float(df["close"].iloc[-1])
    dec = _price_decimals(price)

    highs = df["high"].values[-20:]
    lows = df["low"].values[-20:]
    closes = df["close"].values

    # ATR (14)
    atr = price * 0.008
    if len(closes) > 14:
        trs = []
        for i in range(1, min(15, len(closes))):
            h = float(df["high"].iloc[-i])
            l = float(df["low"].iloc[-i])
            pc = float(closes[-i - 1])
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        if trs:
            atr = np.mean(trs)

    support = round(float(np.min(lows)), dec)
    resistance = round(float(np.max(highs)), dec)
    risk = atr * 1.5
    rr = 2.0 + confidence

    if signal == "BUY":
        entry = round(price, dec)
        sl = round(entry - risk, dec)
        tp = round(entry + risk * rr, dec)
    elif signal == "SELL":
        entry = round(price, dec)
        sl = round(entry + risk, dec)
        tp = round(entry - risk * rr, dec)
    else:
        entry = round(price, dec)
        sl = round(entry - risk, dec)
        tp = round(entry + risk, dec)

    rr_actual = round(abs(tp - entry) / abs(sl - entry), 2) if abs(sl - entry) > 0 else 0

    return {
        "price": round(price, dec),
        "entry": entry,
        "stop_loss": sl,
        "take_profit": tp,
        "risk_reward": rr_actual,
        "support": support,
        "resistance": resistance,
        "atr": round(atr, dec),
    }


async def analyze_symbol(symbol: str, timeframe: str = "5m") -> dict:
    """Main entry point. Fetches data, runs all modules + ensemble, returns full result."""
    from app.data.feed import fetch_live_data

    t0 = time.monotonic()
    loop = asyncio.get_event_loop()

    # Fetch data in thread (yfinance is blocking)
    df = await loop.run_in_executor(_executor, fetch_live_data, symbol, timeframe, 300)

    if df is None or df.empty:
        return {"error": "No data available for this symbol", "symbol": symbol}

    # Run modules and ensemble in thread pool
    module_results = await loop.run_in_executor(_executor, run_all_modules, df, symbol)
    ensemble = await loop.run_in_executor(_executor, run_ensemble, df, module_results)
    levels = compute_levels(df, ensemble["signal"], ensemble["confidence"])

    elapsed = round((time.monotonic() - t0) * 1000)

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "signal": ensemble["signal"],
        "confidence": ensemble["confidence"],
        "ensemble": ensemble,
        "levels": levels,
        "modules": module_results,
        "latency_ms": elapsed,
    }
