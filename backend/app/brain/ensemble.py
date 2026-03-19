"""
INSTITUTIONAL EDGE - ENSEMBLE BRAIN SYSTEM
==========================================
Phase 5 Upgrade: Trains 3 models on different time horizons.
Uses confidence-weighted majority voting for final signal.
"""

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
import os
import json
from datetime import datetime

from app.brain.model import InstitutionalBrain, TransformerBrain, LiteBrain
from app.brain.feature_engine import InstitutionalFeatureEngine


class EnsembleTrainer:
    """
    Trains 3 specialized models on different time horizons:
    1. Short-term (2 months) - Catches recent trends
    2. Medium-term (6 months) - Balanced view
    3. Long-term (12 months) - Captures regime patterns
    """
    
    def __init__(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.feature_engine = InstitutionalFeatureEngine()
        
        # Three specialized models
        self.models = {
            'short': InstitutionalBrain(input_size=40).to(self.device),
            'medium': TransformerBrain(input_size=40).to(self.device),
            'long': LiteBrain(input_size=40).to(self.device)
        }
        
        self.optimizers = {
            name: optim.Adam(model.parameters(), lr=0.001)
            for name, model in self.models.items()
        }
        
        self.criterion = nn.CrossEntropyLoss()
        self.history = []
        
    def fetch_data(self, symbol: str, period: str) -> pd.DataFrame:
        """Fetch market data for given period."""
        import yfinance as yf
        
        ticker_map = {
            'EURUSD': 'EURUSD=X', 'GBPUSD': 'GBPUSD=X',
            'XAUUSD': 'GC=F', 'USDCAD': 'USDCAD=X',
            'GER30': '^GDAXI', 'BTCUSD': 'BTC-USD',
            'SPX500': '^GSPC', 'NAS100': '^NDX',
            'GOLD': 'GC=F'
        }
        
        ticker = ticker_map.get(symbol, symbol)
        data = yf.download(ticker, period=period, interval='1h', progress=False)
        
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
            
        return data.reset_index()[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)
    
    def generate_labels(self, df: pd.DataFrame, lookahead: int = 5) -> np.ndarray:
        """Generate target labels based on future price movement."""
        close = df['Close'].values
        labels = np.zeros(len(close))
        threshold = 0.0010  # 10 pips
        
        for i in range(len(close) - lookahead):
            current = close[i]
            future = close[i + lookahead]
            change = (future - current) / current
            
            if change > threshold:
                labels[i] = 2  # BUY
            elif change < -threshold:
                labels[i] = 0  # SELL
            else:
                labels[i] = 1  # HOLD
                
        return labels
    
    def train_single_model(self, model_name: str, symbol: str, period: str, episodes: int = 50) -> Dict:
        """Train a single model on specified period."""
        model = self.models[model_name]
        optimizer = self.optimizers[model_name]
        model.train()
        
        print(f"\n🧠 Training {model_name.upper()} model on {symbol} ({period})...")
        
        try:
            df = self.fetch_data(symbol, period)
            if len(df) < 200:
                return {'status': 'error', 'message': f'Insufficient data for {period}'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
        
        # Generate features and labels
        X_list = []
        window = min(100, len(df) - 50)
        
        for i in range(50, len(df) - 5):
            subset = df.iloc[:i+1]
            feats = self.feature_engine.extract_features(subset, symbol)['features']
            X_list.append(feats)
        
        y_list = self.generate_labels(df)[50:len(df)-5]
        
        min_len = min(len(X_list), len(y_list))
        X = torch.FloatTensor(np.array(X_list[:min_len])).unsqueeze(1).to(self.device)
        y = torch.LongTensor(y_list[:min_len]).to(self.device)
        
        losses = []
        for ep in range(episodes):
            optimizer.zero_grad()
            logits, _ = model(X)
            loss = self.criterion(logits, y)
            loss.backward()
            optimizer.step()
            losses.append(loss.item())
            
            if ep % 10 == 0:
                print(f"  Episode {ep}/{episodes}, Loss: {loss.item():.4f}")
        
        return {
            'status': 'success',
            'model': model_name,
            'final_loss': losses[-1],
            'samples': min_len
        }
    
    def train_ensemble(self, symbol: str) -> Dict:
        """Train all 3 models in the ensemble."""
        results = {}
        
        # Short-term: 2 months
        results['short'] = self.train_single_model('short', symbol, '2mo', episodes=50)
        
        # Medium-term: 6 months
        results['medium'] = self.train_single_model('medium', symbol, '6mo', episodes=75)
        
        # Long-term: 12 months
        results['long'] = self.train_single_model('long', symbol, '1y', episodes=100)
        
        # Log history
        self.history.append({
            'timestamp': datetime.now().isoformat(),
            'symbol': symbol,
            'results': results
        })
        
        # Save history
        history_path = os.path.join(os.path.dirname(__file__), 'training_history.json')
        with open(history_path, 'w') as f:
            json.dump(self.history, f, indent=2)
        
        return {'status': 'complete', 'models': results}
    
    def save_models(self, path: str = None):
        """Save all models to disk."""
        if path is None:
            path = os.path.dirname(__file__)
        
        for name, model in self.models.items():
            torch.save(model.state_dict(), os.path.join(path, f'{name}_brain.pth'))
        
        print(f"✅ Saved all ensemble models to {path}")
    
    def load_models(self, path: str = None):
        """Load all models from disk."""
        if path is None:
            path = os.path.dirname(__file__)
        
        for name, model in self.models.items():
            model_path = os.path.join(path, f'{name}_brain.pth')
            if os.path.exists(model_path):
                model.load_state_dict(torch.load(model_path, map_location=self.device))
                print(f"✅ Loaded {name} model")


class EnsemblePredictor:
    """
    Uses trained ensemble for predictions.
    Implements confidence-weighted majority voting.
    """
    
    def __init__(self, trainer: EnsembleTrainer = None):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        if trainer:
            self.models = trainer.models
        else:
            # Initialize fresh models
            self.models = {
                'short': InstitutionalBrain(input_size=40).to(self.device),
                'medium': TransformerBrain(input_size=40).to(self.device),
                'long': LiteBrain(input_size=40).to(self.device)
            }
            self.load_models()
    
    def load_models(self, path: str = None):
        """Load models from disk."""
        if path is None:
            path = os.path.dirname(__file__)
        
        for name, model in self.models.items():
            model_path = os.path.join(path, f'{name}_brain.pth')
            if os.path.exists(model_path):
                model.load_state_dict(torch.load(model_path, map_location=self.device))
    
    def predict(self, features: np.ndarray) -> Dict:
        """
        Make ensemble prediction using confidence-weighted voting.
        
        Args:
            features: 40-dimensional feature vector
            
        Returns:
            Dict with signal, confidence, and individual model votes
        """
        x = torch.FloatTensor(features).unsqueeze(0).to(self.device)
        
        votes = {'SELL': 0.0, 'HOLD': 0.0, 'BUY': 0.0}
        individual_preds = {}
        
        for name, model in self.models.items():
            model.eval()
            pred = model.predict(x)
            
            # Weight vote by confidence
            signal = pred['signal']
            confidence = pred['confidence']
            votes[signal] += confidence
            
            individual_preds[name] = {
                'signal': signal,
                'confidence': confidence
            }
        
        # Determine final signal
        final_signal = max(votes, key=votes.get)
        total_confidence = sum(votes.values())
        final_confidence = votes[final_signal] / total_confidence if total_confidence > 0 else 0
        
        return {
            'signal': final_signal,
            'confidence': final_confidence,
            'ensemble_votes': votes,
            'individual_predictions': individual_preds,
            'agreement': sum(1 for p in individual_preds.values() if p['signal'] == final_signal) / 3
        }


# Singleton instances for global access
ensemble_trainer = None
ensemble_predictor = None

def get_trainer() -> EnsembleTrainer:
    """Get or create ensemble trainer."""
    global ensemble_trainer
    if ensemble_trainer is None:
        ensemble_trainer = EnsembleTrainer()
    return ensemble_trainer

def get_predictor() -> EnsemblePredictor:
    """Get or create ensemble predictor."""
    global ensemble_predictor
    if ensemble_predictor is None:
        ensemble_predictor = EnsemblePredictor()
    return ensemble_predictor


if __name__ == "__main__":
    print("Testing Ensemble System...")
    
    trainer = EnsembleTrainer()
    
    # Test prediction with random features
    predictor = EnsemblePredictor(trainer)
    test_features = np.random.randn(40)
    result = predictor.predict(test_features)
    
    print(f"\nEnsemble Prediction:")
    print(f"  Signal: {result['signal']}")
    print(f"  Confidence: {result['confidence']:.2%}")
    print(f"  Agreement: {result['agreement']:.0%}")
    print(f"  Votes: {result['ensemble_votes']}")
