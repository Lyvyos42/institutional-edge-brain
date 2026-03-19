"""
INSTITUTIONAL EDGE - ENHANCED FEATURE ENGINE V2
================================================
Combines all 12 institutional detection methods into a unified 40-feature vector.
With timeout protection to prevent UI freezes.
"""

import numpy as np
import pandas as pd
from typing import Dict, List
import concurrent.futures

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
# Phase 26: Signal Fusion
from app.core.correlation_engine import topology
from app.core.gamma_engine import gamma_engine

# Module timeout in seconds (prevents any single module from hanging forever)
MODULE_TIMEOUT = 5.0

class InstitutionalFeatureEngineV2:
    """
    Enhanced feature extraction engine with 14 institutional methods (12 Core + Topology + Gamma).
    Now with timeout protection on each module.
    """

    def __init__(self):
        """Initialize all 12 detectors."""
        # Original 7 detectors
        self.entropy = EntropyAnalyzer()
        self.vpin = VPINCalculator()
        self.volume = VolumeAccumulation()
        self.fix_time = FixTimeFilter()
        self.month_end = MonthEndFlow()
        self.iceberg = IcebergDetector()
        self.cot = COTAnalyzer()

        # New 5 advanced detectors
        self.correlation = CorrelationBreakdown()
        self.volume_profile = VolumeProfileAnalyzer()
        self.stop_run = StopRunProfiler()
        self.sweep = SweepDetector()
        self.volatility = VolatilityStructure()

        # Feature dimensions
        self.num_features = 40

    def _run_with_timeout(self, func, timeout=MODULE_TIMEOUT, default=None):
        """Run a function with timeout protection."""
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func)
                return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            print(f"[TIMEOUT] Module {func.__name__ if hasattr(func, '__name__') else 'unknown'} timed out after {timeout}s")
            return default
        except Exception as e:
            print(f"[ERROR] Module error: {e}")
            return default

    def extract_features(self, df: pd.DataFrame, symbol: str = "EURUSD") -> Dict:
        """
        Extract all institutional features from OHLCV data.
        Each module has timeout protection to prevent freezing.

        Returns:
            Dict with:
            - features: numpy array of shape (40,)
            - signals: Dict of individual detector signals
            - meta: Combined analysis and recommendations
        """
        features = np.zeros(self.num_features)
        signals = {}

        # Default results for each module
        default_entropy = {'shannon': 0.5, 'permutation': 0.5, 'is_collapse': False, 'is_chaos': False}
        default_vpin = {'vpin': 0.5, 'smart_money_active': False, 'direction_hint': 'NEUTRAL', 'signal': 'NEUTRAL'}
        default_vol = {'institutional_activity': 0.0, 'absorption': {'is_absorption': False}, 'climax': {'is_climax': False}, 'ad_analysis': {'signal': 'NEUTRAL'}, 'composite_signal': 'NEUTRAL'}
        default_fix = {'fix_status': {'is_danger_zone': False, 'is_reversal_zone': False, 'action': 'NEUTRAL'}, 'session': {'session': 'UNKNOWN'}}
        default_month = {'adjusted_confidence': 0.0, 'window': {'multiplier': 1.0}, 'flow': {'flow_direction': 'NEUTRAL'}, 'final_signal': 'NEUTRAL'}
        default_iceberg = {'iceberg_detected': False, 'absorption': {'is_absorption': False}, 'signal': 'NEUTRAL'}
        default_cot = {'positioning': {'historical_percentile': 0.5, 'extreme_positioning': False, 'is_extreme_long': False}, 'final_confidence': 0.5}
        default_corr = {'signal': 'NEUTRAL', 'confidence': 0.5}
        default_vp = {'signal': 'NEUTRAL', 'vpoc': 0.0, 'va_high': 0.0, 'va_low': 0.0}
        default_sr = {'signal': 'NEUTRAL', 'current_status': {'in_progress': False}}
        default_sweep = {'primary_signal': 'NEUTRAL', 'aggression_score': 0.0}
        default_volatility = {'regime': {'regime': 'NORMAL'}, 'atr': {'atr_value': 0.0}}

        # =====================================================================
        # 1. ENTROPY FEATURES (indices 0-2) - Usually fast
        # =====================================================================
        try:
            entropy_result = self._run_with_timeout(
                lambda: self.entropy.analyze(df),
                timeout=2.0,
                default=default_entropy
            ) or default_entropy
            features[0] = entropy_result.get('shannon', 0.5)
            features[1] = entropy_result.get('permutation', 0.5)
            features[2] = 1.0 if entropy_result.get('is_collapse') else (0.0 if entropy_result.get('is_chaos') else 0.5)
            signals['entropy'] = entropy_result
        except Exception as e:
            print(f"[ENGINE] Entropy error: {e}")
            signals['entropy'] = default_entropy

        # =====================================================================
        # 2. VPIN FEATURES (indices 3-5) - Usually fast
        # =====================================================================
        try:
            vpin_result = self._run_with_timeout(
                lambda: self.vpin.analyze(df),
                timeout=2.0,
                default=default_vpin
            ) or default_vpin
            features[3] = vpin_result.get('vpin', 0.5)
            features[4] = 1.0 if vpin_result.get('smart_money_active') else 0.0
            features[5] = {'BULLISH': 1.0, 'BEARISH': -1.0, 'NEUTRAL': 0.0}.get(vpin_result.get('direction_hint', 'NEUTRAL'), 0.0)
            signals['vpin'] = vpin_result
        except Exception as e:
            print(f"[ENGINE] VPIN error: {e}")
            signals['vpin'] = default_vpin

        # =====================================================================
        # 3. VOLUME ACCUMULATION FEATURES (indices 6-9)
        # =====================================================================
        try:
            vol_result = self._run_with_timeout(
                lambda: self.volume.analyze(df),
                timeout=2.0,
                default=default_vol
            ) or default_vol
            features[6] = vol_result.get('institutional_activity', 0.0)
            features[7] = 1.0 if vol_result.get('absorption', {}).get('is_absorption') else 0.0
            features[8] = 1.0 if vol_result.get('climax', {}).get('is_climax') else 0.0
            ad_signal = vol_result.get('ad_analysis', {}).get('signal', 'NEUTRAL')
            features[9] = 1.0 if 'ACCUMULATION' in ad_signal else (-1.0 if 'DISTRIBUTION' in ad_signal else 0.0)
            signals['volume'] = vol_result
        except Exception as e:
            print(f"[ENGINE] Volume error: {e}")
            signals['volume'] = default_vol

        # =====================================================================
        # 4. FIX TIME FEATURES (indices 10-12) - Usually fast
        # =====================================================================
        try:
            fix_result = self._run_with_timeout(
                lambda: self.fix_time.analyze(df),
                timeout=2.0,
                default=default_fix
            ) or default_fix
            features[10] = 1.0 if fix_result.get('fix_status', {}).get('is_danger_zone') else 0.0
            features[11] = 1.0 if fix_result.get('fix_status', {}).get('is_reversal_zone') else 0.0
            session_score = {'LONDON_NY_OVERLAP': 1.0, 'LONDON_MORNING': 0.8, 'NY_AFTERNOON': 0.6, 'ASIAN': 0.4, 'LATE_NY': 0.2}
            features[12] = session_score.get(fix_result.get('session', {}).get('session', 'UNKNOWN'), 0.5)
            signals['fix_time'] = fix_result
        except Exception as e:
            print(f"[ENGINE] Fix time error: {e}")
            signals['fix_time'] = default_fix

        # =====================================================================
        # 5. MONTH-END FLOW FEATURES (indices 13-15)
        # =====================================================================
        try:
            month_result = self._run_with_timeout(
                lambda: self.month_end.analyze(df),
                timeout=2.0,
                default=default_month
            ) or default_month
            features[13] = month_result.get('adjusted_confidence', 0.0)
            features[14] = month_result.get('window', {}).get('multiplier', 1.0) / 5.0
            flow_dir = month_result.get('flow', {}).get('flow_direction', 'NEUTRAL')
            features[15] = {'BUY': 1.0, 'SELL': -1.0, 'NEUTRAL': 0.0, 'UNKNOWN': 0.0}.get(flow_dir, 0.0)
            signals['month_end'] = month_result
        except Exception as e:
            print(f"[ENGINE] Month-end error: {e}")
            signals['month_end'] = default_month

        # =====================================================================
        # 6. ICEBERG FEATURES (indices 16-18)
        # =====================================================================
        try:
            iceberg_result = self._run_with_timeout(
                lambda: self.iceberg.analyze(df),
                timeout=2.0,
                default=default_iceberg
            ) or default_iceberg
            features[16] = 1.0 if iceberg_result.get('iceberg_detected') else 0.0
            features[17] = 1.0 if iceberg_result.get('absorption', {}).get('is_absorption') else 0.0
            ice_signal = iceberg_result.get('signal', 'NEUTRAL')
            features[18] = 1.0 if 'BULLISH' in ice_signal else (-1.0 if 'BEARISH' in ice_signal else 0.0)
            signals['iceberg'] = iceberg_result
        except Exception as e:
            print(f"[ENGINE] Iceberg error: {e}")
            signals['iceberg'] = default_iceberg

        # =====================================================================
        # 7. COT FEATURES (indices 19-21) - Can be slow (external data)
        # =====================================================================
        try:
            cot_result = self._run_with_timeout(
                lambda: self.cot.analyze(symbol),
                timeout=3.0,  # Slightly longer for external data
                default=default_cot
            ) or default_cot
            features[19] = cot_result.get('positioning', {}).get('historical_percentile', 0.5)
            features[20] = cot_result.get('final_confidence', 0.5)
            pos = cot_result.get('positioning', {})
            if pos.get('extreme_positioning'):
                features[21] = 1.0 if pos.get('is_extreme_long') else -1.0
            else:
                features[21] = (pos.get('historical_percentile', 0.5) - 0.5) * 2
            signals['cot'] = cot_result
        except Exception as e:
            print(f"[ENGINE] COT error: {e}")
            signals['cot'] = default_cot

        # =====================================================================
        # 8. CORRELATION FEATURES (indices 22-25)
        # =====================================================================
        try:
            corr_features = self._run_with_timeout(
                lambda: self.correlation.get_features(df, symbol),
                timeout=2.0,
                default=np.zeros(4)
            )
            if corr_features is not None:
                features[22:26] = corr_features[:4] if len(corr_features) >= 4 else np.zeros(4)
            signals['correlation'] = self._run_with_timeout(
                lambda: self.correlation.analyze_vs_benchmark(df, symbol),
                timeout=2.0,
                default=default_corr
            ) or default_corr
        except Exception as e:
            print(f"[ENGINE] Correlation error: {e}")
            signals['correlation'] = default_corr

        # =====================================================================
        # 9. VOLUME PROFILE FEATURES (indices 26-29)
        # =====================================================================
        try:
            vp_features = self._run_with_timeout(
                lambda: self.volume_profile.get_features(df),
                timeout=2.0,
                default=np.zeros(4)
            )
            if vp_features is not None:
                features[26:30] = vp_features[:4] if len(vp_features) >= 4 else np.zeros(4)
            signals['volume_profile'] = self._run_with_timeout(
                lambda: self.volume_profile.analyze(df),
                timeout=2.0,
                default=default_vp
            ) or default_vp
        except Exception as e:
            print(f"[ENGINE] Volume profile error: {e}")
            signals['volume_profile'] = default_vp

        # =====================================================================
        # 10. STOP-RUN FEATURES (indices 30-33)
        # =====================================================================
        try:
            sr_features = self._run_with_timeout(
                lambda: self.stop_run.get_features(df),
                timeout=2.0,
                default=np.zeros(4)
            )
            if sr_features is not None:
                features[30:34] = sr_features[:4] if len(sr_features) >= 4 else np.zeros(4)
            signals['stop_run'] = self._run_with_timeout(
                lambda: self.stop_run.analyze(df),
                timeout=2.0,
                default=default_sr
            ) or default_sr
        except Exception as e:
            print(f"[ENGINE] Stop-run error: {e}")
            signals['stop_run'] = default_sr

        # =====================================================================
        # 11. SWEEP FEATURES (indices 34-37)
        # =====================================================================
        try:
            sweep_features = self._run_with_timeout(
                lambda: self.sweep.get_features(df),
                timeout=2.0,
                default=np.zeros(4)
            )
            if sweep_features is not None:
                features[34:38] = sweep_features[:4] if len(sweep_features) >= 4 else np.zeros(4)
            signals['sweep'] = self._run_with_timeout(
                lambda: self.sweep.analyze(df),
                timeout=2.0,
                default=default_sweep
            ) or default_sweep
        except Exception as e:
            print(f"[ENGINE] Sweep error: {e}")
            signals['sweep'] = default_sweep

        # =====================================================================
        # 12. VOLATILITY FEATURES (indices 38-39)
        # =====================================================================
        try:
            vol_struct_features = self._run_with_timeout(
                lambda: self.volatility.get_features(df),
                timeout=2.0,
                default=np.zeros(2)
            )
            if vol_struct_features is not None:
                features[38:40] = vol_struct_features[:2] if len(vol_struct_features) >= 2 else np.zeros(2)
            signals['volatility'] = self._run_with_timeout(
                lambda: self.volatility.analyze(df),
                timeout=2.0,
                default=default_volatility
            ) or default_volatility
        except Exception as e:
            print(f"[ENGINE] Volatility error: {e}")
            signals['volatility'] = default_volatility

        # =====================================================================
        # 13. TOPOLOGY & GAMMA FUSION (Phase 26) - Quick lookups
        # =====================================================================
        topo_stress = 0.0
        try:
            snap = topology.get_topology_snapshot()
            if snap and 'nodes' in snap:
                s_vals = [n['stress'] for n in snap['nodes']]
                if s_vals:
                    topo_stress = sum(s_vals) / len(s_vals)
        except:
            pass

        gamma_signal = 'NEUTRAL'
        try:
            current_price = df['Close'].iloc[-1] if not df.empty else 0
            g_data = gamma_engine.get_gamma_state()
            relevant_key = next((k for k in g_data.keys() if k in symbol or symbol in k), None)

            if relevant_key and current_price > 0:
                levels = g_data[relevant_key]
                cw = levels.get('call_wall', 999999)
                pw = levels.get('put_wall', 0)
                zg = levels.get('zero_gamma', 0)

                if current_price >= cw * 0.9985:
                    gamma_signal = 'CALL_WALL_RESISTANCE'
                elif current_price <= pw * 1.0015:
                    gamma_signal = 'PUT_WALL_SUPPORT'
                elif zg > 0 and abs(current_price - zg) / current_price < 0.0015:
                    gamma_signal = 'ZERO_GAMMA_pinning'
        except:
            pass

        signals['topology'] = {'stress': topo_stress, 'mode': 'CRITICAL' if topo_stress > 0.75 else 'NORMAL'}
        signals['gamma'] = {'signal': gamma_signal}

        # =====================================================================
        # META ANALYSIS - Combine all signals
        # =====================================================================
        bullish_score = 0.0
        bearish_score = 0.0

        # Aggregate directional signals
        directional_indices = [5, 9, 15, 18, 21, 25, 29, 33, 37]
        for idx in directional_indices:
            if idx < len(features):
                if features[idx] > 0:
                    bullish_score += abs(features[idx])
                elif features[idx] < 0:
                    bearish_score += abs(features[idx])

        # Quality filters - use safe access
        entropy_result = signals.get('entropy', default_entropy)
        fix_result = signals.get('fix_time', default_fix)
        vpin_result = signals.get('vpin', default_vpin)
        vol_result = signals.get('volume', default_vol)
        cot_result = signals.get('cot', default_cot)

        avoid_trade = (
            fix_result.get('fix_status', {}).get('is_danger_zone', False) or
            entropy_result.get('is_chaos', False) or
            signals.get('volatility', {}).get('regime', {}).get('regime') == 'HIGH_VOL' or
            topo_stress > 0.75
        )

        institutional_active = (
            vpin_result.get('smart_money_active', False) or
            vol_result.get('institutional_activity', 0) > 0.5 or
            signals.get('sweep', {}).get('aggression_score', 0) > 0.5 or
            (gamma_signal != 'NEUTRAL')
        )

        extreme_positioning = (
            cot_result.get('positioning', {}).get('extreme_positioning', False) or
            signals.get('stop_run', {}).get('current_status', {}).get('in_progress', False) or
            'WALL' in gamma_signal
        )

        high_conviction = institutional_active and extreme_positioning
        net_direction = bullish_score - bearish_score

        # Generate meta signal
        if avoid_trade:
            meta_signal = 'AVOID'
            meta_confidence = 0.0
            if topo_stress > 0.75:
                meta_signal = 'CRASH_WARNING'

        elif signals.get('stop_run', {}).get('signal') == 'BUY_OPPORTUNITY':
            meta_signal = 'STRONG_BUY'
            meta_confidence = 0.85
        elif signals.get('stop_run', {}).get('signal') == 'SELL_OPPORTUNITY':
            meta_signal = 'STRONG_SELL'
            meta_confidence = 0.85

        elif 'CALL_WALL' in gamma_signal:
            meta_signal = 'SELL_SCALP'
            meta_confidence = 0.80
            net_direction = -1.0
        elif 'PUT_WALL' in gamma_signal:
            meta_signal = 'BUY_SCALP'
            meta_confidence = 0.80
            net_direction = 1.0

        elif high_conviction:
            if net_direction > 0.5:
                meta_signal = 'STRONG_BUY'
                meta_confidence = min(0.9, 0.5 + net_direction * 0.1)
            elif net_direction < -0.5:
                meta_signal = 'STRONG_SELL'
                meta_confidence = min(0.9, 0.5 + abs(net_direction) * 0.1)
            else:
                meta_signal = 'WAIT'
                meta_confidence = 0.4
        else:
            if net_direction > 1.0:
                meta_signal = 'BUY'
                meta_confidence = 0.60 + (0.05 * (net_direction - 1.0))
            elif net_direction < -1.0:
                meta_signal = 'SELL'
                meta_confidence = 0.60 + (0.05 * (abs(net_direction) - 1.0))
            else:
                meta_signal = 'NEUTRAL'
                meta_confidence = 0.5

        meta = {
            'signal': meta_signal,
            'confidence': meta_confidence,
            'net_direction': net_direction,
            'bullish_score': bullish_score,
            'bearish_score': bearish_score,
            'avoid_trade': avoid_trade,
            'high_conviction': high_conviction,
            'institutional_active': institutional_active,
            'extreme_positioning': extreme_positioning
        }

        return {
            'features': features,
            'signals': signals,
            'meta': meta
        }

    def get_feature_names(self) -> List[str]:
        """Return names for all 40 features."""
        return [
            # Entropy (0-2)
            'entropy_shannon', 'entropy_permutation', 'entropy_state',
            # VPIN (3-5)
            'vpin_value', 'vpin_smart_money', 'vpin_direction',
            # Volume (6-9)
            'vol_institutional', 'vol_absorption', 'vol_climax', 'vol_accum_dist',
            # Fix Time (10-12)
            'fix_danger', 'fix_reversal', 'session_quality',
            # Month-End (13-15)
            'month_confidence', 'month_intensity', 'month_direction',
            # Iceberg (16-18)
            'iceberg_detected', 'iceberg_absorption', 'iceberg_direction',
            # COT (19-21)
            'cot_percentile', 'cot_confidence', 'cot_direction',
            # Correlation (22-25)
            'corr_autocorr', 'corr_short_return', 'corr_long_return', 'corr_confidence',
            # Volume Profile (26-29)
            'vp_position', 'vp_vpoc_dist', 'vp_near_lvn', 'vp_va_width',
            # Stop-Run (30-33)
            'sr_in_progress', 'sr_extension', 'sr_confidence', 'sr_frequency',
            # Sweep (34-37)
            'sweep_aggression', 'sweep_volume_ratio', 'sweep_direction', 'sweep_liquidity',
            # Volatility (38-39)
            'vol_regime', 'vol_ratio'
        ]

    def get_summary(self, result: Dict) -> str:
        """Generate human-readable summary."""
        meta = result['meta']
        signals = result['signals']

        lines = []
        lines.append(f"SIGNAL: {meta['signal']} ({meta['confidence']:.0%})")
        lines.append(f"Direction Score: {meta['net_direction']:+.2f}")
        lines.append("")

        # Key signals with safe access
        lines.append("Key Signals:")
        lines.append(f"  - VPIN: {signals.get('vpin', {}).get('signal', 'N/A')} ({signals.get('vpin', {}).get('direction_hint', 'N/A')})")
        lines.append(f"  - Volume: {signals.get('volume', {}).get('composite_signal', 'N/A')}")
        lines.append(f"  - Stop-Run: {signals.get('stop_run', {}).get('signal', 'N/A')}")
        lines.append(f"  - Sweep: {signals.get('sweep', {}).get('primary_signal', 'N/A')}")
        lines.append(f"  - Volatility: {signals.get('volatility', {}).get('regime', {}).get('regime', 'N/A')}")
        lines.append(f"  - Topology: Stress {signals.get('topology', {}).get('stress', 0):.2f} ({signals.get('topology', {}).get('mode', 'N/A')})")
        lines.append(f"  - Gamma: {signals.get('gamma', {}).get('signal', 'N/A')}")

        if meta['avoid_trade']:
            lines.append("")
            lines.append("WARNING: AVOID TRADING - Unfavorable conditions")

        return "\n".join(lines)


# Maintain backward compatibility
InstitutionalFeatureEngine = InstitutionalFeatureEngineV2


# Quick test
if __name__ == "__main__":
    import numpy as np

    # Create sample data
    np.random.seed(42)
    n = 100
    close = 100 + np.cumsum(np.random.randn(n) * 0.3)
    volume = np.random.randint(100, 500, n).astype(float)

    df = pd.DataFrame({
        'Open': close - np.random.rand(n) * 0.2,
        'High': close + np.abs(np.random.randn(n) * 0.3),
        'Low': close - np.abs(np.random.randn(n) * 0.3),
        'Close': close,
        'Volume': volume
    })

    engine = InstitutionalFeatureEngineV2()
    result = engine.extract_features(df, 'EURUSD')

    print("=" * 60)
    print("INSTITUTIONAL FEATURE ENGINE V2 - 12 METHODS")
    print("=" * 60)

    print(f"\nExtracted {len(result['features'])} features")
    print("\n" + engine.get_summary(result))
