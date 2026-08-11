"""Shared-encoder multitask model: Fact 19-head + Emotion + Willingness."""

from __future__ import annotations

from typing import Any

import torch
import torch.nn as nn

from encoder import TextEncoder
from labels import emotion_labels, willingness_labels
from paths import load_fact_schema


class MultitaskV1Model(nn.Module):
    """
    Fact: per-head Linear over schema.values (masked multi-head CE at train).
    Emotion / Willingness: single Linear each.
    """

    def __init__(
        self,
        model_name: str = "__mock__",
        *,
        fact_schema=None,
        emotion_vocab: list[str] | None = None,
        willingness_vocab: list[str] | None = None,
        max_length: int = 256,
    ):
        super().__init__()
        self.encoder = TextEncoder(model_name, max_length=max_length)
        self.fact_schema = fact_schema or load_fact_schema()
        self.emotion_vocab = list(emotion_vocab or emotion_labels())
        self.willingness_vocab = list(willingness_vocab or willingness_labels())
        h = self.encoder.hidden_size
        self.fact_heads = nn.ModuleDict(
            {head.name: nn.Linear(h, head.n_classes) for head in self.fact_schema.heads}
        )
        self.emotion_head = nn.Linear(h, len(self.emotion_vocab))
        self.willingness_head = nn.Linear(h, len(self.willingness_vocab))

    @property
    def hidden_size(self) -> int:
        return self.encoder.hidden_size

    def forward(self, texts: list[str], device: torch.device) -> dict[str, Any]:
        pooled = self.encoder.encode_texts(texts, device)
        fact_logits = {name: layer(pooled) for name, layer in self.fact_heads.items()}
        return {
            "pooled": pooled,
            "fact_logits": fact_logits,
            "emotion_logits": self.emotion_head(pooled),
            "willingness_logits": self.willingness_head(pooled),
        }
