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

MODULE_TIMEOUT = 5.0   # seconds per module (reduced to stay within Render limits)
ANALYZE_TIMEOUT = 25.0  # hard cap on full analysis

# ── Singleton caches — loaded ONCE, reused on every request ───────────────────
# Avoids OOM-killing Render's 512MB free dyno on repeated torch model loads.
_feature_engine = None
_torch_models: dict = {}
_torch_labels = ["SELL", "HOLD", "BUY"]
_torch_weights = {"short": 0.4, "medium": 0.35, "long": 0.25}


def _get_feature_engine():
    global _feature_engine
    if _feature_engine is None:
        try:
            from app.brain.feature_engine import InstitutionalFeatureEngine
            _feature_engine = InstitutionalFeatureEngine()
        except Exception as e:
            log.warning("feature_engine_init_failed", error=str(e))
    return _feature_engine


def _get_torch_models(input_size: int) -> dict:
    """Load torch models once and cache them. Skip gracefully if torch unavailable."""
    global _torch_models
    if _torch_models:
        return _torch_models
    try:
        import os
        import torch
        from app.brain.model import InstitutionalBrain, TransformerBrain, LiteBrain
        weights_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "weights"
        )
        best_model_path = os.path.join(weights_dir, "best_model.pth")
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
        _torch_models = models
    except Exception as e:
        log.warning("torch_models_init_failed", error=str(e))
    return _torch_models


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


_SIGNAL_ALIASES = {
    "BULLISH": "BUY", "LONG": "BUY", "HIGH": "BUY",
    "BULLISH_REVERSAL": "BUY", "ACCUMULATION": "BUY",
    "BEARISH": "SELL", "SHORT": "SELL", "BEARISH_REVERSAL": "SELL",
    "DISTRIBUTION": "SELL",
    "WAIT": "NEUTRAL", "AVOID": "NEUTRAL", "CHOPPY_AVOID": "NEUTRAL",
    "LOW": "NEUTRAL", "MODERATE": "NEUTRAL", "RANGE_TRADING": "NEUTRAL",
    "MEAN_REVERSION": "NEUTRAL", "TRENDING": "NEUTRAL", "HOLD": "NEUTRAL",
}

# Module-specific extractors — called before generic fallback
_MODULE_EXTRACTORS = {
    "entropy": lambda r: {
        "signal": _resolve_signal(r.get("signal", "NEUTRAL")),
        "value": float(r.get("entropy_score", r.get("shannon", 0.0)) or 0.0),
        "label": str(r.get("signal", "—")),
        "detail": f"Hurst={r.get('hurst',0):.2f} chaos={r.get('is_chaos',False)} ghost={r.get('is_ghost_algo',False)}",
    },
    "vpin": lambda r: {
        "signal": _resolve_signal(r.get("direction_hint", r.get("signal", "NEUTRAL"))),
        "value": float(r.get("vpin", 0.0) or 0.0),
        "label": str(r.get("signal", "—")),
        "detail": f"VPIN={r.get('vpin',0):.3f} toxicity={r.get('is_high_toxicity',False)} smart={r.get('smart_money_active',False)}",
    },
    "vol_accum": lambda r: {
        "signal": _resolve_signal(r.get("signal", "NEUTRAL")),
        "value": float(r.get("accumulation_score", r.get("score", 0.0)) or 0.0),
        "label": str(r.get("pattern", r.get("signal", "—"))),
        "detail": str(r.get("interpretation", r.get("detail", "")))[:150],
    },
    "fix_time": lambda r: {
        "signal": _resolve_signal(r.get("signal", "NEUTRAL")),
        "value": float(r.get("strength", r.get("score", 0.0)) or 0.0),
        "label": str(r.get("signal", "—")),
        "detail": str(r.get("detail", r.get("reason", "")))[:150],
    },
    "month_flow": lambda r: {
        "signal": _resolve_signal(r.get("signal", "NEUTRAL")),
        "value": float(r.get("strength", r.get("score", 0.0)) or 0.0),
        "label": str(r.get("signal", "—")),
        "detail": str(r.get("detail", r.get("reason", "")))[:150],
    },
    "iceberg": lambda r: {
        "signal": _resolve_signal(r.get("signal", "NEUTRAL")),
        "value": float(r.get("confidence", r.get("score", 0.0)) or 0.0),
        "label": str(r.get("signal", "—")),
        "detail": str(r.get("detail", r.get("interpretation", "")))[:150],
    },
    "cot": lambda r: {
        "signal": _resolve_signal(r.get("signal", "NEUTRAL")),
        "value": float(r.get("net_position", r.get("score", 0.0)) or 0.0),
        "label": str(r.get("signal", "—")),
        "detail": str(r.get("detail", r.get("interpretation", "")))[:150],
    },
    "correlation": lambda r: {
        "signal": _resolve_signal(r.get("signal", "NEUTRAL")),
        "value": float(r.get("score", r.get("strength", 0.0)) or 0.0),
        "label": str(r.get("signal", "—")),
        "detail": str(r.get("detail", r.get("interpretation", "")))[:150],
    },
    "vol_profile": lambda r: {
        "signal": _resolve_signal(r.get("signal", "NEUTRAL")),
        "value": float(r.get("vpoc", r.get("value_area_low", 0.0)) or 0.0),
        "label": str(r.get("signal", "—")),
        "detail": str(r.get("detail", r.get("interpretation", "")))[:150],
    },
    "stop_run": lambda r: {
        "signal": _resolve_signal(r.get("signal", "NEUTRAL")),
        "value": float(r.get("score", r.get("strength", 0.0)) or 0.0),
        "label": str(r.get("signal", "—")),
        "detail": str(r.get("detail", r.get("interpretation", "")))[:150],
    },
    "sweep": lambda r: {
        "signal": _resolve_signal(r.get("primary_signal", r.get("signal", "NEUTRAL"))),
        "value": float(r.get("confidence", r.get("aggression_score", 0.0)) or 0.0),
        "label": str(r.get("primary_signal", "—")),
        "detail": f"conf={r.get('confidence',0):.2f} aggr={r.get('aggression_score',0):.2f}",
    },
    "volatility": lambda r: {
        "signal": _resolve_signal(r.get("signal", "NEUTRAL")),
        "value": float(r.get("atr_value", 0.0) or 0.0),
        "label": str(r.get("signal", "—")),
        "detail": str(r.get("recommendation", ""))[:150],
    },
}


def _resolve_signal(raw_signal: str) -> str:
    s = str(raw_signal).upper().strip()
    return _SIGNAL_ALIASES.get(s, "NEUTRAL" if s not in ("BUY", "SELL", "NEUTRAL") else s)


def _normalize_module_result(name: str, raw) -> dict:
    """Normalize module output into {signal, value, label, detail}."""
    if raw is None:
        return {"signal": "NEUTRAL", "value": 0.0, "label": "—", "detail": "no data"}

    if isinstance(raw, dict):
        # Use module-specific extractor if available
        extractor = _MODULE_EXTRACTORS.get(name)
        if extractor:
            try:
                result = extractor(raw)
                return result
            except Exception:
                pass
        # Generic fallback
        sig_raw = raw.get("signal", raw.get("direction", raw.get("bias", "NEUTRAL")))
        signal = _resolve_signal(str(sig_raw))
        value = 0.0
        for k in ("value", "score", "strength", "level", "confidence", "entropy_score", "vpin"):
            v = raw.get(k)
            if v is not None:
                try:
                    value = float(v)
                    break
                except (TypeError, ValueError):
                    pass
        label = str(raw.get("label", raw.get("status", raw.get("signal", signal))))
        detail = str(raw.get("detail", raw.get("reason", raw.get("recommendation", raw.get("interpretation", "")))))
        return {"signal": signal, "value": round(value, 4), "label": label, "detail": detail[:200]}

    if isinstance(raw, (tuple, list)) and len(raw) >= 2:
        return {"signal": _resolve_signal(str(raw[0])), "value": float(raw[1]) if isinstance(raw[1], (int, float)) else 0.0, "label": str(raw[0]), "detail": ""}

    if isinstance(raw, (int, float)):
        signal = "BUY" if raw > 0.3 else ("SELL" if raw < -0.3 else "NEUTRAL")
        return {"signal": signal, "value": float(raw), "label": signal, "detail": ""}

    return {"signal": "NEUTRAL", "value": 0.0, "label": str(raw)[:50], "detail": ""}


def run_ensemble(df: pd.DataFrame, module_results: dict) -> dict:
    """Run the ensemble brain model using cached singletons. Returns {signal, confidence, models}."""
    try:
        import torch

        col_map = {"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"}
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

        # Use cached feature engine — no re-instantiation on every request
        feature_engine = _get_feature_engine()
        if feature_engine is None:
            raise ValueError("Feature engine unavailable")

        features_raw = feature_engine.extract_features(df)
        if features_raw is None:
            raise ValueError("No features extracted")

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

        input_size = features.shape[-1]

        # Use cached torch models — loaded once, never reloaded
        models = _get_torch_models(input_size)
        if not models:
            raise ValueError("Torch models unavailable")

        x = torch.tensor(features, dtype=torch.float32)
        results = {}

        for name, model in models.items():
            model.eval()
            with torch.no_grad():
                try:
                    out = model(x)
                    logits = out[0] if isinstance(out, (tuple, list)) else out
                    probs = torch.softmax(logits, dim=-1)[0]
                    idx = int(probs.argmax().item())
                    conf = float(probs[idx])
                    results[name] = {"signal": _torch_labels[idx], "confidence": round(conf, 3)}
                except Exception:
                    results[name] = {"signal": "HOLD", "confidence": 0.33}

        votes = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
        for name, res in results.items():
            votes[res["signal"]] += _torch_weights.get(name, 0.33) * res["confidence"]

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

    # Fetch data — never returns None (mock fallback in feed.py)
    df = await loop.run_in_executor(_executor, fetch_live_data, symbol, timeframe, 300)

    if df is None or df.empty:
        return {"error": "No data available for this symbol", "symbol": symbol}

    # Run modules with hard timeout to prevent Render dyno OOM-kill
    try:
        module_results = await asyncio.wait_for(
            loop.run_in_executor(_executor, run_all_modules, df, symbol),
            timeout=ANALYZE_TIMEOUT,
        )
    except asyncio.TimeoutError:
        log.warning("modules_timeout", symbol=symbol)
        module_results = {
            name: {"signal": "NEUTRAL", "value": 0.0, "label": "—", "detail": "timeout"}
            for name in ["entropy","vpin","vol_accum","fix_time","month_flow",
                         "iceberg","cot","correlation","vol_profile","stop_run","sweep","volatility"]
        }

    # Ensemble with hard timeout — falls back to module vote on any failure
    try:
        ensemble = await asyncio.wait_for(
            loop.run_in_executor(_executor, run_ensemble, df, module_results),
            timeout=15.0,
        )
    except asyncio.TimeoutError:
        log.warning("ensemble_timeout", symbol=symbol)
        ensemble = _module_vote_fallback(module_results)

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
