# -*- coding: utf-8 -*-
"""Formal PyTorch structure for AIS risk level prediction.

This model is intentionally different from the vessel type classifier:

- Vessel classifier: sequence model, answers "what type of ship is it?"
- Risk model: tabular risk-feature model, answers "how dangerous is it now?"

Install PyTorch before using:
    pip install torch
"""

from __future__ import annotations

try:
    import torch
    from torch import nn
except ImportError as exc:  # pragma: no cover
    raise ImportError("This formal risk model requires PyTorch. Install it with: pip install torch") from exc


class ResidualBlock(nn.Module):
    def __init__(self, dim: int, dropout: float = 0.2) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(dim, dim),
            nn.BatchNorm1d(dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(dim, dim),
            nn.BatchNorm1d(dim),
        )
        self.act = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.act(x + self.net(x))


class RiskLevelMLP(nn.Module):
    """Residual MLP for low/medium/elevated/high risk prediction."""

    def __init__(self, feature_count: int, class_count: int = 4, hidden_dim: int = 64) -> None:
        super().__init__()
        self.input_layer = nn.Sequential(
            nn.Linear(feature_count, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ReLU(),
        )
        self.blocks = nn.Sequential(
            ResidualBlock(hidden_dim),
            ResidualBlock(hidden_dim),
        )
        self.output_layer = nn.Linear(hidden_dim, class_count)

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        hidden = self.blocks(self.input_layer(x))
        logits = self.output_layer(hidden)
        return {
            "logits": logits,
            "probabilities": torch.softmax(logits, dim=-1),
        }
