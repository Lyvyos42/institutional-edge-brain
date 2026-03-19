"""
VPIN CALCULATOR - Detect Smart Money Activity
=============================================
Institutional Secret: VPIN (Volume-Synchronized Probability of Informed Trading)
measures when "informed traders" (institutions with information edge) are active.

High VPIN = Smart money is trading aggressively = Big move coming soon
VPIN predicted the Flash Crash of 2010 hours before it happened.
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, List


class VPINCalculator:
    """
    Volume-Synchronized Probability of Informed Trading (VPIN)
    
    Theory:
    - Trades can be classified as "buyer-initiated" or "seller-initiated"
    - Informed traders (institutions) cause order imbalance
    - High imbalance = High VPIN = Informed traders active = Move imminent
    
    Original paper: Easley, López de Prado, O'Hara (2012)
    Used by: Chicago Mercantile Exchange for risk monitoring
    """
    
    def __init__(self, volume_bucket_size: int = 50, num_buckets: int = 50):
        """
        Args:
            volume_bucket_size: Volume per bucket for time-sync
            num_buckets: Number of buckets for VPIN calculation
        """
        self.volume_bucket_size = volume_bucket_size
        self.num_buckets = num_buckets
    
    def classify_trades(self, df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Classify trades as buyer or seller initiated using Bulk Volume Classification.
        
        BVC uses price changes to probabilistically classify volume.
        More sophisticated than tick rule, works with OHLCV data.
        """
        close = df['Close'].values
        volume = df['Volume'].values if 'Volume' in df.columns else np.ones(len(close)) * 1000
        
        # Calculate returns
        returns = np.zeros(len(close))
        returns[1:] = (close[1:] - close[:-1]) / close[:-1]
        
        # Estimate standard deviation of returns
        sigma = np.std(returns[returns != 0]) if len(returns[returns != 0]) > 0 else 0.01
        
        # Bulk Volume Classification
        # Z-score of return
        z = returns / (sigma + 1e-10)
        
        # CDF gives probability of buy (using logistic approximation)
        # This approximates scipy.stats.norm.cdf well
        buy_prob = 1 / (1 + np.exp(-z * 1.7))
        
        # Classify volume
        buy_volume = volume * buy_prob
        sell_volume = volume * (1 - buy_prob)
        
        return buy_volume, sell_volume
    
    def calculate_vpin(self, df: pd.DataFrame) -> Dict:
        """
        Calculate VPIN metric.
        
        VPIN = Average of |Buy Volume - Sell Volume| / Total Volume
        
        Returns:
            Dict with VPIN value and related metrics
        """
        buy_vol, sell_vol = self.classify_trades(df)
        total_vol = df['Volume'].values if 'Volume' in df.columns else np.ones(len(df)) * 1000
        
        # Create volume buckets
        cumulative_vol = np.cumsum(total_vol)
        target_vol = self.volume_bucket_size * np.mean(total_vol)
        
        buckets = []
        bucket_start = 0
        
        for i in range(len(cumulative_vol)):
            if cumulative_vol[i] - (cumulative_vol[bucket_start - 1] if bucket_start > 0 else 0) >= target_vol:
                bucket_buy = np.sum(buy_vol[bucket_start:i+1])
                bucket_sell = np.sum(sell_vol[bucket_start:i+1])
                bucket_total = np.sum(total_vol[bucket_start:i+1])
                
                if bucket_total > 0:
                    imbalance = abs(bucket_buy - bucket_sell) / bucket_total
                    buckets.append(imbalance)
                
                bucket_start = i + 1
                
                if len(buckets) >= self.num_buckets:
                    break
        
        # Calculate VPIN
        if len(buckets) > 0:
            vpin = np.mean(buckets)
            vpin_std = np.std(buckets)
        else:
            # Fallback: simple calculation
            total = np.sum(total_vol)
            if total > 0:
                vpin = np.sum(np.abs(buy_vol - sell_vol)) / total
                vpin_std = 0.1
            else:
                vpin = 0.5
                vpin_std = 0.1
        
        return {
            'vpin': vpin,
            'vpin_std': vpin_std,
            'num_buckets': len(buckets),
            'is_high': vpin > 0.4,
            'is_extreme': vpin > 0.6
        }
    
    def analyze(self, df: pd.DataFrame) -> Dict:
        """
        Full VPIN analysis with signal generation.
        
        Returns:
            Dict with VPIN metrics and trading signals
        """
        vpin_result = self.calculate_vpin(df)
        vpin = vpin_result['vpin']
        
        # Determine signal
        if vpin > 0.6:
            signal = 'HIGH_TOXICITY'  # Extreme informed trading - expect big move
            confidence = 0.9
        elif vpin > 0.4:
            signal = 'ELEVATED'  # Above normal - be cautious
            confidence = 0.7
        elif vpin > 0.3:
            signal = 'NORMAL'
            confidence = 0.5
        else:
            signal = 'LOW'  # Retail-dominated, random
            confidence = 0.3
        
        # Direction hint based on order imbalance
        buy_vol, sell_vol = self.classify_trades(df)
        recent_buy = np.sum(buy_vol[-10:])
        recent_sell = np.sum(sell_vol[-10:])
        
        if recent_buy > recent_sell * 1.2:
            direction_hint = 'BULLISH'
        elif recent_sell > recent_buy * 1.2:
            direction_hint = 'BEARISH'
        else:
            direction_hint = 'NEUTRAL'
        
        return {
            'vpin': vpin,
            'vpin_std': vpin_result['vpin_std'],
            'signal': signal,
            'confidence': confidence,
            'direction_hint': direction_hint,
            'is_high_toxicity': vpin > 0.4,
            'smart_money_active': vpin > 0.5
        }
    
    def get_vpin_trend(self, df: pd.DataFrame, lookback_periods: List[int] = [10, 20, 50]) -> Dict:
        """
        Check VPIN trend over multiple periods.
        Rising VPIN = More informed trading = Move building
        """
        vpins = {}
        
        for period in lookback_periods:
            if len(df) >= period:
                subset = df.tail(period).copy()
                result = self.calculate_vpin(subset)
                vpins[f'vpin_{period}'] = result['vpin']
        
        # Trend analysis
        if len(vpins) >= 2:
            values = list(vpins.values())
            if values[-1] > values[0] * 1.3:
                trend = 'RISING'  # VPIN increasing - move building
            elif values[-1] < values[0] * 0.7:
                trend = 'FALLING'  # VPIN decreasing - calming down
            else:
                trend = 'STABLE'
        else:
            trend = 'UNKNOWN'
        
        vpins['trend'] = trend
        return vpins


# Quick test
if __name__ == "__main__":
    # Create sample data
    np.random.seed(42)
    
    # Simulate market with some informed trading
    close = 100 + np.cumsum(np.random.randn(200) * 0.5)
    volume = np.random.randint(100, 1000, 200).astype(float)
    
    # Spike volume in middle (simulate informed trading)
    volume[90:110] *= 3
    
    df = pd.DataFrame({
        'Close': close,
        'Volume': volume
    })
    
    calculator = VPINCalculator()
    result = calculator.analyze(df)
    
    print("VPIN Analysis:")
    print(f"  VPIN: {result['vpin']:.3f}")
    print(f"  Signal: {result['signal']}")
    print(f"  Direction Hint: {result['direction_hint']}")
    print(f"  Smart Money Active: {result['smart_money_active']}")
