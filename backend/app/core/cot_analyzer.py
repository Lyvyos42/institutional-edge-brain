"""
COT ANALYZER - Follow the Commercial Hedgers
=============================================
Institutional Secret: The Commitment of Traders (COT) report shows 
what commercial hedgers (big producers/consumers) are doing.

Commercials are ALWAYS right at extremes - they hedge real business exposure.
When commercials flip from short to long at a major low → FOLLOW THEM

This data is public but 99% of retail traders ignore it.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Optional
import json
import os


class COTAnalyzer:
    """
    Analyzes Commitment of Traders data for trading signals.
    
    Trader Categories:
    1. Commercials (Hedgers): Big producers/consumers hedging real exposure
       - RIGHT at extremes, often early in middle
    2. Large Speculators (Funds): Hedge funds, trend followers
       - Right during trends, wrong at extremes
    3. Small Speculators (Retail): Wrong most of the time
       - Fade them at extremes
    
    Key Signals:
    - Commercial net position flip = Major turning point
    - Commercial extreme positioning = Counter-trend opportunity
    - Speculator crowding = Reversal warning
    """
    
    def __init__(self, data_path: str = "cot_data.json"):
        """
        Args:
            data_path: Path to COT data file (or will use simulated data)
        """
        self.data_path = data_path
        self.cot_data = {}
        
        # Historical percentile thresholds
        self.extreme_percentile_high = 0.9  # 90th percentile = extreme long
        self.extreme_percentile_low = 0.1   # 10th percentile = extreme short
    
    def load_cot_data(self) -> Dict:
        """
        Load COT data from file or API.
        
        In production, this would fetch from:
        - CFTC: https://www.cftc.gov/MarketReports/CommitmentsofTraders/
        - Quandl: Historical COT data
        """
        if os.path.exists(self.data_path):
            with open(self.data_path, 'r') as f:
                self.cot_data = json.load(f)
            return self.cot_data
        
        # Simulated data structure for demo
        self.cot_data = {
            'EURUSD': {
                'commercial_net': 50000,     # Commercials net long
                'speculator_net': -30000,    # Speculators net short
                'retail_net': -20000,        # Retail net short
                'commercial_change': 15000,  # Weekly change
                'historical_percentile': 0.75,  # 75th percentile = moderately bullish
                'last_update': datetime.now().isoformat()
            },
            'GBPUSD': {
                'commercial_net': -40000,
                'speculator_net': 25000,
                'retail_net': 15000,
                'commercial_change': -10000,
                'historical_percentile': 0.35,
                'last_update': datetime.now().isoformat()
            },
            'XAUUSD': {
                'commercial_net': -120000,   # Gold commercials usually short (producers hedging)
                'speculator_net': 100000,
                'retail_net': 20000,
                'commercial_change': -5000,
                'historical_percentile': 0.25,
                'last_update': datetime.now().isoformat()
            },
            'USDCAD': {
                'commercial_net': 30000,
                'speculator_net': -25000,
                'retail_net': -5000,
                'commercial_change': 8000,
                'historical_percentile': 0.68,
                'last_update': datetime.now().isoformat()
            }
        }
        
        return self.cot_data
    
    def analyze_symbol(self, symbol: str) -> Dict:
        """
        Analyze COT positioning for a specific symbol.
        """
        if not self.cot_data:
            self.load_cot_data()
        
        # Map forex pairs to COT contracts
        symbol_map = {
            'EURUSD': 'EURUSD',
            'GBPUSD': 'GBPUSD',
            'XAUUSD': 'XAUUSD',
            'USDCAD': 'USDCAD',
            'GER30': 'EURUSD',  # Use EUR as proxy
            'USDJPY': 'USDJPY'
        }
        
        cot_symbol = symbol_map.get(symbol, symbol)
        
        if cot_symbol not in self.cot_data:
            return {
                'signal': 'NO_DATA',
                'commercial_bias': 'UNKNOWN',
                'extreme_positioning': False,
                'confidence': 0.0
            }
        
        data = self.cot_data[cot_symbol]
        
        # Analyze commercial positioning
        percentile = data['historical_percentile']
        change = data['commercial_change']
        
        # Extreme positioning
        is_extreme_long = percentile >= self.extreme_percentile_high
        is_extreme_short = percentile <= self.extreme_percentile_low
        is_extreme = is_extreme_long or is_extreme_short
        
        # Commercial bias
        if data['commercial_net'] > 0:
            commercial_bias = 'BULLISH'
        elif data['commercial_net'] < 0:
            commercial_bias = 'BEARISH'
        else:
            commercial_bias = 'NEUTRAL'
        
        # Commercial momentum (are they adding or reducing?)
        if change > 0:
            commercial_momentum = 'INCREASING_LONGS'
        elif change < 0:
            commercial_momentum = 'INCREASING_SHORTS'
        else:
            commercial_momentum = 'FLAT'
        
        # Generate signal
        signal = 'NEUTRAL'
        confidence = 0.5
        
        if is_extreme_long:
            signal = 'STRONG_BULLISH'  # Commercials extremely bullish
            confidence = 0.85
        elif is_extreme_short:
            signal = 'STRONG_BEARISH'  # Commercials extremely bearish
            confidence = 0.85
        elif percentile > 0.65:
            signal = 'BULLISH'
            confidence = 0.65
        elif percentile < 0.35:
            signal = 'BEARISH'
            confidence = 0.65
        
        # Flip detection (major signal)
        # If commercials changed direction significantly
        if abs(change) > 20000:
            if change > 0:
                signal = 'COMMERCIAL_FLIP_BULLISH'
                confidence = 0.9
            else:
                signal = 'COMMERCIAL_FLIP_BEARISH'
                confidence = 0.9
        
        return {
            'signal': signal,
            'commercial_bias': commercial_bias,
            'commercial_net': data['commercial_net'],
            'commercial_change': change,
            'commercial_momentum': commercial_momentum,
            'historical_percentile': percentile,
            'extreme_positioning': is_extreme,
            'is_extreme_long': is_extreme_long,
            'is_extreme_short': is_extreme_short,
            'confidence': confidence,
            'speculator_net': data['speculator_net'],
            'retail_net': data['retail_net']
        }
    
    def get_speculator_crowding(self, symbol: str) -> Dict:
        """
        Detect speculator crowding - when speculators are all on one side.
        This is a reversal warning - fade the crowd.
        """
        if not self.cot_data:
            self.load_cot_data()
        
        if symbol not in self.cot_data:
            return {'crowding_detected': False}
        
        data = self.cot_data[symbol]
        
        spec_net = data['speculator_net']
        retail_net = data['retail_net']
        
        # Crowding: Speculators and retail on same side with large positions
        same_side = (spec_net > 0 and retail_net > 0) or (spec_net < 0 and retail_net < 0)
        total_spec_retail = abs(spec_net) + abs(retail_net)
        
        crowding_detected = same_side and total_spec_retail > 80000
        
        if crowding_detected:
            if spec_net > 0:
                crowding_direction = 'LONG'
                fade_signal = 'BEARISH'  # Fade the long crowd
            else:
                crowding_direction = 'SHORT'
                fade_signal = 'BULLISH'  # Fade the short crowd
        else:
            crowding_direction = 'NONE'
            fade_signal = 'NEUTRAL'
        
        return {
            'crowding_detected': crowding_detected,
            'crowding_direction': crowding_direction,
            'fade_signal': fade_signal,
            'speculator_net': spec_net,
            'retail_net': retail_net
        }
    
    def analyze(self, symbol: str) -> Dict:
        """
        Full COT analysis for a symbol.
        """
        positioning = self.analyze_symbol(symbol)
        crowding = self.get_speculator_crowding(symbol)
        
        # Combine signals
        if positioning['signal'] in ['COMMERCIAL_FLIP_BULLISH', 'COMMERCIAL_FLIP_BEARISH']:
            final_signal = positioning['signal']
            final_confidence = positioning['confidence']
        elif crowding['crowding_detected']:
            # Crowding warning
            final_signal = f"CROWDING_WARNING_{crowding['fade_signal']}"
            final_confidence = 0.75
        else:
            final_signal = positioning['signal']
            final_confidence = positioning['confidence']
        
        return {
            'positioning': positioning,
            'crowding': crowding,
            'final_signal': final_signal,
            'final_confidence': final_confidence,
            'recommendation': self._get_recommendation(positioning, crowding)
        }
    
    def _get_recommendation(self, positioning: Dict, crowding: Dict) -> str:
        """Generate human-readable recommendation."""
        
        if positioning['signal'] == 'NO_DATA':
            return 'No COT data available for this symbol'
        
        parts = []
        
        # Commercial positioning
        if positioning['extreme_positioning']:
            if positioning['is_extreme_long']:
                parts.append('COMMERCIALS EXTREME LONG - Strong bullish bias')
            else:
                parts.append('COMMERCIALS EXTREME SHORT - Strong bearish bias')
        else:
            parts.append(f"Commercials {positioning['commercial_bias'].lower()} ({positioning['historical_percentile']:.0%})")
        
        # Momentum
        parts.append(f"Momentum: {positioning['commercial_momentum'].replace('_', ' ').lower()}")
        
        # Crowding
        if crowding['crowding_detected']:
            parts.append(f"⚠️ CROWDING: Fade the {crowding['crowding_direction'].lower()} crowd")
        
        return ' | '.join(parts)


# Quick test
if __name__ == "__main__":
    analyzer = COTAnalyzer()
    
    # Test with EUR
    result = analyzer.analyze('EURUSD')
    
    print("COT Analysis for EURUSD:")
    print(f"  Commercial Net: {result['positioning']['commercial_net']:,}")
    print(f"  Commercial Bias: {result['positioning']['commercial_bias']}")
    print(f"  Historical Percentile: {result['positioning']['historical_percentile']:.0%}")
    print(f"  Extreme Positioning: {result['positioning']['extreme_positioning']}")
    print(f"  Final Signal: {result['final_signal']}")
    print(f"  Confidence: {result['final_confidence']:.0%}")
    print(f"  Recommendation: {result['recommendation']}")
