"""
INSTITUTIONAL EDGE - NEURAL BRAIN MODEL
========================================
Advanced neural network architecture for institutional edge detection.

Uses a Transformer-Enhanced LSTM to process the 24-dimensional feature vector
from the InstitutionalFeatureEngine.
"""

import torch
import torch.nn as nn
import numpy as np
from typing import Dict, Tuple, Optional


class InstitutionalBrain(nn.Module):
    """
    Neural network brain for institutional edge detection.
    
    Architecture:
    - Input: 40 institutional features
    - Processing: Multi-head attention + LSTM
    - Output: 3 classes (SELL, HOLD, BUY)
    
    Key innovations:
    1. Separate attention heads for different signal types
    2. Residual connections for gradient flow
    3. Dropout for regularization
    """
    
    def __init__(
        self,
        input_size: int = 40,
        hidden_size: int = 64,
        num_heads: int = 4,
        num_layers: int = 2,
        dropout: float = 0.2,
        output_size: int = 3
    ):
        """
        Args:
            input_size: Number of input features (40 from feature engine)
            hidden_size: LSTM hidden size
            num_heads: Number of attention heads
            num_layers: Number of LSTM layers
            dropout: Dropout rate
            output_size: Number of output classes (3: SELL, HOLD, BUY)
        """
        super().__init__()
        
        self.input_size = input_size
        self.hidden_size = hidden_size
        
        # Input projection
        self.input_proj = nn.Linear(input_size, hidden_size)
        
        # Multi-head self-attention
        self.attention = nn.MultiheadAttention(
            embed_dim=hidden_size,
            num_heads=num_heads,
            dropout=dropout,
            batch_first=True
        )
        
        # Layer norm
        self.norm1 = nn.LayerNorm(hidden_size)
        self.norm2 = nn.LayerNorm(hidden_size)
        
        # LSTM for sequential processing
        self.lstm = nn.LSTM(
            input_size=hidden_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=True
        )
        
        # Feed-forward network
        self.ffn = nn.Sequential(
            nn.Linear(hidden_size * 2, hidden_size * 4),  # *2 for bidirectional
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size * 4, hidden_size)
        )
        
        # Output head
        self.output_head = nn.Sequential(
            nn.LayerNorm(hidden_size),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, output_size)
        )
        
        # Confidence head (separate)
        self.confidence_head = nn.Sequential(
            nn.Linear(hidden_size, 1),
            nn.Sigmoid()
        )
        
        self._init_weights()
    
    def _init_weights(self):
        """Initialize weights for better training."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass.
        
        Args:
            x: Input tensor of shape (batch, seq_len, input_size) or (batch, input_size)
        
        Returns:
            Tuple of (logits, confidence)
            - logits: (batch, output_size)
            - confidence: (batch, 1)
        """
        # Handle 2D input (single timestep)
        if x.dim() == 2:
            x = x.unsqueeze(1)  # (batch, 1, features)
        
        batch_size, seq_len, _ = x.shape
        
        # Input projection
        x = self.input_proj(x)  # (batch, seq, hidden)
        
        # Self-attention with residual
        attn_out, _ = self.attention(x, x, x)
        x = self.norm1(x + attn_out)
        
        # LSTM
        lstm_out, _ = self.lstm(x)  # (batch, seq, hidden*2)
        
        # Take last timestep
        x = lstm_out[:, -1, :]  # (batch, hidden*2)
        
        # Feed-forward with residual
        ffn_out = self.ffn(x)
        x = self.norm2(ffn_out)
        
        # Output
        logits = self.output_head(x)
        confidence = self.confidence_head(x)
        
        return logits, confidence
    
    def predict(self, x: torch.Tensor) -> Dict:
        """
        Make a prediction with probabilities and signal.
        
        Args:
            x: Input features
        
        Returns:
            Dict with signal, confidence, and probabilities
        """
        self.eval()
        with torch.no_grad():
            logits, confidence = self(x)
            probs = torch.softmax(logits, dim=-1)
            
            # Get prediction
            pred_idx = torch.argmax(probs, dim=-1)
            signals = ['SELL', 'HOLD', 'BUY']
            
            return {
                'signal': signals[pred_idx.item()],
                'confidence': confidence.item(),
                'probabilities': {
                    'SELL': probs[0, 0].item(),
                    'HOLD': probs[0, 1].item(),
                    'BUY': probs[0, 2].item()
                },
                'raw_confidence': probs.max().item()
            }


class TransformerBrain(nn.Module):
    """
    PHASE 4 UPGRADE: Pure Transformer Model
    ========================================
    Uses only self-attention without LSTM for different temporal pattern recognition.
    Better at capturing long-range dependencies in market data.
    """
    
    def __init__(
        self,
        input_size: int = 40,
        hidden_size: int = 64,
        num_heads: int = 4,
        num_layers: int = 3,
        dropout: float = 0.2,
        output_size: int = 3
    ):
        super().__init__()
        
        self.input_size = input_size
        self.hidden_size = hidden_size
        
        # Input projection
        self.input_proj = nn.Linear(input_size, hidden_size)
        
        # Positional encoding (learnable)
        self.pos_encoding = nn.Parameter(torch.randn(1, 512, hidden_size) * 0.02)
        
        # Transformer encoder layers
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_size,
            nhead=num_heads,
            dim_feedforward=hidden_size * 4,
            dropout=dropout,
            activation='gelu',
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        # Output head
        self.output_head = nn.Sequential(
            nn.LayerNorm(hidden_size),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, output_size)
        )
        
        # Confidence head
        self.confidence_head = nn.Sequential(
            nn.Linear(hidden_size, 1),
            nn.Sigmoid()
        )
        
        self._init_weights()
    
    def _init_weights(self):
        """Initialize weights."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Forward pass with pure attention."""
        if x.dim() == 2:
            x = x.unsqueeze(1)
        
        batch_size, seq_len, _ = x.shape
        
        # Input projection + positional encoding
        x = self.input_proj(x)
        x = x + self.pos_encoding[:, :seq_len, :]
        
        # Transformer
        x = self.transformer(x)
        
        # Global average pooling over sequence
        x = x.mean(dim=1)
        
        # Output
        logits = self.output_head(x)
        confidence = self.confidence_head(x)
        
        return logits, confidence
    
    def predict(self, x: torch.Tensor) -> Dict:
        """Make prediction."""
        self.eval()
        with torch.no_grad():
            logits, confidence = self(x)
            probs = torch.softmax(logits, dim=-1)
            
            pred_idx = torch.argmax(probs, dim=-1)
            signals = ['SELL', 'HOLD', 'BUY']
            
            return {
                'signal': signals[pred_idx.item()],
                'confidence': confidence.item(),
                'probabilities': {
                    'SELL': probs[0, 0].item(),
                    'HOLD': probs[0, 1].item(),
                    'BUY': probs[0, 2].item()
                }
            }


class LiteBrain(nn.Module):
    """
    Lightweight version of the brain for faster inference.
    Still uses all 40 institutional features but with simpler architecture.
    """
    
    def __init__(
        self,
        input_size: int = 40,
        hidden_size: int = 32,
        output_size: int = 3,
        dropout: float = 0.2
    ):
        super().__init__()
        
        self.network = nn.Sequential(
            nn.Linear(input_size, hidden_size * 2),
            nn.LayerNorm(hidden_size * 2),
            nn.GELU(),
            nn.Dropout(dropout),
            
            nn.Linear(hidden_size * 2, hidden_size),
            nn.LayerNorm(hidden_size),
            nn.GELU(),
            nn.Dropout(dropout),
            
            nn.Linear(hidden_size, output_size)
        )
        
        self.confidence = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.GELU(),
            nn.Linear(hidden_size, 1),
            nn.Sigmoid()
        )
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Forward pass."""
        if x.dim() == 3:
            x = x[:, -1, :]  # Take last timestep
        
        logits = self.network(x)
        conf = self.confidence(x)
        
        return logits, conf
    
    def predict(self, x: torch.Tensor) -> Dict:
        """Make prediction."""
        self.eval()
        with torch.no_grad():
            logits, confidence = self(x)
            probs = torch.softmax(logits, dim=-1)
            
            pred_idx = torch.argmax(probs, dim=-1)
            signals = ['SELL', 'HOLD', 'BUY']
            
            return {
                'signal': signals[pred_idx.item()],
                'confidence': confidence.item(),
                'probabilities': {
                    'SELL': probs[0, 0].item(),
                    'HOLD': probs[0, 1].item(),
                    'BUY': probs[0, 2].item()
                }
            }


# Quick test
if __name__ == "__main__":
    print("Testing Institutional Brain Models...")
    
    # Test full brain
    brain = InstitutionalBrain()
    x = torch.randn(1, 1, 40)  # batch=1, seq=1, features=40
    logits, conf = brain(x)
    print(f"\nFull Brain:")
    print(f"  Input shape: {x.shape}")
    print(f"  Logits shape: {logits.shape}")
    print(f"  Confidence shape: {conf.shape}")
    print(f"  Parameters: {sum(p.numel() for p in brain.parameters()):,}")
    
    # Test prediction
    pred = brain.predict(x)
    print(f"  Prediction: {pred['signal']} ({pred['confidence']:.1%})")
    
    # Test lite brain
    lite = LiteBrain()
    logits, conf = lite(x)
    print(f"\nLite Brain:")
    print(f"  Logits shape: {logits.shape}")
    print(f"  Parameters: {sum(p.numel() for p in lite.parameters()):,}")
    
    pred = lite.predict(x)
    print(f"  Prediction: {pred['signal']} ({pred['confidence']:.1%})")
