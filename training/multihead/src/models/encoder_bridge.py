"""Local TextEncoder for multihead (vendored; no training/src)."""

from __future__ import annotations

import torch.nn as nn

from models.text_encoder import TextEncoder


def build_encoder(model_name: str, max_length: int = 256):
    return TextEncoder(model_name, max_length)


class EncoderMixin(nn.Module):
    """Shared encoder holder for state multihead model."""

    def __init__(self, model_name: str, max_length: int = 256):
        super().__init__()
        self.encoder = build_encoder(model_name, max_length)

    @property
    def hidden_size(self) -> int:
        return self.encoder.hidden_size

    def encode(self, texts: list[str], device):
        return self.encoder.encode_texts(texts, device)
