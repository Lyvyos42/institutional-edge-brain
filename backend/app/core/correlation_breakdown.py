"""
CORRELATION BREAKDOWN DETECTOR
==============================
Institutional Secret: Normally correlated assets temporarily diverge.
When they do, one will "catch up" - creating a mean-reversion opportunity.

Examples:
- DXY up but Gold not dropping → Gold will catch up and drop
- Oil up but CAD not moving → CAD will strengthen
- VIX spiking but SPY not dropping → SPY will catch up and drop
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional


class CorrelationBreakdown:
    """
    Detects when normally correlated assets diverge.
    
    Theory:
    - Some assets have stable long-term correlations
    - When correlation temporarily breaks, it's an opportunity
    - The "lagging" asset will catch up to the "leading" asset
    
    Used by: Statistical arbitrage desks, pairs trading funds
    """
    
    # Known correlation pairs and their expected relationship
    CORRELATION_PAIRS = {
        # (Asset1, Asset2): Expected correlation (-1 to +1)
        ('DXY', 'XAUUSD'): -0.7,      # Dollar up → Gold down
        ('DXY', 'EURUSD'): -0.95,     # Dollar up → Euro down
        ('USOIL', 'USDCAD'): -0.6,    # Oil up → CAD strengthens (USD/CAD down)
        ('VIX', 'SPX'): -0.8,         # Fear up → Stocks down
        ('US10Y', 'USDJPY'): 0.7,     # Yields up → Yen weakens
        ('XAUUSD', 'XAGUSD'): 0.9,    # Gold and Silver move together
        ('EURUSD', 'GBPUSD'): 0.85,   # Euro and Pound often correlated
    }
    
    def __init__(self, lookback: int = 50, correlation_window: int = 20):
        """
        Args:
            lookback: Period for calculating rolling correlation
            correlation_window: Window for recent correlation check
        """
        self.lookback = lookback
        self.correlation_window = correlation_window
        self.breakdown_threshold = 0.3  # Correlation drop threshold
    
    def calculate_rolling_correlation(
        self, 
        series1: np.ndarray, 
        series2: np.ndarray, 
        window: int = 20
    ) -> np.ndarray:
        """Calculate rolling correlation between two price series."""
        
        # Convert to returns
        returns1 = np.diff(series1) / series1[:-1]
        returns2 = np.diff(series2) / series2[:-1]
        
        n = len(returns1)
        correlations = np.zeros(n)
        
        for i in range(window, n):
            r1 = returns1[i-window:i]
            r2 = returns2[i-window:i]
            
            # Pearson correlation
            corr = np.corrcoef(r1, r2)[0, 1]
            correlations[i] = corr if not np.isnan(corr) else 0
        
        return correlations
    
    def detect_breakdown(
        self, 
        series1: np.ndarray, 
        series2: np.ndarray,
        expected_corr: float
    ) -> Dict:
        """
        Detect if correlation has broken down from expected level.
        
        Args:
            series1: Price series for asset 1
            series2: Price series for asset 2
            expected_corr: Expected correlation (-1 to +1)
        
        Returns:
            Dict with breakdown detection and trading signals
        """
        if len(series1) < self.lookback or len(series2) < self.lookback:
            return {
                'breakdown_detected': False,
                'message': 'Insufficient data'
            }
        
        # Calculate correlations
        rolling_corr = self.calculate_rolling_correlation(
            series1, series2, self.correlation_window
        )
        
        recent_corr = np.mean(rolling_corr[-5:])  # Last 5 periods
        historical_corr = np.mean(rolling_corr[-self.lookback:-5])  # Older periods
        
        # Detect breakdown
        corr_change = abs(recent_corr - expected_corr)
        breakdown_detected = corr_change > self.breakdown_threshold
        
        # Determine which asset is leading/lagging
        returns1 = (series1[-1] - series1[-self.correlation_window]) / series1[-self.correlation_window]
        returns2 = (series2[-1] - series2[-self.correlation_window]) / series2[-self.correlation_window]
        
        if expected_corr > 0:
            # Positive correlation - they should move same direction
            if returns1 > returns2:
                leader = 'ASSET1'
                laggard = 'ASSET2'
                trade_signal = 'ASSET2_CATCH_UP'  # Expect asset2 to move in same direction
            else:
                leader = 'ASSET2'
                laggard = 'ASSET1'
                trade_signal = 'ASSET1_CATCH_UP'
        else:
            # Negative correlation - they should move opposite
            if returns1 * returns2 > 0:  # Both moved same direction = wrong
                if abs(returns1) > abs(returns2):
                    leader = 'ASSET1'
                    trade_signal = 'ASSET2_REVERSE'  # Expect asset2 to reverse
                else:
                    leader = 'ASSET2'
                    trade_signal = 'ASSET1_REVERSE'
            else:
                # Correlation holding
                trade_signal = 'CORRELATION_INTACT'
                leader = None
        
        return {
            'breakdown_detected': breakdown_detected,
            'recent_correlation': recent_corr,
            'expected_correlation': expected_corr,
            'correlation_deviation': corr_change,
            'leader': leader if breakdown_detected else None,
            'trade_signal': trade_signal if breakdown_detected else 'NO_SIGNAL',
            'asset1_return': returns1 * 100,
            'asset2_return': returns2 * 100
        }
    
    def analyze_pair(
        self, 
        df1: pd.DataFrame, 
        df2: pd.DataFrame,
        pair_name: Tuple[str, str]
    ) -> Dict:
        """
        Analyze a specific correlation pair.
        """
        expected_corr = self.CORRELATION_PAIRS.get(pair_name, 0)
        
        series1 = df1['Close'].values
        series2 = df2['Close'].values
        
        result = self.detect_breakdown(series1, series2, expected_corr)
        result['pair'] = pair_name
        
        return result
    
    def analyze_vs_benchmark(
        self, 
        df: pd.DataFrame, 
        symbol: str
    ) -> Dict:
        """
        Analyze an asset vs its typical benchmark.
        Uses the asset's own internal correlation (autocorrelation).
        """
        close = df['Close'].values
        
        if len(close) < self.lookback:
            return {'signal': 'NO_DATA'}
        
        # Calculate returns
        returns = np.diff(close) / close[:-1]
        
        # Autocorrelation (correlation with lagged self)
        lag = 5
        if len(returns) > lag + 10:
            autocorr = np.corrcoef(returns[:-lag], returns[lag:])[0, 1]
        else:
            autocorr = 0
        
        # Trend consistency
        short_return = (close[-1] - close[-10]) / close[-10]
        long_return = (close[-1] - close[-self.lookback]) / close[-self.lookback]
        
        # Divergence: short-term vs long-term
        if short_return * long_return < 0:
            signal = 'TREND_REVERSAL_FORMING'
            confidence = min(abs(short_return - long_return) * 10, 1.0)
        elif abs(short_return) > abs(long_return) * 2:
            signal = 'MOMENTUM_ACCELERATION'
            confidence = 0.7
        else:
            signal = 'TREND_CONSISTENT'
            confidence = 0.5
        
        return {
            'symbol': symbol,
            'signal': signal,
            'confidence': confidence,
            'short_return': short_return * 100,
            'long_return': long_return * 100,
            'autocorrelation': autocorr
        }
    
    def get_features(self, df: pd.DataFrame, symbol: str = "UNKNOWN") -> np.ndarray:
        """
        Extract correlation features for the feature engine.
        Returns 4 features.
        """
        result = self.analyze_vs_benchmark(df, symbol)
        
        features = np.zeros(4)
        features[0] = result.get('autocorrelation', 0)
        features[1] = result.get('short_return', 0) / 10  # Normalize
        features[2] = result.get('long_return', 0) / 10  # Normalize
        features[3] = result.get('confidence', 0.5)
        
        return features


# Quick test
if __name__ == "__main__":
    np.random.seed(42)
    
    # Create two correlated price series
    n = 100
    base = np.cumsum(np.random.randn(n) * 0.5)
    
    # Asset 1 follows base
    series1 = 100 + base
    
    # Asset 2 inversely correlated but breaks down at the end
    series2 = 100 - base * 0.7 + np.cumsum(np.random.randn(n) * 0.2)
    series2[-20:] += np.linspace(0, 5, 20)  # Break correlation at end
    
    detector = CorrelationBreakdown()
    result = detector.detect_breakdown(series1, series2, expected_corr=-0.7)
    
    print("Correlation Breakdown Analysis:")
    print(f"  Breakdown Detected: {result['breakdown_detected']}")
    print(f"  Recent Correlation: {result['recent_correlation']:.3f}")
    print(f"  Expected: {result['expected_correlation']:.3f}")
    print(f"  Deviation: {result['correlation_deviation']:.3f}")
    print(f"  Trade Signal: {result['trade_signal']}")
