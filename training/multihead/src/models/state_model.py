"""18-head current-state model (no P0/P1)."""

from __future__ import annotations

import sys
from pathlib import Path

import torch
import torch.nn as nn

_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from models.encoder_bridge import EncoderMixin
from schema_loader import MultiheadSchema, load_schema


class StateMultiheadModel(EncoderMixin):
    """context_window → per-head value logits."""

    def __init__(
        self,
        model_name: str,
        schema: MultiheadSchema | None = None,
        max_length: int = 256,
    ):
        super().__init__(model_name, max_length)
        self.schema = schema or load_schema()
        h = self.hidden_size
        self.heads = nn.ModuleDict(
            {head.name: nn.Linear(h, head.n_classes) for head in self.schema.heads}
        )

    @classmethod
    def from_config(cls, config: dict) -> "StateMultiheadModel":
        schema_path = config.get("schema_path")
        schema = load_schema(str(schema_path) if schema_path else None)
        return cls(
            config.get("model_name", "__mock__"),
            schema=schema,
            max_length=int(config.get("max_length", 256)),
        )

    def forward(self, texts: list[str], device: torch.device) -> dict[str, torch.Tensor | dict]:
        pooled = self.encode(texts, device)
        return {
            "pooled": pooled,
            "logits": {name: layer(pooled) for name, layer in self.heads.items()},
        }

    def load_encoder_from_checkpoint(self, ckpt: dict) -> None:
        """Load encoder weights from Stage1/Stage2/E1-A style checkpoints."""
        state = ckpt.get("model_state_dict") or ckpt.get("model") or ckpt
        if not isinstance(state, dict):
            raise ValueError("checkpoint missing model_state_dict")
        # Prefer nested encoder.* keys
        enc_sd = {}
        for k, v in state.items():
            if k.startswith("encoder.encoder."):
                enc_sd[k[len("encoder.encoder.") :]] = v
            elif k.startswith("encoder.") and not k.startswith("encoder.mock"):
                # TextEncoder wraps HF as self.encoder
                rest = k[len("encoder.") :]
                if rest.startswith("encoder."):
                    enc_sd[rest[len("encoder.") :]] = v
        if enc_sd and self.encoder.encoder is not None:
            self.encoder.encoder.load_state_dict(enc_sd, strict=False)
            return
        # Fallback: TextEncoder.encoder_state_dict format
        if "encoder_state_dict" in ckpt:
            self.encoder.load_encoder_state_dict(ckpt["encoder_state_dict"])
            return
        # Try loading via a temporary Stage1-like prefix strip
        stripped = {
            k.replace("encoder.", "", 1): v
            for k, v in state.items()
            if k.startswith("encoder.") and "head" not in k.split(".")[0:2]
        }
        if stripped and self.encoder.mock is None:
            # keys like encoder.embeddings... under HF model
            try:
                self.encoder.encoder.load_state_dict(stripped, strict=False)
            except Exception:
                self.encoder.load_encoder_state_dict(
                    {k: v for k, v in state.items() if not k.startswith("head")}
                )
