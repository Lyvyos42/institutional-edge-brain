"""
VOLUME PROFILE / VPOC ANALYZER - Auction Theory
================================================
Institutional Secret: Price is an auction that searches for "fair value".
The Volume Point of Control (VPOC) is where most trading occurred - 
it acts as a powerful magnet for price.

Used by: Market makers, institutional traders, prop firms
Source: Auction Market Theory by James Dalton
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple


class VolumeProfileAnalyzer:
    """
    Analyzes volume distribution across price levels using Auction Theory.
    
    Key Concepts:
    - VPOC (Volume Point of Control): Price level with highest volume
    - Value Area (VA): Range containing 70% of volume
    - VAH/VAL: Value Area High/Low - key support/resistance
    - Single Prints: Low volume areas - often revisited to "fill"
    
    When price is:
    - Inside Value Area: Equilibrium, range-bound
    - Above VA: Bullish auction, look for pullbacks to VAH
    - Below VA: Bearish auction, look for rallies to VAL
    """
    
    def __init__(self, num_bins: int = 50, value_area_pct: float = 0.70):
        """
        Args:
            num_bins: Number of price bins for volume profile
            value_area_pct: Percentage of volume for value area (typically 70%)
        """
        self.num_bins = num_bins
        self.value_area_pct = value_area_pct
    
    def build_volume_profile(self, df: pd.DataFrame) -> Dict:
        """
        Build a volume profile from OHLCV data.
        
        Returns distribution of volume across price levels.
        """
        highs = df['High'].values
        lows = df['Low'].values
        closes = df['Close'].values
        volumes = df['Volume'].values if 'Volume' in df.columns else np.ones(len(df))
        
        # Price range
        price_min = np.min(lows)
        price_max = np.max(highs)
        price_range = price_max - price_min
        
        if price_range == 0:
            return {'error': 'No price range'}
        
        # Create bins
        bin_size = price_range / self.num_bins
        bins = np.linspace(price_min, price_max, self.num_bins + 1)
        bin_centers = (bins[:-1] + bins[1:]) / 2
        
        # Distribute volume across price levels touched by each bar
        volume_at_price = np.zeros(self.num_bins)
        
        for i in range(len(df)):
            bar_low = lows[i]
            bar_high = highs[i]
            bar_volume = volumes[i]
            
            # Find bins touched by this bar
            low_bin = int((bar_low - price_min) / bin_size)
            high_bin = int((bar_high - price_min) / bin_size)
            
            low_bin = max(0, min(low_bin, self.num_bins - 1))
            high_bin = max(0, min(high_bin, self.num_bins - 1))
            
            # Distribute volume evenly across touched bins
            num_bins_touched = high_bin - low_bin + 1
            vol_per_bin = bar_volume / num_bins_touched
            
            for b in range(low_bin, high_bin + 1):
                volume_at_price[b] += vol_per_bin
        
        return {
            'bins': bins,
            'bin_centers': bin_centers,
            'volume': volume_at_price,
            'price_min': price_min,
            'price_max': price_max,
            'bin_size': bin_size
        }
    
    def calculate_vpoc(self, profile: Dict) -> float:
        """
        Find the Volume Point of Control - highest volume price level.
        """
        if 'volume' not in profile:
            return 0
        
        vpoc_idx = np.argmax(profile['volume'])
        vpoc_price = profile['bin_centers'][vpoc_idx]
        
        return vpoc_price
    
    def calculate_value_area(self, profile: Dict) -> Dict:
        """
        Calculate the Value Area - range containing 70% of volume.
        
        Uses the TPO method:
        1. Start at VPOC
        2. Expand up and down, adding bins with more volume
        3. Stop when 70% of volume is captured
        """
        if 'volume' not in profile:
            return {'error': 'No profile'}
        
        volumes = profile['volume']
        centers = profile['bin_centers']
        total_volume = np.sum(volumes)
        target_volume = total_volume * self.value_area_pct
        
        # Start at VPOC
        vpoc_idx = np.argmax(volumes)
        included = {vpoc_idx}
        current_volume = volumes[vpoc_idx]
        
        low_idx = vpoc_idx
        high_idx = vpoc_idx
        
        # Expand until we capture enough volume
        while current_volume < target_volume and (low_idx > 0 or high_idx < len(volumes) - 1):
            # Check volume at next lower and higher bins
            vol_below = volumes[low_idx - 1] if low_idx > 0 else 0
            vol_above = volumes[high_idx + 1] if high_idx < len(volumes) - 1 else 0
            
            # Add the one with more volume
            if vol_below >= vol_above and low_idx > 0:
                low_idx -= 1
                included.add(low_idx)
                current_volume += vol_below
            elif high_idx < len(volumes) - 1:
                high_idx += 1
                included.add(high_idx)
                current_volume += vol_above
            else:
                break
        
        val = centers[low_idx]  # Value Area Low
        vah = centers[high_idx]  # Value Area High
        
        return {
            'val': val,
            'vah': vah,
            'vpoc': centers[vpoc_idx],
            'value_area_volume_pct': current_volume / total_volume if total_volume > 0 else 0,
            'low_idx': low_idx,
            'high_idx': high_idx
        }
    
    def find_low_volume_nodes(self, profile: Dict, threshold_pct: float = 0.15) -> List[float]:
        """
        Find Low Volume Nodes (LVN) - price levels with little trading.
        These are often revisited as price "fills in" gaps.
        """
        if 'volume' not in profile:
            return []
        
        volumes = profile['volume']
        centers = profile['bin_centers']
        
        avg_volume = np.mean(volumes)
        threshold = avg_volume * threshold_pct
        
        lvns = []
        for i, vol in enumerate(volumes):
            if vol < threshold:
                lvns.append(centers[i])
        
        return lvns
    
    def find_high_volume_nodes(self, profile: Dict, threshold_pct: float = 1.5) -> List[float]:
        """
        Find High Volume Nodes (HVN) - significant S/R levels.
        """
        if 'volume' not in profile:
            return []
        
        volumes = profile['volume']
        centers = profile['bin_centers']
        
        avg_volume = np.mean(volumes)
        threshold = avg_volume * threshold_pct
        
        hvns = []
        for i, vol in enumerate(volumes):
            if vol > threshold:
                hvns.append(centers[i])
        
        return hvns
    
    def analyze(self, df: pd.DataFrame) -> Dict:
        """
        Full volume profile analysis.
        """
        if len(df) < 10:
            return {
                'signal': 'NO_DATA',
                'vpoc': 0,
                'val': 0,
                'vah': 0
            }
        
        # Build profile
        profile = self.build_volume_profile(df)
        
        if 'error' in profile:
            return {'signal': 'ERROR', 'error': profile['error']}
        
        # Calculate key levels
        vpoc = self.calculate_vpoc(profile)
        value_area = self.calculate_value_area(profile)
        lvns = self.find_low_volume_nodes(profile)
        hvns = self.find_high_volume_nodes(profile)
        
        # Current price position
        current_price = df['Close'].iloc[-1]
        val = value_area['val']
        vah = value_area['vah']
        
        # Determine signal based on price position
        if val <= current_price <= vah:
            position = 'INSIDE_VALUE'
            signal = 'RANGE_BOUND'
        elif current_price > vah:
            position = 'ABOVE_VALUE'
            signal = 'BULLISH_AUCTION'
        else:  # current_price < val
            position = 'BELOW_VALUE'
            signal = 'BEARISH_AUCTION'
        
        # Distance to VPOC (magnet effect)
        vpoc_distance = (current_price - vpoc) / vpoc * 100
        
        # Near LVN? (Price tends to fill these)
        near_lvn = any(abs(current_price - lvn) / current_price < 0.005 for lvn in lvns)
        
        return {
            'vpoc': vpoc,
            'val': val,
            'vah': vah,
            'current_price': current_price,
            'position': position,
            'signal': signal,
            'vpoc_distance_pct': vpoc_distance,
            'hvns': hvns[:5],  # Top 5
            'lvns': lvns[:5],  # Top 5
            'near_lvn': near_lvn,
            'profile': profile
        }
    
    def get_features(self, df: pd.DataFrame) -> np.ndarray:
        """
        Extract volume profile features for the feature engine.
        Returns 4 features.
        """
        result = self.analyze(df)
        
        features = np.zeros(4)
        
        if 'error' in result or result.get('signal') == 'NO_DATA':
            return features
        
        # Feature 1: Position relative to value area (-1 = below, 0 = inside, 1 = above)
        if result['position'] == 'ABOVE_VALUE':
            features[0] = 1.0
        elif result['position'] == 'BELOW_VALUE':
            features[0] = -1.0
        else:
            features[0] = 0.0
        
        # Feature 2: Distance to VPOC (normalized)
        features[1] = np.clip(result['vpoc_distance_pct'] / 5, -1, 1)
        
        # Feature 3: Near LVN (likely to fill)
        features[2] = 1.0 if result['near_lvn'] else 0.0
        
        # Feature 4: Value area width (volatility proxy)
        if result['vah'] > 0:
            va_width = (result['vah'] - result['val']) / result['vah'] * 100
            features[3] = np.clip(va_width / 5, 0, 1)
        
        return features


# Quick test
if __name__ == "__main__":
    np.random.seed(42)
    
    # Create sample OHLCV data
    n = 100
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    
    df = pd.DataFrame({
        'Open': close - np.random.rand(n) * 0.3,
        'High': close + np.abs(np.random.randn(n) * 0.5),
        'Low': close - np.abs(np.random.randn(n) * 0.5),
        'Close': close,
        'Volume': np.random.randint(100, 1000, n).astype(float)
    })
    
    analyzer = VolumeProfileAnalyzer()
    result = analyzer.analyze(df)
    
    print("Volume Profile Analysis:")
    print(f"  VPOC: {result['vpoc']:.2f}")
    print(f"  Value Area Low: {result['val']:.2f}")
    print(f"  Value Area High: {result['vah']:.2f}")
    print(f"  Current Price: {result['current_price']:.2f}")
    print(f"  Position: {result['position']}")
    print(f"  Signal: {result['signal']}")
    print(f"  Distance to VPOC: {result['vpoc_distance_pct']:.2f}%")
    print(f"  HVNs: {[f'{x:.2f}' for x in result['hvns']]}")
