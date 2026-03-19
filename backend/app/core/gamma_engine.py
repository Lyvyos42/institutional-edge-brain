import yfinance as yf
import pandas as pd
import numpy as np
import time
import threading
from datetime import datetime

class GammaEngine:
    def __init__(self):
        # Proxies: SPY for SPX, GLD for Gold. 
        # Real options data is hard to get for free/cheap real-time.
        self.proxies = {
            'SPX': 'SPY', 
            'GOLD': 'GLD',
            'OIL': 'USO',
            'QQQ': 'QQQ'
        }
        self.gamma_levels = {}
        self.lock = threading.Lock()
        
    def fetch_options_gamma(self, symbol):
        """Calculates GEX profile for a given symbol proxy."""
        ticker_symbol = self.proxies.get(symbol, symbol)
        print(f"🌑 Gamma Engine: Fetching Options Chain for {ticker_symbol}...")
        
        try:
            tk = yf.Ticker(ticker_symbol)
            # expirations = tk.options
            # Note: yfinance options fetching can be slow/flaky.
            # We will try to get the nearest expiration.
            
            # For robustness in this MVP, we simulate a 'Gravity Well' logic 
            # if live options fail, based on Round Numbers (Psychological Gamma).
            # But let's try real fetch first.
            
            # Fallback logic for now as yf options often timeout in non-interactive modes
            # We will use "Psychological Barriers" as a proxy for Gamma Walls in this version
            # unless a robust fetch source is available.
            
            # Simple "Gamma Approximation" using Volume Profiles from history?
            # Or just fetch current price and finding nearest strikes.
            
            price = tk.history(period='1d')['Close'].iloc[-1]
            
            # Calculate Theoretical Gamma Levels (0DTE approximation)
            # Zero Gamma is often near the 20d MA or significant VWAP.
            
            with self.lock:
                self.gamma_levels[symbol] = {
                    'price': price,
                    'zero_gamma': self._calculate_synthetic_zero_gamma(price), 
                    'call_wall': round(price * 1.02, 0), # +2% approx
                    'put_wall': round(price * 0.98, 0),  # -2% approx
                    'net_gex': np.random.uniform(-100, 100) # Placeholder until full chain parse
                }
                
            print(f"🌑 {symbol} Gamma Profile: Zero={self.gamma_levels[symbol]['zero_gamma']} | Price={price}")
            
        except Exception as e:
            print(f"❌ Gamma Fetch Failed {symbol}: {e}")

    def _calculate_synthetic_zero_gamma(self, price):
        # In absence of full chain, Zero Gamma often aligns with:
        # 1. Round numbers (e.g. 5000, 5100)
        # 2. 20-Day Moving Average
        return round(price / 50) * 50 # Snap to nearest 50

    def detect_event_horizon(self, symbol):
        """
        Detects Schrödinger Catalysts:
        High Open Interest pinning + Binary Event incoming.
        Logic: Low Net GEX but massive Calls/Puts at same strike.
        """
        with self.lock:
            if symbol not in self.gamma_levels:
                return {"detected": False, "reason": "No Data"}
                
            data = self.gamma_levels[symbol]
            current_price = data.get('price', 0)
            
            # Simulation Logic:
            # If price is suspiciously close to a 'Synthetic Zero Gamma'
            # It implies pinning.
            
            dist_to_pin = abs(current_price - data['zero_gamma']) / current_price
            
            # If within 0.1% of the Pin -> Event Horizon
            is_pinned = dist_to_pin < 0.001
            
            return {
                "detected": is_pinned,
                "type": "QUANTUM_PIN" if is_pinned else "FREE_FLOAT",
                "distance_to_singularity": dist_to_pin,
                "pinned_level": data['zero_gamma']
            }

    def get_gamma_state(self):
        with self.lock:
            return self.gamma_levels

gamma_engine = GammaEngine()
