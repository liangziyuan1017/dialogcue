"""State-only dataset from build_state_dataset JSONL."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import torch
from torch.utils.data import Dataset

import sys

_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from schema_loader import MultiheadSchema, load_schema

UNKNOWN = "unknown"


@dataclass
class StateSample:
    conversation_id: str
    turn_id: int
    text: str
    labels: dict[str, str]
    head_mask: dict[str, int]
    meta: dict[str, Any] = field(default_factory=dict)
    split: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "StateSample":
        inp = d.get("input") or {}
        text = str(inp.get("context_window") or d.get("text") or "")
        return cls(
            conversation_id=str(d.get("conversation_id") or ""),
            turn_id=int(d.get("turn_id") or 0),
            text=text,
            labels={str(k): str(v) for k, v in (d.get("labels") or {}).items()},
            head_mask={str(k): int(v) for k, v in (d.get("head_mask") or {}).items()},
            meta=dict(d.get("meta") or {}),
            split=str(d.get("split") or ""),
        )


def load_state_jsonl(path: Path) -> list[StateSample]:
    rows: list[StateSample] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(StateSample.from_dict(json.loads(line)))
    return rows


def iter_mock_state_samples(schema: MultiheadSchema, n: int = 4) -> Iterator[StateSample]:
    defaults = {h.name: h.values[-1] for h in schema.heads}
    mask = schema.head_mask_for_sample()
    for i in range(n):
        labels = dict(defaults)
        # flip a couple heads for smoke
        if schema.heads:
            h0 = schema.heads[0]
            if len(h0.values) >= 2:
                labels[h0.name] = h0.values[0]
        yield StateSample(
            conversation_id=f"mock_{i}",
            turn_id=i,
            text=f"[customer] mock utterance {i} 失业了没收入。",
            labels=labels,
            head_mask=dict(mask),
            meta={"mock": True},
            split="train",
        )


class StateDataset(Dataset):
    def __init__(self, samples: list[StateSample], schema: MultiheadSchema | None = None):
        self.samples = samples
        self.schema = schema or load_schema()
        self._value_index = {h.name: h.value_to_index() for h in self.schema.heads}
        self._defaults = {h.name: h.values[-1] for h in self.schema.heads}

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        s = self.samples[idx]
        target_idx: dict[str, int] = {}
        mask: dict[str, float] = {}
        for h in self.schema.heads:
            lab = s.labels.get(h.name, self._defaults[h.name])
            v2i = self._value_index[h.name]
            if lab == UNKNOWN or lab not in v2i:
                # unknown / invalid → placeholder index; must be masked out of loss
                target_idx[h.name] = int(v2i[self._defaults[h.name]])
                mask[h.name] = 0.0
            else:
                target_idx[h.name] = int(v2i[lab])
                mask[h.name] = float(s.head_mask.get(h.name, 1))
            # IdentityProcess always masked in train even if label present
            if h.name == "IdentityProcess":
                mask[h.name] = 0.0
        return {
            "text": s.text,
            "target_idx": target_idx,
            "head_mask": mask,
            "labels": dict(s.labels),
            "conversation_id": s.conversation_id,
            "turn_id": s.turn_id,
        }


def collate_state(batch: list[dict[str, Any]]) -> dict[str, Any]:
    texts = [b["text"] for b in batch]
    head_names = list(batch[0]["target_idx"].keys())
    target_idx = {
        h: torch.tensor([b["target_idx"][h] for b in batch], dtype=torch.long)
        for h in head_names
    }
    head_mask = {
        h: torch.tensor([b["head_mask"][h] for b in batch], dtype=torch.float32)
        for h in head_names
    }
    return {
        "texts": texts,
        "target_idx": target_idx,
        "head_mask": head_mask,
        "labels": [b["labels"] for b in batch],
        "conversation_id": [b["conversation_id"] for b in batch],
        "turn_id": [b["turn_id"] for b in batch],
    }


def compute_class_counts(
    samples: list[StateSample],
    schema: MultiheadSchema,
) -> dict[str, list[int]]:
    """Per-head class counts aligned to schema.values (supervised rows only)."""
    counts = {h.name: [0] * h.n_classes for h in schema.heads}
    defaults = {h.name: h.values[-1] for h in schema.heads}
    v2i = {h.name: h.value_to_index() for h in schema.heads}
    for s in samples:
        for h in schema.heads:
            if int(s.head_mask.get(h.name, 0)) == 0:
                continue
            lab = s.labels.get(h.name, defaults[h.name])
            if lab == UNKNOWN or lab not in v2i[h.name]:
                continue
            counts[h.name][v2i[h.name][lab]] += 1
    return counts
