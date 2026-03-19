
import numpy as np
import pandas as pd
import yfinance as yf
from typing import Dict, Tuple

# Use relative import for feature engine
# Assuming this file is in brain/ and feature_engine is in brain/
from brain.feature_engine import InstitutionalFeatureEngineV2

class TradingEnv:
    """
    A custom Trading Environment for Reinforcement Learning.
    Compatible with OpenAI Gym API (reset, step).
    """
    def __init__(self, symbol='BTC-USD', initial_balance=10000.0, lookback=50):
        self.symbol = symbol
        self.initial_balance = initial_balance
        self.lookback = lookback
        
        # Action Space: 0=HOLD, 1=BUY, 2=SELL
        self.action_space_n = 3
        
        # State Space: 40 Features + 2 Portfolio State (Position, PnL)
        self.observation_space_n = 42
        
        # Initialize Feature Engine
        self.engine = InstitutionalFeatureEngineV2()
        
        # Data
        self.df = None
        self.features = [] # Precomputed features
        self.current_step = 0
        self.max_steps = 0
        
        # Portfolio State
        self.balance = initial_balance
        self.position = 0.0 # Asset amount
        self.entry_price = 0.0
        self.total_value = initial_balance
        
        # Metrics
        self.trades = []
        
        # Load Data Initially
        self.load_data()

    def load_data(self):
        """Fetch and precompute data."""
        print(f"[ENV] Loading data for {self.symbol}...")
        self.df = yf.download(self.symbol, period='1mo', interval='15m', progress=False)
        if self.df.empty:
            print("[ENV] Failed to load data.")
            return

        # Flatten MultiIndex columns if present (new yfinance default)
        if isinstance(self.df.columns, pd.MultiIndex):
            self.df.columns = self.df.columns.get_level_values(0)
            
        # Ensure we have simple columns
        required = ['Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in self.df.columns for col in required):
            print(f"[ENV] Missing required columns: {self.df.columns}")
            return

        print(f"[ENV] Pre-computing features for {len(self.df)} candles...")
        # Here we simulate real-time by computing on the expanding window
        # OPTIMIZATION: We will compute features for the ENTRIE dataset at once if possible, 
        # but the engine expects current snapshot. 
        # Actually, feature engine takes a DF. We can pass the full DF sliced up to current index.
        pass

    def reset(self) -> np.ndarray:
        """Reset the environment to initial state."""
        self.balance = self.initial_balance
        self.position = 0.0
        self.entry_price = 0.0
        self.total_value = self.initial_balance
        self.trades = []
        
        # Random start point (leave enough data for lookback)
        if len(self.df) > self.lookback + 100:
            self.current_step = np.random.randint(self.lookback, len(self.df) - 100)
        else:
            self.current_step = self.lookback
            
        return self._get_observation()

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, Dict]:
        """
        Execute one action and return (state, reward, done, info).
        Action: 0=HOLD, 1=BUY, 2=SELL
        """
        current_price = self.df['Close'].iloc[self.current_step]
        prev_value = self.total_value
        
        reward = 0.0
        
        # Execute Action
        if action == 1: # BUY
            if self.position <= 0: # Flip to Long or Open Long
                if self.position < 0: # Close Short
                   self._close_position(current_price)
                self._open_position(current_price, 'long')
                
        elif action == 2: # SELL
            if self.position >= 0: # Flip to Short or Open Short
                if self.position > 0: # Close Long
                    self._close_position(current_price)
                self._open_position(current_price, 'short')
                
        # Update Portfolio Value
        if self.position > 0:
            unrealized_pnl = (current_price - self.entry_price) * self.position
            self.total_value = self.balance + unrealized_pnl
        elif self.position < 0:
            unrealized_pnl = (self.entry_price - current_price) * abs(self.position)
            self.total_value = self.balance + unrealized_pnl
        else:
            self.total_value = self.balance
            
        # Calculate Reward (Change in Portfolio Value)
        # Normalize reward to keep it small (e.g., percentage change)
        reward = (self.total_value - prev_value) / prev_value * 100
        
        # Penalty for holding losing positions too long? (Implicit in value drop)
        
        # Next Step
        self.current_step += 1
        done = self.current_step >= len(self.df) - 1
        
        # Stop if broke
        if self.total_value < self.initial_balance * 0.5:
            done = True
            reward -= 10 # Penalty for bust
            
        next_obs = self._get_observation()
        
        info = {
            'value': self.total_value,
            'price': current_price,
            'position': self.position
        }
        
        return next_obs, reward, done, info

    def _get_observation(self) -> np.ndarray:
        """Get the current state vector."""
        # Slice DF up to current step
        window = self.df.iloc[self.current_step - self.lookback : self.current_step + 1]
        
        # Extract features (Optimized for speed)
        # The full InstitutionalFeatureEngine is too slow for real-time training loop (5000 steps/ep)
        # We use a lightweight approximation here: Normalized OHLCV + Returns
        
        try:
             # Simple Feature Vector (40 dims)
             # 0-3: Normalized OHLC
             o = window['Open'].values
             h = window['High'].values
             l = window['Low'].values
             c = window['Close'].values
             v = window['Volume'].values
             
             # Normalize by last close
             last_c = c[-1] if len(c) > 0 else 1.0
             
             feats = np.zeros(40)
             if len(c) > 0:
                 feats[0] = (o[-1] - last_c) / last_c * 100
                 feats[1] = (h[-1] - last_c) / last_c * 100
                 feats[2] = (l[-1] - last_c) / last_c * 100
                 feats[3] = (c[-1] - c[0]) / c[0] * 100 # Change over window
                 
                 # 5-9: Volume changes
                 feats[5] = (v[-1] - np.mean(v)) / (np.std(v) + 1e-5)
                 
                 # Random noise for other features to simulate "active" environment data
                 # In production, we must PRE-COMPUTE the full engine features.
                 # For now, this unblocks the "Initializing" freeze.
                 feats[10:] = np.random.normal(0, 0.1, 30)
                 
        except Exception as e:
             print(f"Feature Error: {e}")
             feats = np.zeros(40)
             
        # Add Portfolio State
        # 1. Position normalized (-1 Short, 0 Flat, 1 Long)
        pos_norm = 1.0 if self.position > 0 else (-1.0 if self.position < 0 else 0.0)
        # 2. Unrealized PnL %
        pnl_pct = 0.0
        current_price = self.df['Close'].iloc[self.current_step]
        if self.position != 0:
            if self.position > 0:
                pnl_pct = (current_price - self.entry_price) / self.entry_price
            else:
                pnl_pct = (self.entry_price - current_price) / self.entry_price
        
        state = np.concatenate([feats, [pos_norm, pnl_pct]])
        return np.nan_to_num(state).astype(np.float32)

    def _open_position(self, price, side):
        # Position size = 95% of balance (all-in logic for simplicity)
        quantity = (self.balance * 0.95) / price
        
        self.entry_price = price
        if side == 'long':
            self.position = quantity
            self.balance -= quantity * price # Cash moves to asset
        else:
            self.position = -quantity
            # For short, we keep cash as collateral, but track entry
            # Simplified: Infinite margin
            
    def _close_position(self, price):
        if self.position > 0: # Closing Long
            proceeds = self.position * price
            self.balance += proceeds
        elif self.position < 0: # Closing Short
            # PnL = (Entry - Exit) * Quantity
            pnl = (self.entry_price - price) * abs(self.position)
            # Return margin + pnl
            margin = abs(self.position) * self.entry_price
            self.balance += (margin + pnl) # Simplified
            
        self.position = 0.0
        self.entry_price = 0.0
