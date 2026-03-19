"""
ENTROPY ANALYZER - Detect "Calm Before the Storm"
===============================================
Institutional Secret: Before every major market move, information entropy decreases.
Low entropy = Order forming = Breakout imminent

This module uses Shannon entropy and other information-theoretic measures 
to detect when the market is about to make a big move.
"""

import numpy as np
import pandas as pd
from typing import Tuple, Dict


class EntropyAnalyzer:
    """
    Detects entropy collapse - the calm before major market moves.
    
    Theory: 
    - High entropy = Chaos, random price action, unpredictable
    - Low entropy = Order forming, compression, breakout imminent
    - Entropy DROP = Institutions positioning before move
    """
    
    def __init__(self, lookback: int = 20, threshold_low: float = 0.3, threshold_high: float = 0.7):
        """
        Args:
            lookback: Period for entropy calculation
            threshold_low: Below this = low entropy (breakout imminent)
            threshold_high: Above this = high entropy (choppy market)
        """
        self.lookback = lookback
        self.threshold_low = threshold_low
        self.threshold_high = threshold_high
    
    def shannon_entropy(self, data: np.ndarray, bins: int = 10) -> float:
        """
        Calculate Shannon entropy of price changes.
        
        H(X) = -Σ p(x) * log2(p(x))
        
        Higher entropy = more random/unpredictable
        Lower entropy = more ordered/predictable
        """
        if len(data) < 2:
            return 0.5
        
        # Discretize into bins
        hist, _ = np.histogram(data, bins=bins, density=True)
        hist = hist[hist > 0]  # Remove zero bins
        
        if len(hist) == 0:
            return 0.5
        
        # Normalize to probabilities
        probs = hist / hist.sum()
        
        # Shannon entropy
        entropy = -np.sum(probs * np.log2(probs + 1e-10))
        
        # Normalize to 0-1 range (max entropy = log2(bins))
        max_entropy = np.log2(bins)
        normalized = entropy / max_entropy if max_entropy > 0 else 0.5
        
        return normalized
    
    def approximate_entropy(self, data: np.ndarray, m: int = 2, r: float = 0.2) -> float:
        """
        Approximate Entropy (ApEn) - measures regularity/predictability.
        Used in financial time series to detect regime changes.
        
        Lower ApEn = More regular/predictable
        Higher ApEn = More random/complex
        """
        N = len(data)
        if N < m + 1:
            return 0.5
        
        # Standard deviation threshold
        r = r * np.std(data)
        
        def phi(m):
            patterns = np.array([data[i:i+m] for i in range(N - m + 1)])
            counts = []
            for i, pattern in enumerate(patterns):
                # Count similar patterns
                matches = np.sum(np.max(np.abs(patterns - pattern), axis=1) <= r)
                counts.append(matches / (N - m + 1))
            return np.mean(np.log(counts + 1e-10))
        
        return phi(m) - phi(m + 1)
    
    def permutation_entropy(self, data: np.ndarray, order: int = 3, delay: int = 1) -> float:
        """
        Permutation Entropy - measures complexity based on ordinal patterns.
        Very robust to noise and market microstructure.
        
        Used by quant funds to detect when "order" is emerging in chaos.
        """
        n = len(data)
        if n < order * delay:
            return 0.5
        
        # Extract ordinal patterns
        patterns = {}
        for i in range(n - (order - 1) * delay):
            indices = [i + j * delay for j in range(order)]
            values = [data[idx] for idx in indices]
            # Get permutation pattern
            pattern = tuple(np.argsort(values))
            patterns[pattern] = patterns.get(pattern, 0) + 1
        
        if not patterns:
            return 0.5
        
        # Normalize to probabilities
        total = sum(patterns.values())
        probs = np.array([c / total for c in patterns.values()])
        
        # Entropy
        entropy = -np.sum(probs * np.log2(probs + 1e-10))
        
        # Normalize by maximum possible entropy
        from math import factorial
        max_entropy = np.log2(factorial(order))
        
        return entropy / max_entropy if max_entropy > 0 else 0.5
    
    
    def hurst_exponent(self, data: np.ndarray) -> float:
        """
        Calculate Hurst Exponent (Fractal Dimension).
        H = 0.5: Geometric Brownian Motion (Random Walk).
        H > 0.5: Persistent (Trend).
        H < 0.5: Anti-persistent (Mean Reversion).
        
        Institutional Edge:
        - If H ~ 0.5 but Entropy is LOW: "Simulated Chaos" (Ghost Algo).
        """
        lags = range(2, 20)
        tau = [np.sqrt(np.std(np.subtract(data[lag:], data[:-lag]))) for lag in lags]
        
        # Avoid log(0)
        if len(tau) == 0 or np.any(np.array(tau) == 0): return 0.5
        
        poly = np.polyfit(np.log(lags), np.log(tau), 1)
        return poly[0] * 2.0 
    
    def analyze(self, df: pd.DataFrame) -> Dict:
        """
        Analyze entropy of price data.
        
        Returns:
            Dict with entropy metrics and signals
        """
        close = df['Close'].values
        returns = np.diff(close) / close[:-1] * 100
        
        if len(returns) < self.lookback:
            return {
                'shannon': 0.5,
                'permutation': 0.5,
                'entropy_score': 0.5,
                'hurst': 0.5,
                'signal': 'NEUTRAL',
                'is_collapse': False,
                'is_chaos': False,
                'is_ghost_algo': False
            }
        
        # Get recent data
        recent_returns = returns[-self.lookback:]
        
        # Calculate multiple entropy measures
        shannon = self.shannon_entropy(recent_returns)
        perm = self.permutation_entropy(recent_returns)
        hurst = self.hurst_exponent(df['Close'].values[-self.lookback:]) # Use price for Hurst
        
        # Combined score (weighted average)
        entropy_score = 0.6 * shannon + 0.4 * perm
        
        # Detect states
        is_collapse = entropy_score < self.threshold_low
        is_chaos = entropy_score > self.threshold_high
        
        # Phase 33: Ghost Algo Detection (Simulated Chaos)
        # H ~ 0.5 (Random) but Entropy is Low (Structured) -> Artificial
        is_ghost_algo = False
        if abs(hurst - 0.5) < 0.05 and entropy_score < 0.4:
            is_ghost_algo = True
        
        # Signal
        signal = 'NEUTRAL'
        if is_ghost_algo:
             signal = 'GHOST_ALGO_DETECTED'
        elif is_collapse:
            signal = 'BREAKOUT_IMMINENT'
        elif is_chaos:
            signal = 'CHOPPY_AVOID'
        
        return {
            'shannon': shannon,
            'permutation': perm,
            'entropy_score': entropy_score,
            'hurst': hurst,
            'signal': signal,
            'is_collapse': is_collapse,
            'is_chaos': is_chaos,
            'is_ghost_algo': is_ghost_algo
        }
    
    def get_entropy_trend(self, df: pd.DataFrame, periods: int = 5) -> str:
        """
        Check if entropy is decreasing (collapsing) over time.
        Decreasing entropy = Institutions positioning = Move coming
        """
        close = df['Close'].values
        returns = np.diff(close) / close[:-1] * 100
        
        if len(returns) < self.lookback + periods:
            return 'NEUTRAL'
        
        entropies = []
        for i in range(periods):
            idx = -(self.lookback + i)
            end_idx = -i if i > 0 else len(returns)
            slice_data = returns[idx:end_idx]
            if len(slice_data) >= 5:
                entropies.append(self.shannon_entropy(slice_data))
        
        if len(entropies) < 3:
            return 'NEUTRAL'
        
        # Reverse to get chronological order
        entropies = entropies[::-1]
        
        # Check trend
        if entropies[-1] < entropies[0] * 0.8:  # 20% drop
            return 'COLLAPSING'  # Breakout imminent
        elif entropies[-1] > entropies[0] * 1.2:  # 20% rise
            return 'EXPANDING'  # Getting choppy
        else:
            return 'STABLE'


# Quick test
if __name__ == "__main__":
    # Create sample data
    np.random.seed(42)
    
    # Simulate choppy market followed by compression
    choppy = np.random.randn(50) * 2  # High volatility, random
    compression = np.random.randn(20) * 0.3  # Low volatility, compressed
    
    data = np.concatenate([choppy, compression])
    df = pd.DataFrame({'Close': 100 + np.cumsum(data)})
    
    analyzer = EntropyAnalyzer()
    result = analyzer.analyze(df)
    
    print("Entropy Analysis:")
    print(f"  Shannon Entropy: {result['shannon']:.3f}")
    print(f"  Permutation Entropy: {result['permutation']:.3f}")
    print(f"  Combined Score: {result['entropy_score']:.3f}")
    print(f"  Signal: {result['signal']}")
    print(f"  Is Collapse: {result['is_collapse']}")
