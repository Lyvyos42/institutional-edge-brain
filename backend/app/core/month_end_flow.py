"""
MONTH-END REBALANCING FLOW - Trade Forced Institutional Flows
=============================================================
Institutional Secret: Pension funds and asset managers MUST rebalance 
at month-end/quarter-end. This isn't optional - it's legally required.

These flows are predictable:
- If stocks went up all month → They must sell stocks, buy bonds
- If USD went up all month → They must sell USD to rebalance FX hedges

Last 3-5 trading days of the month = HUGE predictable flows
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict
import calendar


class MonthEndFlow:
    """
    Predicts and detects month-end/quarter-end rebalancing flows.
    
    Theory:
    - Pension funds hold target allocations (e.g., 60% stocks, 40% bonds)
    - If stocks outperform, they become overweight and must sell
    - This selling happens in last 3-5 days of month
    - Creates predictable counter-trend moves
    
    Quarter-end is 3x stronger than month-end.
    Year-end is 5x stronger.
    """
    
    def __init__(self):
        """Initialize with calendar calculations."""
        pass
    
    def get_trading_days_to_month_end(self, date: datetime = None) -> int:
        """
        Calculate trading days remaining until month end.
        """
        if date is None:
            date = datetime.now()
        
        # Get last day of month
        _, last_day = calendar.monthrange(date.year, date.month)
        month_end = datetime(date.year, date.month, last_day)
        
        # Count trading days (exclude weekends)
        trading_days = 0
        current = date
        while current <= month_end:
            if current.weekday() < 5:  # Monday = 0, Friday = 4
                trading_days += 1
            current += timedelta(days=1)
        
        return trading_days
    
    def is_rebalancing_window(self, date: datetime = None) -> Dict:
        """
        Check if we're in month-end rebalancing window.
        
        Returns intensity based on calendar:
        - Last 5 days of month = rebalancing window
        - Quarter-end = 3x intensity
        - Year-end = 5x intensity
        """
        if date is None:
            date = datetime.now()
        
        trading_days_left = self.get_trading_days_to_month_end(date)
        month = date.month
        
        # Determine intensity
        is_quarter_end = month in [3, 6, 9, 12]
        is_year_end = month == 12
        
        if trading_days_left <= 5:
            in_window = True
            if is_year_end:
                intensity = 'EXTREME'
                multiplier = 5.0
            elif is_quarter_end:
                intensity = 'HIGH'
                multiplier = 3.0
            else:
                intensity = 'MODERATE'
                multiplier = 1.0
        else:
            in_window = False
            intensity = 'NONE'
            multiplier = 0.0
        
        return {
            'in_rebalancing_window': in_window,
            'trading_days_to_month_end': trading_days_left,
            'intensity': intensity,
            'multiplier': multiplier,
            'is_quarter_end': is_quarter_end,
            'is_year_end': is_year_end
        }
    
    def predict_flow_direction(self, df: pd.DataFrame) -> Dict:
        """
        Predict rebalancing flow direction based on month's performance.
        
        If an asset went UP all month → Expect SELLING pressure at month-end
        If an asset went DOWN all month → Expect BUYING pressure at month-end
        
        This is counter-trend trading with institutional backing.
        """
        if len(df) < 20:
            return {
                'flow_direction': 'UNKNOWN',
                'mtd_return': 0.0,
                'confidence': 0.0
            }
        
        close = df['Close'].values
        
        # Calculate month-to-date return (approx using last 20 bars)
        mtd_return = (close[-1] - close[-20]) / close[-20] * 100
        
        # Strong move = Strong rebalancing flow
        if mtd_return > 3:
            flow_direction = 'SELL'  # Was up → Will sell to rebalance
            confidence = min(abs(mtd_return) / 5, 1.0)
        elif mtd_return < -3:
            flow_direction = 'BUY'  # Was down → Will buy to rebalance
            confidence = min(abs(mtd_return) / 5, 1.0)
        else:
            flow_direction = 'NEUTRAL'
            confidence = 0.3
        
        return {
            'flow_direction': flow_direction,
            'mtd_return': mtd_return,
            'confidence': confidence
        }
    
    def analyze(self, df: pd.DataFrame = None, date: datetime = None) -> Dict:
        """
        Full month-end rebalancing analysis.
        """
        window = self.is_rebalancing_window(date)
        
        if df is not None and len(df) >= 20:
            flow = self.predict_flow_direction(df)
        else:
            flow = {'flow_direction': 'UNKNOWN', 'mtd_return': 0, 'confidence': 0}
        
        # Generate signal
        if window['in_rebalancing_window'] and flow['flow_direction'] != 'UNKNOWN':
            if flow['flow_direction'] == 'BUY':
                signal = 'BULLISH_REBALANCING'
            elif flow['flow_direction'] == 'SELL':
                signal = 'BEARISH_REBALANCING'
            else:
                signal = 'NEUTRAL'
            
            # Adjusted confidence based on intensity
            adjusted_confidence = flow['confidence'] * (1 + window['multiplier'] * 0.2)
        else:
            signal = 'NO_REBALANCING'
            adjusted_confidence = 0
        
        return {
            'window': window,
            'flow': flow,
            'signal': signal,
            'adjusted_confidence': min(adjusted_confidence, 1.0),
            'recommendation': self._get_recommendation(window, flow)
        }
    
    def _get_recommendation(self, window: Dict, flow: Dict) -> str:
        """Generate trading recommendation."""
        
        if not window['in_rebalancing_window']:
            return 'Normal trading - no month-end effects'
        
        if window['is_year_end']:
            prefix = 'YEAR-END REBALANCING: '
        elif window['is_quarter_end']:
            prefix = 'QUARTER-END: '
        else:
            prefix = 'MONTH-END: '
        
        if flow['flow_direction'] == 'BUY':
            return f"{prefix}Expect buying pressure - MTD was {flow['mtd_return']:.1f}%"
        elif flow['flow_direction'] == 'SELL':
            return f"{prefix}Expect selling pressure - MTD was {flow['mtd_return']:.1f}%"
        else:
            return f"{prefix}Mixed signals, trade cautiously"


# Quick test
if __name__ == "__main__":
    flow_detector = MonthEndFlow()
    
    # Test with sample data
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(30) * 0.5)  # Simulate slight uptrend
    df = pd.DataFrame({'Close': close})
    
    result = flow_detector.analyze(df)
    
    print("Month-End Flow Analysis:")
    print(f"  In Window: {result['window']['in_rebalancing_window']}")
    print(f"  Days to Month End: {result['window']['trading_days_to_month_end']}")
    print(f"  Intensity: {result['window']['intensity']}")
    print(f"  Predicted Flow: {result['flow']['flow_direction']}")
    print(f"  MTD Return: {result['flow']['mtd_return']:.1f}%")
    print(f"  Signal: {result['signal']}")
    print(f"  Recommendation: {result['recommendation']}")
