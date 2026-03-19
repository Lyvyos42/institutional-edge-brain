"""
SWEEP / AGGRESSION DETECTOR
============================
Institutional Secret: When institutions need to execute NOW, they "sweep" 
all available liquidity. This creates a distinct signature visible in volume.

Sweep = Urgency = They know something is coming

Detection:
- Sudden volume spike (3x+ normal)
- Wide bar (engulfing previous bars)
- Often near key levels (S/R, round numbers)
"""

import numpy as np
import pandas as pd
from typing import Dict, List


class SweepDetector:
    """
    Detects sweep/aggression patterns in price action.
    
    Types of Sweeps:
    1. Liquidity Sweep: Takes out stops above/below a level
    2. Momentum Sweep: Aggressive buying/selling with conviction
    3. Panic Sweep: Rushed liquidation (usually at capitulation)
    """
    
    def __init__(self, lookback: int = 20, volume_threshold: float = 2.5):
        """
        Args:
            lookback: Bars for baseline calculation
            volume_threshold: Multiple of average volume to flag as sweep
        """
        self.lookback = lookback
        self.volume_threshold = volume_threshold
    
    def detect_volume_sweep(self, df: pd.DataFrame) -> Dict:
        """
        Detect sweeps based on volume spikes.
        """
        if len(df) < self.lookback:
            return {'sweep_detected': False}
        
        volume = df['Volume'].values if 'Volume' in df.columns else np.ones(len(df)) * 1000
        close = df['Close'].values
        open_price = df['Open'].values
        high = df['High'].values
        low = df['Low'].values
        
        # Calculate metrics
        avg_volume = np.mean(volume[-self.lookback:-1])
        recent_volume = volume[-1]
        
        # Volume spike
        volume_ratio = recent_volume / (avg_volume + 1e-10)
        is_volume_spike = volume_ratio > self.volume_threshold
        
        # Bar characteristics
        bar_range = high[-1] - low[-1]
        bar_body = abs(close[-1] - open_price[-1])
        avg_range = np.mean(high[-self.lookback:-1] - low[-self.lookback:-1])
        
        is_wide_bar = bar_range > avg_range * 1.5
        
        # Direction
        if close[-1] > open_price[-1]:
            direction = 'BULLISH'
        elif close[-1] < open_price[-1]:
            direction = 'BEARISH'
        else:
            direction = 'NEUTRAL'
        
        # Sweep detection
        sweep_detected = is_volume_spike and is_wide_bar
        
        if sweep_detected:
            if direction == 'BULLISH':
                sweep_type = 'BULLISH_SWEEP'
                signal = 'STRONG_BUYING'
            else:
                sweep_type = 'BEARISH_SWEEP'
                signal = 'STRONG_SELLING'
        else:
            sweep_type = 'NONE'
            signal = 'NEUTRAL'
        
        return {
            'sweep_detected': sweep_detected,
            'sweep_type': sweep_type,
            'signal': signal,
            'volume_ratio': volume_ratio,
            'bar_range_ratio': bar_range / (avg_range + 1e-10),
            'direction': direction
        }
    
    def detect_liquidity_sweep(self, df: pd.DataFrame) -> Dict:
        """
        Detect liquidity sweeps - price takes out a level then reverses.
        """
        if len(df) < self.lookback:
            return {'liquidity_sweep': False}
        
        high = df['High'].values
        low = df['Low'].values
        close = df['Close'].values
        
        # Find recent swing high/low
        swing_highs = []
        swing_lows = []
        
        for i in range(-self.lookback + 2, -2):
            if high[i] > high[i-1] and high[i] > high[i+1]:
                swing_highs.append(high[i])
            if low[i] < low[i-1] and low[i] < low[i+1]:
                swing_lows.append(low[i])
        
        current_high = high[-1]
        current_low = low[-1]
        current_close = close[-1]
        previous_close = close[-2]
        
        # Check for sweep above swing high then close below
        bullish_sweep = False
        for sh in swing_highs:
            if current_high > sh and current_close < sh and current_close < previous_close:
                bullish_sweep = True  # Actually a failed breakout = bearish
                break
        
        # Check for sweep below swing low then close above
        bearish_sweep = False
        for sl in swing_lows:
            if current_low < sl and current_close > sl and current_close > previous_close:
                bearish_sweep = True  # Actually a failed breakdown = bullish
                break
        
        if bullish_sweep:
            return {
                'liquidity_sweep': True,
                'type': 'BULL_TRAP',
                'signal': 'BEARISH_REVERSAL',
                'recommendation': 'Look for short entries'
            }
        elif bearish_sweep:
            return {
                'liquidity_sweep': True,
                'type': 'BEAR_TRAP',
                'signal': 'BULLISH_REVERSAL',
                'recommendation': 'Look for long entries'
            }
        else:
            return {
                'liquidity_sweep': False,
                'type': 'NONE',
                'signal': 'NEUTRAL'
            }
    
    def detect_momentum_burst(self, df: pd.DataFrame) -> Dict:
        """
        Detect momentum bursts - sustained aggressive moves.
        """
        if len(df) < self.lookback:
            return {'momentum_burst': False}
        
        close = df['Close'].values
        volume = df['Volume'].values if 'Volume' in df.columns else np.ones(len(df)) * 1000
        
        # Count consecutive bars in same direction with increasing volume
        same_direction = 0
        increasing_volume = 0
        direction = 'NEUTRAL'
        
        for i in range(-5, 0):
            if close[i] > close[i-1]:
                if direction == 'BULLISH' or direction == 'NEUTRAL':
                    same_direction += 1
                    direction = 'BULLISH'
                    if volume[i] > volume[i-1]:
                        increasing_volume += 1
                else:
                    break
            elif close[i] < close[i-1]:
                if direction == 'BEARISH' or direction == 'NEUTRAL':
                    same_direction += 1
                    direction = 'BEARISH'
                    if volume[i] > volume[i-1]:
                        increasing_volume += 1
                else:
                    break
        
        is_momentum_burst = same_direction >= 4 and increasing_volume >= 2
        
        return {
            'momentum_burst': is_momentum_burst,
            'consecutive_bars': same_direction,
            'direction': direction,
            'signal': f'{direction}_MOMENTUM' if is_momentum_burst else 'NEUTRAL',
            'strength': same_direction / 5 + increasing_volume / 4
        }
    
    def analyze(self, df: pd.DataFrame) -> Dict:
        """
        Full sweep analysis.
        """
        volume_sweep = self.detect_volume_sweep(df)
        liquidity_sweep = self.detect_liquidity_sweep(df)
        momentum = self.detect_momentum_burst(df)
        
        # Combine signals
        if liquidity_sweep['liquidity_sweep']:
            primary_signal = liquidity_sweep['signal']
            confidence = 0.85
        elif volume_sweep['sweep_detected']:
            primary_signal = volume_sweep['signal']
            confidence = 0.75
        elif momentum['momentum_burst']:
            primary_signal = momentum['signal']
            confidence = 0.65
        else:
            primary_signal = 'NEUTRAL'
            confidence = 0.5
        
        return {
            'volume_sweep': volume_sweep,
            'liquidity_sweep': liquidity_sweep,
            'momentum': momentum,
            'primary_signal': primary_signal,
            'confidence': confidence,
            'aggression_score': (
                (1 if volume_sweep['sweep_detected'] else 0) * 0.4 +
                (1 if liquidity_sweep['liquidity_sweep'] else 0) * 0.4 +
                (1 if momentum['momentum_burst'] else 0) * 0.2
            )
        }
    
    def get_features(self, df: pd.DataFrame) -> np.ndarray:
        """
        Extract sweep features for the feature engine.
        Returns 4 features.
        """
        result = self.analyze(df)
        
        features = np.zeros(4)
        
        # Feature 1: Aggression score
        features[0] = result['aggression_score']
        
        # Feature 2: Volume ratio (capped)
        features[1] = min(result['volume_sweep']['volume_ratio'] / 5, 1.0)
        
        # Feature 3: Sweep direction (-1 = bearish, 0 = neutral, 1 = bullish)
        if 'BULLISH' in result['primary_signal']:
            features[2] = 1.0
        elif 'BEARISH' in result['primary_signal']:
            features[2] = -1.0
        else:
            features[2] = 0.0
        
        # Feature 4: Liquidity sweep detected
        features[3] = 1.0 if result['liquidity_sweep']['liquidity_sweep'] else 0.0
        
        return features


# Quick test
if __name__ == "__main__":
    np.random.seed(42)
    
    # Create sample data with a sweep pattern
    n = 50
    close = 100 + np.cumsum(np.random.randn(n) * 0.3)
    volume = np.random.randint(100, 300, n).astype(float)
    
    # Add sweep at end (volume spike + wide bar)
    close[-1] = close[-2] + 1.5  # Big up move
    volume[-1] = 900  # Volume spike
    
    df = pd.DataFrame({
        'Open': close - np.random.rand(n) * 0.2,
        'High': close + np.abs(np.random.randn(n) * 0.4),
        'Low': close - np.abs(np.random.randn(n) * 0.4),
        'Close': close,
        'Volume': volume
    })
    
    detector = SweepDetector()
    result = detector.analyze(df)
    
    print("Sweep Detection Analysis:")
    print(f"  Volume Sweep: {result['volume_sweep']['sweep_detected']}")
    print(f"  Volume Ratio: {result['volume_sweep']['volume_ratio']:.2f}x")
    print(f"  Liquidity Sweep: {result['liquidity_sweep']['liquidity_sweep']}")
    print(f"  Momentum Burst: {result['momentum']['momentum_burst']}")
    print(f"  Primary Signal: {result['primary_signal']}")
    print(f"  Confidence: {result['confidence']:.0%}")
    print(f"  Aggression Score: {result['aggression_score']:.2f}")
