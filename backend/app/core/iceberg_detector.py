"""
ICEBERG ORDER DETECTOR - Detect Hidden Institutional Orders
============================================================
Institutional Secret: Large institutional orders are hidden as "Icebergs"
They show small orders but execute large amounts at the same price level.

Detection Signature:
- Same price level hit repeatedly with similar volume
- Price doesn't move despite high volume = Hidden buying/selling
- Sudden "reveal" when they finish accumulating
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from collections import defaultdict


class IcebergDetector:
    """
    Detects iceberg orders - hidden large institutional positions.
    
    How Icebergs Work:
    1. Institution wants to buy 1 million shares
    2. Showing this would move the market against them
    3. They show 1,000 shares at a time, refilling as executed
    4. Creates signature: Same price hit repeatedly with constant small sizes
    
    Detection Methods:
    1. Price Level Magnet: Price keeps returning to same level
    2. Volume Clustering: High volume at a single price
    3. Rejection Count: Multiple failed breakout attempts
    4. Hidden Absorption: Volume >> Price Movement
    """
    
    def __init__(self, lookback: int = 50, price_tolerance: float = 0.0005):
        """
        Args:
            lookback: Bars to analyze
            price_tolerance: How close prices must be to count as "same level"
        """
        self.lookback = lookback
        self.price_tolerance = price_tolerance  # 0.05% = 5 pips for forex
    
    def find_price_clusters(self, df: pd.DataFrame) -> List[Dict]:
        """
        Find price levels that are repeatedly visited.
        These are potential iceberg locations.
        """
        close = df['Close'].values
        high = df['High'].values
        low = df['Low'].values
        volume = df['Volume'].values if 'Volume' in df.columns else np.ones(len(close)) * 1000
        
        # Create price bins
        price_min = np.min(low[-self.lookback:])
        price_max = np.max(high[-self.lookback:])
        price_range = price_max - price_min
        
        if price_range == 0:
            return []
        
        # Bin size based on tolerance
        bin_size = price_range * self.price_tolerance * 10
        num_bins = int(price_range / bin_size) + 1
        
        # Count visits and volume at each price level
        level_stats = defaultdict(lambda: {'visits': 0, 'volume': 0, 'prices': []})
        
        for i in range(-self.lookback, 0):
            # Each bar touches multiple price levels
            bar_low = low[i]
            bar_high = high[i]
            bar_close = close[i]
            bar_volume = volume[i]
            
            # Record close price level
            level_idx = int((bar_close - price_min) / bin_size)
            level_stats[level_idx]['visits'] += 1
            level_stats[level_idx]['volume'] += bar_volume
            level_stats[level_idx]['prices'].append(bar_close)
        
        # Find significant clusters (many visits, high volume)
        avg_visits = np.mean([s['visits'] for s in level_stats.values()])
        avg_volume = np.mean([s['volume'] for s in level_stats.values()])
        
        clusters = []
        for level_idx, stats in level_stats.items():
            if stats['visits'] >= avg_visits * 1.5 and stats['volume'] >= avg_volume * 1.3:
                level_price = price_min + (level_idx + 0.5) * bin_size
                clusters.append({
                    'price_level': level_price,
                    'visits': stats['visits'],
                    'volume': stats['volume'],
                    'avg_price': np.mean(stats['prices']),
                    'is_iceberg_candidate': True
                })
        
        # Sort by volume
        clusters.sort(key=lambda x: x['volume'], reverse=True)
        
        return clusters[:5]  # Top 5 clusters
    
    def detect_repeated_rejection(self, df: pd.DataFrame) -> Dict:
        """
        Detect repeated rejections at a price level.
        Multiple wicks at same level = Iceberg defending that price.
        """
        high = df['High'].values
        low = df['Low'].values
        close = df['Close'].values
        
        recent = min(self.lookback, len(df))
        
        # Find swing highs and lows
        swing_highs = []
        swing_lows = []
        
        for i in range(-recent + 2, -2):
            if high[i] > high[i-1] and high[i] > high[i+1]:
                swing_highs.append(high[i])
            if low[i] < low[i-1] and low[i] < low[i+1]:
                swing_lows.append(low[i])
        
        # Check for clustering of swing points
        resistance_cluster = None
        support_cluster = None
        
        if len(swing_highs) >= 3:
            # Check if multiple highs are at similar level
            high_std = np.std(swing_highs[-5:]) if len(swing_highs) >= 5 else np.std(swing_highs)
            avg_high = np.mean(swing_highs[-5:]) if len(swing_highs) >= 5 else np.mean(swing_highs)
            if high_std / avg_high < self.price_tolerance * 2:
                resistance_cluster = {
                    'level': avg_high,
                    'rejections': len(swing_highs[-5:]),
                    'is_iceberg': True,
                    'type': 'RESISTANCE'
                }
        
        if len(swing_lows) >= 3:
            low_std = np.std(swing_lows[-5:]) if len(swing_lows) >= 5 else np.std(swing_lows)
            avg_low = np.mean(swing_lows[-5:]) if len(swing_lows) >= 5 else np.mean(swing_lows)
            if low_std / avg_low < self.price_tolerance * 2:
                support_cluster = {
                    'level': avg_low,
                    'rejections': len(swing_lows[-5:]),
                    'is_iceberg': True,
                    'type': 'SUPPORT'
                }
        
        return {
            'resistance': resistance_cluster,
            'support': support_cluster,
            'iceberg_detected': resistance_cluster is not None or support_cluster is not None
        }
    
    def detect_absorption(self, df: pd.DataFrame) -> Dict:
        """
        Detect absorption - high volume but price doesn't move.
        Signature of iceberg absorbing all selling/buying pressure.
        """
        close = df['Close'].values
        volume = df['Volume'].values if 'Volume' in df.columns else np.ones(len(close)) * 1000
        
        # Calculate efficiency: Price change per unit volume
        price_changes = np.abs(np.diff(close))
        volumes = volume[1:]
        
        efficiency = price_changes / (volumes + 1e-10)
        
        # Recent efficiency vs average
        avg_eff = np.mean(efficiency[-self.lookback:])
        recent_eff = np.mean(efficiency[-5:])
        recent_vol = np.mean(volume[-5:])
        avg_vol = np.mean(volume[-self.lookback:])
        
        # Absorption: High volume but low efficiency (price not moving)
        is_absorption = (recent_vol > avg_vol * 1.5) and (recent_eff < avg_eff * 0.5)
        
        # Direction: If closing higher despite absorption = bullish
        price_dir = close[-1] - close[-5]
        if is_absorption:
            if price_dir > 0:
                direction = 'BULLISH_ABSORPTION'  # Buy iceberg
            elif price_dir < 0:
                direction = 'BEARISH_ABSORPTION'  # Sell iceberg
            else:
                direction = 'NEUTRAL_ABSORPTION'
        else:
            direction = 'NONE'
        
        return {
            'is_absorption': is_absorption,
            'direction': direction,
            'volume_ratio': recent_vol / (avg_vol + 1e-10),
            'efficiency_ratio': recent_eff / (avg_eff + 1e-10)
        }
    
    def detect_ghost_protocol(self, df: pd.DataFrame) -> Dict:
        """
        Phase 32: Detect "Ghost Prions" (Algorithmic Infection).
        Logic: High Volume with Zero Price Variance (Stasis).
        This indicates an algo is 'taxing' liquidity without moving price.
        """
        if len(df) < 20: return {'ghost_detected': False}
        
        close = df['Close'].values[-20:]
        open_ = df['Open'].values[-20:]
        high = df['High'].values[-20:]
        low = df['Low'].values[-20:]
        volume = df['Volume'].values[-20:]
        
        avg_vol = np.mean(volume)
        ghost_bars = 0
        
        for i in range(len(close)):
            # "Zero Variance" - Price is artificially flat
            range_pct = (high[i] - low[i]) / (close[i] + 1e-9)
            
            # High Volume (> 1.5x avg) AND Ultra-Low Range (< 0.01%)
            if volume[i] > avg_vol * 1.5 and range_pct < 0.0001:
                ghost_bars += 1
                
        is_ghost = ghost_bars >= 2 # At least 2 such anomalies
        
        return {
            'ghost_detected': is_ghost,
            'ghost_bars': ghost_bars,
            'signal': 'GHOST_PRION_DETECTED' if is_ghost else 'NONE'
        }

    def analyze(self, df: pd.DataFrame) -> Dict:
        """
        Full iceberg detection analysis.
        """
        if len(df) < self.lookback:
            return {
                'iceberg_detected': False,
                'clusters': [],
                'rejections': {'iceberg_detected': False},
                'absorption': {'is_absorption': False},
                'ghost_protocol': {'ghost_detected': False},
                'signal': 'NO_DATA'
            }
        
        clusters = self.find_price_clusters(df)
        rejections = self.detect_repeated_rejection(df)
        absorption = self.detect_absorption(df)
        ghost = self.detect_ghost_protocol(df) # Phase 32
        
        # Determine overall signal
        current_price = df['Close'].iloc[-1]
        
        signal = 'NEUTRAL'
        iceberg_level = None
        
        # Check if price is near an iceberg level
        for cluster in clusters:
            distance = abs(current_price - cluster['price_level']) / current_price
            if distance < self.price_tolerance * 3:
                iceberg_level = cluster['price_level']
                if current_price > cluster['price_level']:
                    signal = 'NEAR_SUPPORT_ICEBERG'  # Potential bounce
                else:
                    signal = 'NEAR_RESISTANCE_ICEBERG'  # Potential rejection
                break
        
        # Absorption overrides if detected
        if absorption['is_absorption']:
            if absorption['direction'] == 'BULLISH_ABSORPTION':
                signal = 'BULLISH_ICEBERG_ACTIVE'
            elif absorption['direction'] == 'BEARISH_ABSORPTION':
                signal = 'BEARISH_ICEBERG_ACTIVE'
                
        # Ghost Override (Meta-Signal)
        if ghost['ghost_detected']:
            signal = 'GHOST_PRION_DETECTED'
        
        return {
            'iceberg_detected': len(clusters) > 0 or rejections['iceberg_detected'] or absorption['is_absorption'],
            'clusters': clusters,
            'rejections': rejections,
            'absorption': absorption,
            'ghost_protocol': ghost,
            'signal': signal,
            'iceberg_level': iceberg_level,
            'current_price': current_price
        }


# Quick test
if __name__ == "__main__":
    np.random.seed(42)
    
    # Create sample data with repeated tests of same level
    base_price = 100
    prices = []
    for i in range(100):
        # Price oscillates around 100, repeatedly testing it
        noise = np.random.randn() * 0.3
        if i % 10 < 5:
            prices.append(base_price + noise + 0.5)  # Above
        else:
            prices.append(base_price + noise - 0.5)  # Below, but bouncing
    
    close = np.array(prices)
    volume = np.random.randint(100, 500, 100).astype(float)
    
    # High volume near the base_price level
    for i in range(100):
        if abs(close[i] - base_price) < 0.5:
            volume[i] *= 3
    
    df = pd.DataFrame({
        'Open': close - np.random.rand(100) * 0.2,
        'High': close + np.abs(np.random.randn(100) * 0.3),
        'Low': close - np.abs(np.random.randn(100) * 0.3),
        'Close': close,
        'Volume': volume
    })
    
    detector = IcebergDetector()
    result = detector.analyze(df)
    
    print("Iceberg Detection Analysis:")
    print(f"  Iceberg Detected: {result['iceberg_detected']}")
    print(f"  Signal: {result['signal']}")
    print(f"  Clusters Found: {len(result['clusters'])}")
    if result['clusters']:
        print(f"  Top Cluster: {result['clusters'][0]['price_level']:.2f} ({result['clusters'][0]['visits']} visits)")
    print(f"  Absorption: {result['absorption']['is_absorption']}")
