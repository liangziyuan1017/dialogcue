"""Shared text encoder backbone."""

from __future__ import annotations

import hashlib

import torch
import torch.nn as nn


class MockTextEncoder(nn.Module):
    """Lightweight encoder for offline smoke tests (no HF download)."""

    def __init__(self, hidden_size: int = 128, max_length: int = 256):
        super().__init__()
        self.hidden_size = hidden_size
        self.max_length = max_length
        self.proj = nn.Sequential(
            nn.Linear(32, hidden_size),
            nn.Tanh(),
        )

    def encode_texts(self, texts: list[str], device: torch.device) -> torch.Tensor:
        feats = []
        for text in texts:
            h = hashlib.sha256(text.encode("utf-8")).digest()
            vec = torch.tensor([b / 255.0 for b in h], dtype=torch.float32, device=device)
            feats.append(vec)
        stacked = torch.stack(feats)
        return self.proj(stacked)


class TextEncoder(nn.Module):
    def __init__(self, model_name: str, max_length: int = 256):
        super().__init__()
        self.model_name = model_name
        self.max_length = max_length
        if model_name == "__mock__":
            self.mock = MockTextEncoder(hidden_size=128, max_length=max_length)
            self.hidden_size = self.mock.hidden_size
            self.tokenizer = None
            self.encoder = None
        else:
            from transformers import AutoModel, AutoTokenizer

            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.encoder = AutoModel.from_pretrained(model_name)
            self.hidden_size = self.encoder.config.hidden_size
            self.mock = None

    def encode_texts(self, texts: list[str], device: torch.device) -> torch.Tensor:
        if self.mock is not None:
            return self.mock.encode_texts(texts, device)
        encoded = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        encoded = {k: v.to(device) for k, v in encoded.items()}
        outputs = self.encoder(**encoded)
        return outputs.last_hidden_state[:, 0, :]

    def encoder_state_dict(self) -> dict:
        if self.mock is not None:
            return self.mock.state_dict()
        return self.encoder.state_dict()

    def load_encoder_state_dict(self, state: dict) -> None:
        if self.mock is not None:
            self.mock.load_state_dict(state)
        else:
            self.encoder.load_state_dict(state)
