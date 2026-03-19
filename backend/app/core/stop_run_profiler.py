"""
STOP-RUN PROFILER - Historical Stop Hunt Analysis
==================================================
Institutional Secret: Each asset has a typical "stop-run depth" - 
how far price extends beyond obvious structure before reversing.

By profiling historical stop-runs, you can:
1. Set stops that won't get hit
2. Enter at the optimal point during a stop-run
3. Recognize when a stop-run is complete
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple


class StopRunProfiler:
    """
    Profiles historical stop-run patterns for an asset.
    
    Stop-Run = Price extends beyond obvious S/R (taking out stops) then reverses
    
    What we measure:
    - Average depth of stop-runs (in pips/points/%)
    - Typical duration of stop-runs
    - Recovery time after stop-run
    - Success rate of fade-the-run trades
    """
    
    def __init__(self, lookback: int = 50, swing_threshold: float = 0.002):
        """
        Args:
            lookback: Bars to analyze for swing points
            swing_threshold: Minimum move size for swing detection (0.2%)
        """
        self.lookback = lookback
        self.swing_threshold = swing_threshold
    
    def find_swing_points(self, df: pd.DataFrame) -> Dict:
        """
        Find swing highs and lows in the price data.
        """
        high = df['High'].values
        low = df['Low'].values
        close = df['Close'].values
        
        swing_highs = []  # (index, price)
        swing_lows = []   # (index, price)
        
        # Need at least 2 bars on each side
        for i in range(2, len(df) - 2):
            # Swing high: Higher than neighbors
            if high[i] > high[i-1] and high[i] > high[i-2] and \
               high[i] > high[i+1] and high[i] > high[i+2]:
                swing_highs.append((i, high[i]))
            
            # Swing low: Lower than neighbors
            if low[i] < low[i-1] and low[i] < low[i-2] and \
               low[i] < low[i+1] and low[i] < low[i+2]:
                swing_lows.append((i, low[i]))
        
        return {
            'swing_highs': swing_highs,
            'swing_lows': swing_lows
        }
    
    def detect_stop_runs(self, df: pd.DataFrame) -> List[Dict]:
        """
        Detect historical stop-run patterns.
        
        Pattern:
        1. Price is near a swing high/low (obvious level)
        2. Price breaks beyond the level (taking stops)
        3. Price quickly reverses back
        """
        high = df['High'].values
        low = df['Low'].values
        close = df['Close'].values
        
        swings = self.find_swing_points(df)
        stop_runs = []
        
        # Analyze stop-runs at swing highs (bearish stop-runs / bull traps)
        for i, (swing_idx, swing_price) in enumerate(swings['swing_highs'][:-1]):
            # Look for price extending above swing then reversing
            for j in range(swing_idx + 1, min(swing_idx + 15, len(high))):
                if high[j] > swing_price:
                    # Found extension above
                    extension = (high[j] - swing_price) / swing_price * 100
                    
                    # Check for reversal within next 5 bars
                    for k in range(j + 1, min(j + 6, len(close))):
                        if close[k] < swing_price:
                            # Stop-run confirmed
                            stop_runs.append({
                                'type': 'BEARISH_STOP_RUN',
                                'level': swing_price,
                                'max_extension': high[j],
                                'extension_pct': extension,
                                'bars_to_reverse': k - j,
                                'reversal_close': close[k],
                                'index': swing_idx
                            })
                            break
                    break
        
        # Analyze stop-runs at swing lows (bullish stop-runs / bear traps)
        for i, (swing_idx, swing_price) in enumerate(swings['swing_lows'][:-1]):
            # Look for price extending below swing then reversing
            for j in range(swing_idx + 1, min(swing_idx + 15, len(low))):
                if low[j] < swing_price:
                    # Found extension below
                    extension = (swing_price - low[j]) / swing_price * 100
                    
                    # Check for reversal within next 5 bars
                    for k in range(j + 1, min(j + 6, len(close))):
                        if close[k] > swing_price:
                            # Stop-run confirmed
                            stop_runs.append({
                                'type': 'BULLISH_STOP_RUN',
                                'level': swing_price,
                                'min_extension': low[j],
                                'extension_pct': extension,
                                'bars_to_reverse': k - j,
                                'reversal_close': close[k],
                                'index': swing_idx
                            })
                            break
                    break
        
        return stop_runs
    
    def calculate_profile(self, stop_runs: List[Dict]) -> Dict:
        """
        Calculate the typical stop-run profile for this asset.
        """
        if not stop_runs:
            return {
                'avg_extension_pct': 0.0,
                'max_extension_pct': 0.0,
                'avg_bars_to_reverse': 0,
                'bullish_count': 0,
                'bearish_count': 0,
                'total_count': 0
            }
        
        extensions = [sr['extension_pct'] for sr in stop_runs]
        reversals = [sr['bars_to_reverse'] for sr in stop_runs]
        
        bullish = [sr for sr in stop_runs if sr['type'] == 'BULLISH_STOP_RUN']
        bearish = [sr for sr in stop_runs if sr['type'] == 'BEARISH_STOP_RUN']
        
        return {
            'avg_extension_pct': np.mean(extensions),
            'median_extension_pct': np.median(extensions),
            'max_extension_pct': np.max(extensions),
            'std_extension_pct': np.std(extensions),
            'avg_bars_to_reverse': np.mean(reversals),
            'bullish_count': len(bullish),
            'bearish_count': len(bearish),
            'total_count': len(stop_runs),
            'bullish_avg_ext': np.mean([sr['extension_pct'] for sr in bullish]) if bullish else 0,
            'bearish_avg_ext': np.mean([sr['extension_pct'] for sr in bearish]) if bearish else 0
        }
    
    def is_stop_run_in_progress(self, df: pd.DataFrame) -> Dict:
        """
        Detect if a stop-run is currently in progress.
        """
        if len(df) < 10:
            return {'in_progress': False}
        
        high = df['High'].values
        low = df['Low'].values
        close = df['Close'].values
        
        # Get recent swing points (last 20 bars)
        recent_df = df.tail(20).reset_index(drop=True)
        swings = self.find_swing_points(recent_df)
        
        # Check if current bar is extending beyond recent swing
        current_high = high[-1]
        current_low = low[-1]
        current_close = close[-1]
        
        # Check against recent swing highs
        for idx, swing_high in swings['swing_highs']:
            if current_high > swing_high and current_close < swing_high:
                extension = (current_high - swing_high) / swing_high * 100
                return {
                    'in_progress': True,
                    'type': 'BEARISH_STOP_RUN',
                    'level': swing_high,
                    'extension_pct': extension,
                    'signal': 'POTENTIAL_REVERSAL_DOWN',
                    'recommended_action': 'WATCH_FOR_CLOSE_BELOW_LEVEL'
                }
        
        # Check against recent swing lows
        for idx, swing_low in swings['swing_lows']:
            if current_low < swing_low and current_close > swing_low:
                extension = (swing_low - current_low) / swing_low * 100
                return {
                    'in_progress': True,
                    'type': 'BULLISH_STOP_RUN',
                    'level': swing_low,
                    'extension_pct': extension,
                    'signal': 'POTENTIAL_REVERSAL_UP',
                    'recommended_action': 'WATCH_FOR_CLOSE_ABOVE_LEVEL'
                }
        
        return {
            'in_progress': False,
            'type': 'NONE',
            'signal': 'NO_STOP_RUN'
        }
    
    def analyze(self, df: pd.DataFrame) -> Dict:
        """
        Full stop-run analysis.
        """
        if len(df) < self.lookback:
            return {
                'profile': {},
                'current_status': {'in_progress': False},
                'signal': 'NO_DATA'
            }
        
        # Detect historical stop-runs
        stop_runs = self.detect_stop_runs(df)
        
        # Calculate profile
        profile = self.calculate_profile(stop_runs)
        
        # Check current status
        current_status = self.is_stop_run_in_progress(df)
        
        # Generate signal
        if current_status['in_progress']:
            if current_status['type'] == 'BULLISH_STOP_RUN':
                signal = 'BUY_OPPORTUNITY'
                confidence = min(current_status['extension_pct'] / (profile['avg_extension_pct'] + 0.01), 1.0)
            else:
                signal = 'SELL_OPPORTUNITY'
                confidence = min(current_status['extension_pct'] / (profile['avg_extension_pct'] + 0.01), 1.0)
        else:
            signal = 'NO_SIGNAL'
            confidence = 0.0
        
        return {
            'profile': profile,
            'stop_runs': stop_runs[-10:],  # Last 10
            'current_status': current_status,
            'signal': signal,
            'confidence': confidence,
            'recommended_stop_buffer': profile['avg_extension_pct'] * 1.2  # Add 20% safety
        }
    
    def get_features(self, df: pd.DataFrame) -> np.ndarray:
        """
        Extract stop-run features for the feature engine.
        Returns 4 features.
        """
        result = self.analyze(df)
        
        features = np.zeros(4)
        
        if result.get('signal') == 'NO_DATA':
            return features
        
        # Feature 1: Stop-run in progress (0 = no, 1 = bullish, -1 = bearish)
        status = result['current_status']
        if status['in_progress']:
            features[0] = 1.0 if status['type'] == 'BULLISH_STOP_RUN' else -1.0
        
        # Feature 2: Extension relative to average
        if status['in_progress'] and result['profile']['avg_extension_pct'] > 0:
            features[1] = min(status['extension_pct'] / result['profile']['avg_extension_pct'], 2.0) / 2.0
        
        # Feature 3: Signal confidence
        features[2] = result['confidence']
        
        # Feature 4: Historical stop-run frequency
        features[3] = min(result['profile']['total_count'] / 20, 1.0)  # Normalize
        
        return features


# Quick test
if __name__ == "__main__":
    np.random.seed(42)
    
    # Create sample data with some stop-run patterns
    n = 100
    close = 100 + np.cumsum(np.random.randn(n) * 0.3)
    
    # Add some artificial stop-runs
    close[30:35] = [101, 101.5, 100.2, 99.5, 100]  # Bear trap
    close[60:65] = [99, 98.5, 99.8, 100.5, 100]    # Bull trap
    
    df = pd.DataFrame({
        'Open': close - np.random.rand(n) * 0.2,
        'High': close + np.abs(np.random.randn(n) * 0.4),
        'Low': close - np.abs(np.random.randn(n) * 0.4),
        'Close': close,
        'Volume': np.random.randint(100, 500, n).astype(float)
    })
    
    profiler = StopRunProfiler()
    result = profiler.analyze(df)
    
    print("Stop-Run Profile Analysis:")
    print(f"  Total Stop-Runs Detected: {result['profile']['total_count']}")
    print(f"  Avg Extension: {result['profile']['avg_extension_pct']:.2f}%")
    print(f"  Max Extension: {result['profile']['max_extension_pct']:.2f}%")
    print(f"  Avg Bars to Reverse: {result['profile']['avg_bars_to_reverse']:.1f}")
    print(f"  Recommended Stop Buffer: {result['recommended_stop_buffer']:.2f}%")
    print(f"  Current Status: {result['current_status']['in_progress']}")
    print(f"  Signal: {result['signal']}")
