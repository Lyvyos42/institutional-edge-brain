"""
FIX TIME FILTER - Trade the London Fix Reversal
================================================
Institutional Secret: Banks front-run the 4PM London Fix.
Price spikes into the fix, then reverses after 4:00-4:05 PM.

This was proven in court - banks have paid $10B+ in fines for this manipulation.
"""

import numpy as np
import pandas as pd
from datetime import datetime, time
from typing import Dict


class FixTimeFilter:
    """
    Detects and trades the London Fix manipulation pattern.
    
    Key Times (London/GMT):
    - 4:00 PM London = WM Reuters Fix (Main one)
    - 11:00 AM London = ECB Fix
    - 3:00 PM London = Pre-positioning starts
    
    Pattern:
    1. Large orders pile up for the fix
    2. Banks see these orders and front-run them
    3. Price spikes into fix time
    4. Immediately after fix, price reverses
    """
    
    def __init__(self, timezone_offset: int = 0):
        """
        Args:
            timezone_offset: Hours offset from UTC (e.g., +2 for EET)
        """
        self.timezone_offset = timezone_offset
        
        # Fix times in UTC
        self.fix_times = {
            'london_fix': time(16, 0),      # 4:00 PM London (main)
            'ecb_fix': time(11, 0),         # 11:00 AM ECB
            'tokyo_fix': time(0, 55),       # Tokyo Fix (9:55 AM Tokyo = 00:55 UTC)
            'ny_close': time(21, 0),        # NY close
        }
        
        # Danger zones (avoid trading)
        self.danger_windows = {
            'pre_london_fix': (time(15, 30), time(16, 0)),   # 30 min before fix
            'pre_ecb_fix': (time(10, 30), time(11, 0)),      # 30 min before ECB
        }
        
        # Reversal windows (good to trade)
        self.reversal_windows = {
            'post_london_fix': (time(16, 5), time(16, 30)),   # 5-30 min after fix
            'post_ecb_fix': (time(11, 5), time(11, 30)),      # 5-30 min after ECB
        }
    
    def get_current_utc_time(self) -> time:
        """Get current UTC time."""
        now = datetime.utcnow()
        return now.time()
    
    def time_in_window(self, current: time, start: time, end: time) -> bool:
        """Check if current time is within window."""
        if start <= end:
            return start <= current <= end
        else:  # Window crosses midnight
            return current >= start or current <= end
    
    def is_fix_time(self, current_time: time = None) -> Dict:
        """
        Check if we're near a fix time.
        
        Returns danger level and which fix we're near.
        """
        if current_time is None:
            current_time = self.get_current_utc_time()
        
        result = {
            'is_danger_zone': False,
            'is_reversal_zone': False,
            'fix_name': None,
            'minutes_to_fix': None,
            'action': 'NORMAL'
        }
        
        # Check danger zones
        for name, (start, end) in self.danger_windows.items():
            if self.time_in_window(current_time, start, end):
                result['is_danger_zone'] = True
                result['fix_name'] = name
                result['action'] = 'AVOID_NEW_TRADES'
                return result
        
        # Check reversal zones
        for name, (start, end) in self.reversal_windows.items():
            if self.time_in_window(current_time, start, end):
                result['is_reversal_zone'] = True
                result['fix_name'] = name
                result['action'] = 'LOOK_FOR_REVERSAL'
                return result
        
        return result
    
    def analyze_fix_pattern(self, df: pd.DataFrame, fix_time_str: str = "16:00") -> Dict:
        """
        Analyze price action around fix times to detect manipulation pattern.
        
        Pattern: Price runs up into fix, then reverses after.
        """
        if 'Datetime' not in df.columns and df.index.name != 'Datetime':
            return {
                'pattern_detected': False,
                'message': 'Need datetime index for fix analysis'
            }
        
        close = df['Close'].values
        
        # This is a simplified detection - in production you'd use timestamps
        # Look for volatility spike followed by reversal
        
        if len(close) < 10:
            return {'pattern_detected': False}
        
        # Last 10 bars
        recent = close[-10:]
        
        # Check for spike and reversal pattern
        max_idx = np.argmax(recent)
        min_idx = np.argmin(recent)
        
        # Bullish reversal: Low in first half, then up
        bullish_reversal = min_idx < 5 and close[-1] > recent[min_idx] * 1.001
        
        # Bearish reversal: High in first half, then down
        bearish_reversal = max_idx < 5 and close[-1] < recent[max_idx] * 0.999
        
        if bullish_reversal:
            pattern = 'BULLISH_FIX_REVERSAL'
        elif bearish_reversal:
            pattern = 'BEARISH_FIX_REVERSAL'
        else:
            pattern = 'NONE'
        
        return {
            'pattern_detected': pattern != 'NONE',
            'pattern': pattern,
            'spike_size': (np.max(recent) - np.min(recent)) / close[-1] * 100
        }
    
    def get_trading_session(self, current_time: time = None) -> Dict:
        """
        Identify current trading session and its characteristics.
        """
        if current_time is None:
            current_time = self.get_current_utc_time()
        
        hour = current_time.hour
        
        if 0 <= hour < 7:
            session = 'ASIAN'
            volatility = 'LOW'
            liquidity = 'MEDIUM'
        elif 7 <= hour < 12:
            session = 'LONDON_MORNING'
            volatility = 'HIGH'
            liquidity = 'HIGH'
        elif 12 <= hour < 16:
            session = 'LONDON_NY_OVERLAP'
            volatility = 'VERY_HIGH'
            liquidity = 'VERY_HIGH'
        elif 16 <= hour < 21:
            session = 'NY_AFTERNOON'
            volatility = 'MEDIUM'
            liquidity = 'HIGH'
        else:
            session = 'LATE_NY'
            volatility = 'LOW'
            liquidity = 'LOW'
        
        return {
            'session': session,
            'volatility': volatility,
            'liquidity': liquidity,
            'hour_utc': hour
        }
    
    def detect_causal_anomaly(self, df: pd.DataFrame) -> Dict:
        """
        Phase 33: Temporal CRISPR (Causal Imprinting).
        Detects if Price moves *before* Liquidity arrives (Phantom Prints).
        Logic: High Price Velocity with Low Volume = Causal Anomaly (Retroactive Print).
        """
        if len(df) < 10: return {'anomaly_detected': False}
        
        close = df['Close'].values[-10:]
        volume = df['Volume'].values[-10:]
        
        price_velocity = np.abs(np.diff(close))
        avg_vel = np.mean(price_velocity) + 1e-9
        avg_vol = np.mean(volume) + 1e-9
        
        # Check latest bar
        latest_vel = price_velocity[-1]
        latest_vol = volume[-1]
        
        is_anomaly = False
        # If Price moved 3x normal speed...
        if latest_vel > avg_vel * 3.0:
            # But Volume was < 50% normal...
            if latest_vol < avg_vol * 0.5:
                # The price moved without fuel = Causal Breach
                is_anomaly = True
                
        return {
            'anomaly_detected': is_anomaly,
            'signal': 'CAUSAL_ANOMALY' if is_anomaly else 'NONE',
            'type': 'RETROACTIVE_PRINT' if is_anomaly else 'NORMAL'
        }

    def analyze(self, df: pd.DataFrame = None) -> Dict:
        """
        Full fix time analysis.
        """
        current_time = self.get_current_utc_time()
        
        fix_status = self.is_fix_time(current_time)
        session = self.get_trading_session(current_time)
        
        # Pattern analysis if data provided
        pattern = {'pattern_detected': False}
        causal = {'anomaly_detected': False} # Phase 33
        
        if df is not None and len(df) > 10:
            pattern = self.analyze_fix_pattern(df)
            causal = self.detect_causal_anomaly(df)
        
        return {
            'current_time_utc': current_time.strftime('%H:%M'),
            'fix_status': fix_status,
            'session': session,
            'pattern': pattern,
            'causal_analysis': causal,
            'recommendation': self._get_recommendation(fix_status, session)
        }
    
    def _get_recommendation(self, fix_status: Dict, session: Dict) -> str:
        """Generate trading recommendation based on fix and session analysis."""
        
        if fix_status['is_danger_zone']:
            return 'AVOID - Near fix time, expect manipulation'
        
        if fix_status['is_reversal_zone']:
            return 'LOOK FOR REVERSAL - Post-fix period, fade the move'
        
        if session['session'] == 'LONDON_NY_OVERLAP':
            return 'OPTIMAL - Best liquidity and volatility'
        
        if session['volatility'] == 'LOW':
            return 'CAUTION - Low volatility, wider stops needed'
        
        return 'NORMAL - No special conditions'


# Quick test
if __name__ == "__main__":
    filter = FixTimeFilter()
    
    # Test with current time
    result = filter.analyze()
    
    print("Fix Time Analysis:")
    print(f"  Current UTC: {result['current_time_utc']}")
    print(f"  Session: {result['session']['session']}")
    print(f"  Volatility: {result['session']['volatility']}")
    print(f"  Fix Status: {result['fix_status']['action']}")
    print(f"  Recommendation: {result['recommendation']}")
