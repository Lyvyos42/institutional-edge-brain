"""
VOLUME ACCUMULATION DETECTOR - Detect Hidden Institutional Buying/Selling
=========================================================================
Institutional Secret: When institutions accumulate positions, they do it slowly
to avoid moving the market. This creates a signature:
- High volume but no price movement = Absorption
- Price compressing while volume rises = Accumulation/Distribution

This module detects these patterns that precede major moves.
"""

import numpy as np
import pandas as pd
from typing import Dict, List


class VolumeAccumulation:
    """
    Detects institutional accumulation and distribution patterns.
    
    Signatures:
    1. Volume Climax: Huge volume spike, then price reverses
    2. Absorption: High volume but price doesn't move (hidden buying/selling)
    3. Hidden Divergence: Price making lows but volume decreasing (accumulation)
    4. Wyckoff Spring/Upthrust: Stop hunt followed by reversal
    """
    
    def __init__(self, lookback: int = 20):
        """
        Args:
            lookback: Period for analysis
        """
        self.lookback = lookback
    
    def detect_absorption(self, df: pd.DataFrame) -> Dict:
        """
        Detect absorption - high volume with minimal price movement.
        This happens when institutions are quietly accumulating.
        
        Signature: Volume >> average but |Close - Open| << average range
        """
        close = df['Close'].values
        open_price = df['Open'].values
        high = df['High'].values
        low = df['Low'].values
        volume = df['Volume'].values if 'Volume' in df.columns else np.ones(len(close)) * 1000
        
        # Calculate metrics
        body = np.abs(close - open_price)  # Candle body
        range_hl = high - low  # Full range
        avg_range = np.mean(range_hl[-self.lookback:])
        avg_volume = np.mean(volume[-self.lookback:])
        
        # Recent bar
        recent_body = body[-1]
        recent_volume = volume[-1]
        recent_range = range_hl[-1]
        
        # Absorption: Volume > 1.5x average, but body < 0.3x average range
        is_absorption = (recent_volume > avg_volume * 1.5) and (recent_body < avg_range * 0.3)
        
        # Direction hint based on close position in range
        if is_absorption:
            close_position = (close[-1] - low[-1]) / (range_hl[-1] + 1e-10)
            if close_position > 0.7:
                direction = 'BULLISH'  # Closed near high = buying absorption
            elif close_position < 0.3:
                direction = 'BEARISH'  # Closed near low = selling absorption
            else:
                direction = 'NEUTRAL'
        else:
            direction = 'NONE'
        
        return {
            'is_absorption': is_absorption,
            'volume_ratio': recent_volume / (avg_volume + 1e-10),
            'body_ratio': recent_body / (avg_range + 1e-10),
            'direction': direction
        }
    
    def detect_volume_climax(self, df: pd.DataFrame) -> Dict:
        """
        Detect volume climax - exhaustion move with huge volume.
        Often marks major tops/bottoms when institutions unload positions.
        """
        close = df['Close'].values
        volume = df['Volume'].values if 'Volume' in df.columns else np.ones(len(close)) * 1000
        
        avg_volume = np.mean(volume[-self.lookback:])
        std_volume = np.std(volume[-self.lookback:])
        
        # Volume climax: Volume > 3 standard deviations above mean
        recent_volume = volume[-1]
        z_score = (recent_volume - avg_volume) / (std_volume + 1e-10)
        
        is_climax = z_score > 2.5
        
        # Determine if buying or selling climax
        if is_climax:
            if close[-1] > close[-2]:
                climax_type = 'BUYING_CLIMAX'  # Potential top
            else:
                climax_type = 'SELLING_CLIMAX'  # Potential bottom
        else:
            climax_type = 'NONE'
        
        return {
            'is_climax': is_climax,
            'z_score': z_score,
            'climax_type': climax_type,
            'volume_ratio': recent_volume / (avg_volume + 1e-10)
        }
    
    def detect_accumulation_distribution(self, df: pd.DataFrame) -> Dict:
        """
        Detect accumulation (buying) or distribution (selling) using
        Accumulation/Distribution Line and volume patterns.
        """
        close = df['Close'].values
        high = df['High'].values
        low = df['Low'].values
        volume = df['Volume'].values if 'Volume' in df.columns else np.ones(len(close)) * 1000
        
        # Money Flow Multiplier
        mfm = ((close - low) - (high - close)) / (high - low + 1e-10)
        
        # Money Flow Volume
        mfv = mfm * volume
        
        # A/D Line
        ad_line = np.cumsum(mfv)
        
        # Compare A/D trend with price trend
        price_slope = np.polyfit(range(self.lookback), close[-self.lookback:], 1)[0]
        ad_slope = np.polyfit(range(self.lookback), ad_line[-self.lookback:], 1)[0]
        
        # Normalize slopes for comparison
        price_dir = 1 if price_slope > 0 else -1
        ad_dir = 1 if ad_slope > 0 else -1
        
        # Divergence = Smart money doing opposite of price
        if price_dir > 0 and ad_dir < 0:
            signal = 'DISTRIBUTION'  # Price up, A/D down = Smart money selling
        elif price_dir < 0 and ad_dir > 0:
            signal = 'ACCUMULATION'  # Price down, A/D up = Smart money buying
        elif price_dir > 0 and ad_dir > 0:
            signal = 'CONFIRMED_UPTREND'
        elif price_dir < 0 and ad_dir < 0:
            signal = 'CONFIRMED_DOWNTREND'
        else:
            signal = 'NEUTRAL'
        
        return {
            'signal': signal,
            'price_slope': price_slope,
            'ad_slope': ad_slope,
            'divergence': price_dir != ad_dir,
            'ad_line': ad_line[-1]
        }
    
    def detect_hidden_accumulation(self, df: pd.DataFrame) -> Dict:
        """
        Detect hidden accumulation using On-Balance Volume divergence.
        Price makes lower lows but OBV makes higher lows = Accumulation
        """
        close = df['Close'].values
        volume = df['Volume'].values if 'Volume' in df.columns else np.ones(len(close)) * 1000
        
        # Calculate OBV
        obv = np.zeros(len(close))
        obv[0] = volume[0]
        for i in range(1, len(close)):
            if close[i] > close[i-1]:
                obv[i] = obv[i-1] + volume[i]
            elif close[i] < close[i-1]:
                obv[i] = obv[i-1] - volume[i]
            else:
                obv[i] = obv[i-1]
        
        # Find recent swing points
        half = self.lookback // 2
        
        price_low1 = np.min(close[-self.lookback:-half])
        price_low2 = np.min(close[-half:])
        
        obv_low1 = np.min(obv[-self.lookback:-half])
        obv_low2 = np.min(obv[-half:])
        
        # Bullish divergence: Lower price low, higher OBV low
        bullish_div = (price_low2 < price_low1) and (obv_low2 > obv_low1)
        
        # Bearish divergence: Higher price high, lower OBV high
        price_high1 = np.max(close[-self.lookback:-half])
        price_high2 = np.max(close[-half:])
        obv_high1 = np.max(obv[-self.lookback:-half])
        obv_high2 = np.max(obv[-half:])
        
        bearish_div = (price_high2 > price_high1) and (obv_high2 < obv_high1)
        
        if bullish_div:
            signal = 'HIDDEN_ACCUMULATION'
        elif bearish_div:
            signal = 'HIDDEN_DISTRIBUTION'
        else:
            signal = 'NONE'
        
        return {
            'signal': signal,
            'bullish_divergence': bullish_div,
            'bearish_divergence': bearish_div,
            'obv': obv[-1]
        }
    
    def analyze(self, df: pd.DataFrame) -> Dict:
        """
        Run full volume accumulation analysis.
        """
        if len(df) < self.lookback:
            return {
                'absorption': {'is_absorption': False},
                'climax': {'is_climax': False},
                'ad_analysis': {'signal': 'NEUTRAL'},
                'hidden': {'signal': 'NONE'},
                'composite_signal': 'NEUTRAL',
                'institutional_activity': 0.0
            }
        
        absorption = self.detect_absorption(df)
        climax = self.detect_volume_climax(df)
        ad_analysis = self.detect_accumulation_distribution(df)
        hidden = self.detect_hidden_accumulation(df)
        
        # Composite signal
        signals = []
        if absorption['is_absorption']:
            signals.append(absorption['direction'])
        if climax['is_climax']:
            signals.append('REVERSAL' if climax['climax_type'] != 'NONE' else 'NONE')
        if ad_analysis['divergence']:
            signals.append(ad_analysis['signal'])
        if hidden['signal'] != 'NONE':
            signals.append(hidden['signal'])
        
        # Institutional activity score (0-1)
        activity = 0.0
        if absorption['is_absorption']:
            activity += 0.3
        if climax['is_climax']:
            activity += 0.3
        if ad_analysis['divergence']:
            activity += 0.2
        if hidden['signal'] != 'NONE':
            activity += 0.2
        
        # Determine direction
        bullish_count = sum(1 for s in signals if s in ['BULLISH', 'ACCUMULATION', 'HIDDEN_ACCUMULATION'])
        bearish_count = sum(1 for s in signals if s in ['BEARISH', 'DISTRIBUTION', 'HIDDEN_DISTRIBUTION'])
        
        if bullish_count > bearish_count:
            composite = 'BULLISH_ACCUMULATION'
        elif bearish_count > bullish_count:
            composite = 'BEARISH_DISTRIBUTION'
        else:
            composite = 'NEUTRAL'
        
        return {
            'absorption': absorption,
            'climax': climax,
            'ad_analysis': ad_analysis,
            'hidden': hidden,
            'composite_signal': composite,
            'institutional_activity': activity
        }


# Quick test
if __name__ == "__main__":
    np.random.seed(42)
    
    # Create sample data with accumulation pattern
    close = 100 + np.cumsum(np.random.randn(100) * 0.3)
    volume = np.random.randint(100, 500, 100).astype(float)
    
    # Add absorption signature (high volume, small body)
    volume[-5:] *= 3
    
    df = pd.DataFrame({
        'Open': close - np.random.rand(100) * 0.2,
        'High': close + np.abs(np.random.randn(100) * 0.3),
        'Low': close - np.abs(np.random.randn(100) * 0.3),
        'Close': close,
        'Volume': volume
    })
    
    detector = VolumeAccumulation()
    result = detector.analyze(df)
    
    print("Volume Accumulation Analysis:")
    print(f"  Absorption: {result['absorption']['is_absorption']}")
    print(f"  Climax: {result['climax']['is_climax']}")
    print(f"  A/D Signal: {result['ad_analysis']['signal']}")
    print(f"  Hidden: {result['hidden']['signal']}")
    print(f"  Composite: {result['composite_signal']}")
    print(f"  Institutional Activity: {result['institutional_activity']:.1%}")
