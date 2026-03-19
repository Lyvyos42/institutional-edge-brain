"""
WAVELET ANALYZER - The Eye of the Frequency Domain
==================================================
Standard charts show PRICE vs TIME.
Wavelets show ENERGY vs FREQUENCY vs TIME.

We use a Discrete Haar Transform (DHT) to decompose the market into:
- Approximation Coefficients (Trend/Low Freq) => The "Narrative"
- Detail Coefficients (Noise/High Freq) => The "Hidden Energy"

Anomaly Detection:
When Price is flat (Low Volatility) but High-Freq Energy is spiking,
it means "Invisible Force" is entering.
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple

class WaveletAnalyzer:
    """
    Decomposes time series into energy packets using Haar Wavelets.
    """
    def __init__(self):
        pass

    def haar_transform(self, data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Single-level Discrete Haar Transform.
        Returns (Approximation, Detail).
        """
        if len(data) % 2 != 0:
            data = data[:-1] # Truncate to even length
            
        # Reshape to (N/2, 2)
        pairs = data.reshape(-1, 2)
        
        # Approximation = Average (Trend)
        approx = np.mean(pairs, axis=1) * np.sqrt(2)
        
        # Detail = Difference (Energy/Noise)
        detail = (pairs[:, 1] - pairs[:, 0]) / 2 * np.sqrt(2)
        
        return approx, detail

    def calculate_energy(self, coeffs: np.ndarray) -> float:
        """Calculate energy of coefficients."""
        return np.sum(np.square(coeffs))

    def analyze(self, df: pd.DataFrame, lookback: int = 64) -> Dict:
        """
        Perform Multi-Resolution Analysis (MRA).
        """
        if len(df) < lookback:
            return {
                'total_energy': 0.0,
                'hidden_energy': 0.0,
                'regime': 'INSUFFICIENT_DATA',
                'signal': 'NEUTRAL'
            }
            
        prices = df['Close'].values[-lookback:]
        
        # Level 1 Decomposition (Highest Freq)
        a1, d1 = self.haar_transform(prices)
        
        # Level 2 Decomposition
        a2, d2 = self.haar_transform(a1)
        
        # Level 3 Decomposition (Lower Freq)
        a3, d3 = self.haar_transform(a2)
        
        # Calculate Energy at each scale
        e1 = self.calculate_energy(d1) # High Freq Noise
        e2 = self.calculate_energy(d2) # Mid Freq
        e3 = self.calculate_energy(d3) # Low Freq
        
        trend_energy = self.calculate_energy(a3)
        
        # Relative Energies
        total_energy = e1 + e2 + e3 + trend_energy + 1e-9
        hf_ratio = (e1 + e2) / total_energy
        
        # Anomaly Detection: "The Coiled Spring"
        # High HF Energy but flat price (Low Trend Energy)
        # This implies huge fighting/transacting within a tight range.
        
        is_hidden_energy = False
        if hf_ratio > 0.4 and trend_energy < total_energy * 0.3:
            is_hidden_energy = True
            
        signal = 'NEUTRAL'
        regime = 'NORMAL'
        
        if is_hidden_energy:
            signal = 'HIDDEN_ENERGY_DETECTED'
            regime = 'COILING'
        elif trend_energy > total_energy * 0.8:
             regime = 'TRENDING'
             
        return {
            'total_energy': round(float(total_energy), 2),
            'hf_energy': round(float(e1+e2), 2),
            'trend_energy': round(float(trend_energy), 2),
            'hf_ratio': round(float(hf_ratio), 4),
            'signal': signal,
            'regime': regime
        }

# Singleton
wavelet = WaveletAnalyzer()
