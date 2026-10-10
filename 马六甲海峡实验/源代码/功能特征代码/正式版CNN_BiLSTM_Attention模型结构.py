# -*- coding: utf-8 -*-
"""PyTorch model definition for the formal vessel classification plan.

Install PyTorch before using this file:
    pip install torch

Input shape:
    batch_size x sequence_length x feature_count

Recommended AIS sequence features:
    lat, lon, sog, cog, heading, rate_of_turn, time_delta,
    delta_lat, delta_lon, delta_sog, delta_cog
"""

from __future__ import annotations

try:
    import torch
    from torch import nn
except ImportError as exc:  # pragma: no cover
    raise ImportError("This formal deep-learning model requires PyTorch. Install it with: pip install torch") from exc


class AttentionPooling(nn.Module):
    def __init__(self, hidden_dim: int) -> None:
        super().__init__()
        self.score = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.Tanh(),
            nn.Linear(hidden_dim // 2, 1),
        )

    def forward(self, sequence: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        weights = torch.softmax(self.score(sequence), dim=1)
        pooled = torch.sum(sequence * weights, dim=1)
        return pooled, weights.squeeze(-1)


class VesselSequenceClassifier(nn.Module):
    """1D-CNN + BiLSTM + Attention classifier for AIS ship type recognition."""

    def __init__(self, feature_count: int, class_count: int, hidden_dim: int = 64) -> None:
        super().__init__()
        self.cnn = nn.Sequential(
            nn.Conv1d(feature_count, 64, kernel_size=3, padding=1),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Conv1d(64, 64, kernel_size=3, padding=1),
            nn.BatchNorm1d(64),
            nn.ReLU(),
        )
        self.lstm = nn.LSTM(
            input_size=64,
            hidden_size=hidden_dim,
            num_layers=1,
            batch_first=True,
            bidirectional=True,
        )
        self.attention = AttentionPooling(hidden_dim * 2)
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim * 2, 64),
            nn.ReLU(),
            nn.Dropout(0.25),
            nn.Linear(64, class_count),
        )

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        # x: batch x seq_len x features
        conv = self.cnn(x.transpose(1, 2)).transpose(1, 2)
        seq, _ = self.lstm(conv)
        pooled, attention_weights = self.attention(seq)
        logits = self.classifier(pooled)
        return {
            "logits": logits,
            "probabilities": torch.softmax(logits, dim=-1),
            "attention_weights": attention_weights,
        }
