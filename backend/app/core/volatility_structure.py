"""
VOLATILITY STRUCTURE ANALYZER
==============================
Institutional Secret: Volatility term structure tells you where the market 
expects movement. Backwardation (near-term vol > long-term) means fear.

Also tracks volatility regimes:
- Low vol regime: Range-bound, mean-reversion works
- High vol regime: Trends stronger, momentum works
- Vol expansion: Breakout happening
- Vol contraction: Compression before move
"""

import numpy as np
import pandas as pd
from typing import Dict


class VolatilityStructure:
    """
    Analyzes volatility structure and regimes.
    
    Key Concepts:
    1. Realized Volatility: What actually happened
    2. Volatility Regime: Current market state
    3. Volatility Expansion/Contraction: Direction of vol
    4. Bollinger Squeeze: Low vol = breakout imminent
    """
    
    def __init__(self, short_period: int = 10, long_period: int = 30):
        """
        Args:
            short_period: Short volatility lookback
            long_period: Long volatility lookback
        """
        self.short_period = short_period
        self.long_period = long_period
    
    def calculate_realized_volatility(
        self, 
        prices: np.ndarray, 
        period: int
    ) -> float:
        """
        Calculate annualized realized volatility.
        """
        if len(prices) <= period + 1:
            return 0
            
        relevant_prices = prices[-(period + 1):]
        returns = np.diff(relevant_prices) / relevant_prices[:-1]
        std = np.std(returns) if len(returns) > 1 else 0
        
        # Annualize (assuming daily data)
        annualized = std * np.sqrt(252)
        
        return annualized
    
    def detect_regime(self, df: pd.DataFrame) -> Dict:
        """
        Detect current volatility regime.
        """
        close = df['Close'].values
        
        if len(close) < self.long_period:
            return {
                'regime': 'UNKNOWN',
                'vol_short': 0,
                'vol_long': 0
            }
        
        # Calculate short and long vol
        vol_short = self.calculate_realized_volatility(close, self.short_period)
        vol_long = self.calculate_realized_volatility(close, self.long_period)
        
        # Regime classification
        vol_ratio = vol_short / (vol_long + 1e-10)
        
        if vol_short < 0.10:  # 10% annualized
            regime = 'LOW_VOL'
        elif vol_short > 0.25:  # 25% annualized
            regime = 'HIGH_VOL'
        else:
            regime = 'NORMAL_VOL'
        
        # Vol direction
        if vol_ratio > 1.3:
            vol_direction = 'EXPANDING'
        elif vol_ratio < 0.7:
            vol_direction = 'CONTRACTING'
        else:
            vol_direction = 'STABLE'
        
        return {
            'regime': regime,
            'vol_short': vol_short * 100,  # As percentage
            'vol_long': vol_long * 100,
            'vol_ratio': vol_ratio,
            'vol_direction': vol_direction
        }
    
    def detect_bollinger_squeeze(self, df: pd.DataFrame, period: int = 20) -> Dict:
        """
        Detect Bollinger Band squeeze - compression before breakout.
        """
        close = df['Close'].values
        
        if len(close) < period:
            return {'squeeze': False}
        
        # Calculate Bollinger Bands
        sma = np.mean(close[-period:])
        std = np.std(close[-period:])
        
        upper = sma + 2 * std
        lower = sma - 2 * std
        
        # Band width
        width = (upper - lower) / sma * 100
        
        # Calculate historical band width for comparison
        historical_widths = []
        for i in range(period, len(close) - 1):
            hist_sma = np.mean(close[i-period:i])
            hist_std = np.std(close[i-period:i])
            hist_width = (4 * hist_std) / hist_sma * 100
            historical_widths.append(hist_width)
        
        if len(historical_widths) > 0:
            avg_width = np.mean(historical_widths)
            width_percentile = np.sum(np.array(historical_widths) < width) / len(historical_widths)
        else:
            avg_width = width
            width_percentile = 0.5
        
        # Squeeze = Width in bottom 20% of historical
        squeeze = width_percentile < 0.2
        
        # Direction hint based on price position
        current_price = close[-1]
        if current_price > sma:
            direction_hint = 'BULLISH'
        elif current_price < sma:
            direction_hint = 'BEARISH'
        else:
            direction_hint = 'NEUTRAL'
        
        return {
            'squeeze': squeeze,
            'band_width': width,
            'width_percentile': width_percentile,
            'direction_hint': direction_hint,
            'upper_band': upper,
            'lower_band': lower,
            'sma': sma
        }
    
    def detect_volatility_breakout(self, df: pd.DataFrame) -> Dict:
        """
        Detect volatility breakouts - sudden expansion after compression.
        """
        if len(df) < self.long_period:
            return {'breakout': False}
        
        high = df['High'].values
        low = df['Low'].values
        close = df['Close'].values
        
        # Average True Range (ATR)
        tr = np.zeros(len(df))
        for i in range(1, len(df)):
            tr[i] = max(
                high[i] - low[i],
                abs(high[i] - close[i-1]),
                abs(low[i] - close[i-1])
            )
        
        # Short vs long ATR
        atr_short = np.mean(tr[-self.short_period:])
        atr_long = np.mean(tr[-self.long_period:])
        
        atr_ratio = atr_short / (atr_long + 1e-10)
        
        # Breakout = Short ATR much higher than long ATR
        breakout = atr_ratio > 1.5
        
        # Direction based on recent move
        recent_return = (close[-1] - close[-self.short_period]) / close[-self.short_period]
        
        if breakout:
            if recent_return > 0:
                breakout_type = 'BULLISH_BREAKOUT'
            else:
                breakout_type = 'BEARISH_BREAKOUT'
        else:
            breakout_type = 'NONE'
        
        return {
            'breakout': breakout,
            'breakout_type': breakout_type,
            'atr_short': atr_short,
            'atr_long': atr_long,
            'atr_ratio': atr_ratio
        }
    
    def analyze(self, df: pd.DataFrame) -> Dict:
        """
        Full volatility structure analysis.
        """
        regime = self.detect_regime(df)
        squeeze = self.detect_bollinger_squeeze(df)
        breakout = self.detect_volatility_breakout(df)
        
        # Generate trading implications
        if squeeze['squeeze']:
            signal = 'BREAKOUT_IMMINENT'
            recommendation = f"Prepare for {squeeze['direction_hint']} breakout"
        elif breakout['breakout']:
            signal = breakout['breakout_type']
            recommendation = "Trend following, momentum strategies"
        elif regime['regime'] == 'LOW_VOL':
            signal = 'RANGE_TRADING'
            recommendation = "Mean-reversion, sell premium"
        elif regime['regime'] == 'HIGH_VOL':
            signal = 'CAUTION_HIGH_VOL'
            recommendation = "Reduce size, wider stops"
        else:
            signal = 'NEUTRAL'
            recommendation = "Normal trading conditions"
        
        return {
            'regime': regime,
            'squeeze': squeeze,
            'breakout': breakout,
            'signal': signal,
            'recommendation': recommendation,
            'atr_value': breakout['atr_short']  # Expose current ATR (short period)
        }
    
    def get_features(self, df: pd.DataFrame) -> np.ndarray:
        """
        Extract volatility features for the feature engine.
        Returns 4 features.
        """
        result = self.analyze(df)
        
        features = np.zeros(4)
        
        # Feature 1: Vol regime encoded (-1 = low, 0 = normal, 1 = high)
        regime_map = {'LOW_VOL': -1, 'NORMAL_VOL': 0, 'HIGH_VOL': 1, 'UNKNOWN': 0}
        features[0] = regime_map.get(result['regime']['regime'], 0)
        
        # Feature 2: Vol ratio (normalized)
        features[1] = min(result['regime']['vol_ratio'] / 2, 1) if 'vol_ratio' in result['regime'] else 0.5
        
        # Feature 3: Squeeze detected
        features[2] = 1.0 if result['squeeze']['squeeze'] else 0.0
        
        # Feature 4: Breakout strength
        if result['breakout']['breakout']:
            if 'BULLISH' in result['breakout']['breakout_type']:
                features[3] = 1.0
            else:
                features[3] = -1.0
        else:
            features[3] = 0.0
        
        return features


# Quick test
if __name__ == "__main__":
    np.random.seed(42)
    
    # Create sample data - low vol then expansion
    n = 100
    close = 100 + np.cumsum(np.random.randn(n) * 0.1)  # Low vol initially
    close[-20:] = close[-20] + np.cumsum(np.random.randn(20) * 0.5)  # Vol expansion at end
    
    df = pd.DataFrame({
        'Open': close - np.random.rand(n) * 0.2,
        'High': close + np.abs(np.random.randn(n) * 0.3),
        'Low': close - np.abs(np.random.randn(n) * 0.3),
        'Close': close,
        'Volume': np.random.randint(100, 500, n).astype(float)
    })
    
    analyzer = VolatilityStructure()
    result = analyzer.analyze(df)
    
    print("Volatility Structure Analysis:")
    print(f"  Regime: {result['regime']['regime']}")
    print(f"  Short Vol: {result['regime']['vol_short']:.1f}%")
    print(f"  Long Vol: {result['regime']['vol_long']:.1f}%")
    print(f"  Vol Direction: {result['regime']['vol_direction']}")
    print(f"  Squeeze: {result['squeeze']['squeeze']}")
    print(f"  Breakout: {result['breakout']['breakout']}")
    print(f"  Signal: {result['signal']}")
    print(f"  Recommendation: {result['recommendation']}")
