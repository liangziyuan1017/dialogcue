"""Multitask dataset + mock samples for smoke."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import torch
from torch.utils.data import Dataset

from labels import emotion_labels, label_to_index, willingness_labels
from paths import load_fact_schema

UNKNOWN = "unknown"


@dataclass
class MultitaskSample:
    conversation_id: str
    turn_id: int
    text: str
    fact_labels: dict[str, str]
    fact_mask: dict[str, int]
    emotion: str | None
    willingness: str | None
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MultitaskSample":
        inp = d.get("input") or {}
        text = str(inp.get("context_window") or d.get("text") or "")
        fact = d.get("fact_labels") or d.get("labels") or {}
        mask = d.get("fact_mask") or d.get("head_mask") or {}
        emo = d.get("emotion")
        will = d.get("willingness")
        if emo is None and isinstance(d.get("tasks"), dict):
            emo = (d["tasks"] or {}).get("emotion")
            will = (d["tasks"] or {}).get("willingness")
        return cls(
            conversation_id=str(d.get("conversation_id") or ""),
            turn_id=int(d.get("turn_id") or 0),
            text=text,
            fact_labels={str(k): str(v) for k, v in fact.items()},
            fact_mask={str(k): int(v) for k, v in mask.items()},
            emotion=None if emo in (None, "", UNKNOWN) else str(emo),
            willingness=None if will in (None, "", UNKNOWN) else str(will),
            meta=dict(d.get("meta") or {}),
        )


def load_jsonl(path: Path) -> list[MultitaskSample]:
    rows: list[MultitaskSample] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(MultitaskSample.from_dict(json.loads(line)))
    return rows


def iter_mock_samples(
    fact_schema,
    *,
    emotion_vocab: list[str],
    willingness_vocab: list[str],
    n: int = 8,
) -> Iterator[MultitaskSample]:
    defaults = {h.name: h.values[-1] for h in fact_schema.heads}
    mask = fact_schema.head_mask_for_sample()
    for i in range(n):
        labels = dict(defaults)
        if fact_schema.heads:
            h0 = fact_schema.heads[0]
            if len(h0.values) >= 2:
                labels[h0.name] = h0.values[i % len(h0.values)]
        yield MultitaskSample(
            conversation_id=f"mock_{i}",
            turn_id=i,
            text=f"[customer] mock utterance {i} 我失业了暂时还不上。",
            fact_labels=labels,
            fact_mask=dict(mask),
            emotion=emotion_vocab[i % len(emotion_vocab)],
            willingness=willingness_vocab[i % len(willingness_vocab)],
            meta={"mock": True},
        )


class MultitaskDataset(Dataset):
    def __init__(
        self,
        samples: list[MultitaskSample],
        *,
        fact_schema=None,
        emotion_vocab: list[str] | None = None,
        willingness_vocab: list[str] | None = None,
    ):
        self.samples = samples
        self.fact_schema = fact_schema or load_fact_schema()
        self.emotion_vocab = list(emotion_vocab or emotion_labels())
        self.willingness_vocab = list(willingness_vocab or willingness_labels())
        self._fact_v2i = {h.name: h.value_to_index() for h in self.fact_schema.heads}
        self._fact_defaults = {h.name: h.values[-1] for h in self.fact_schema.heads}
        self._emo_v2i = label_to_index(self.emotion_vocab)
        self._will_v2i = label_to_index(self.willingness_vocab)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        s = self.samples[idx]
        fact_target: dict[str, int] = {}
        fact_mask: dict[str, float] = {}
        for h in self.fact_schema.heads:
            lab = s.fact_labels.get(h.name, self._fact_defaults[h.name])
            v2i = self._fact_v2i[h.name]
            if lab == UNKNOWN or lab not in v2i:
                fact_target[h.name] = int(v2i[self._fact_defaults[h.name]])
                fact_mask[h.name] = 0.0
            else:
                fact_target[h.name] = int(v2i[lab])
                fact_mask[h.name] = float(s.fact_mask.get(h.name, 1))
            if h.name == "IdentityProcess":
                fact_mask[h.name] = 0.0

        if s.emotion is None or s.emotion not in self._emo_v2i:
            emo_t, emo_m = 0, 0.0
        else:
            emo_t, emo_m = self._emo_v2i[s.emotion], 1.0

        if s.willingness is None or s.willingness not in self._will_v2i:
            will_t, will_m = 0, 0.0
        else:
            will_t, will_m = self._will_v2i[s.willingness], 1.0

        return {
            "text": s.text,
            "fact_target": fact_target,
            "fact_mask": fact_mask,
            "fact_labels": dict(s.fact_labels),
            "emotion_target": emo_t,
            "emotion_mask": emo_m,
            "emotion_label": s.emotion,
            "willingness_target": will_t,
            "willingness_mask": will_m,
            "willingness_label": s.willingness,
            # Explicit task-level masks (emotion/will never train as fake class 0)
            "task_mask": {
                "fact": 1.0 if any(v > 0 for v in fact_mask.values()) else 0.0,
                "emotion": float(emo_m),
                "willingness": float(will_m),
            },
            "conversation_id": s.conversation_id,
            "turn_id": s.turn_id,
        }


def collate_multitask(batch: list[dict[str, Any]]) -> dict[str, Any]:
    head_names = list(batch[0]["fact_target"].keys())
    return {
        "texts": [b["text"] for b in batch],
        "fact_target": {
            h: torch.tensor([b["fact_target"][h] for b in batch], dtype=torch.long)
            for h in head_names
        },
        "fact_mask": {
            h: torch.tensor([b["fact_mask"][h] for b in batch], dtype=torch.float32)
            for h in head_names
        },
        "fact_labels": [b["fact_labels"] for b in batch],
        "emotion_target": torch.tensor(
            [b["emotion_target"] for b in batch], dtype=torch.long
        ),
        "emotion_mask": torch.tensor(
            [b["emotion_mask"] for b in batch], dtype=torch.float32
        ),
        "emotion_label": [b["emotion_label"] for b in batch],
        "willingness_target": torch.tensor(
            [b["willingness_target"] for b in batch], dtype=torch.long
        ),
        "willingness_mask": torch.tensor(
            [b["willingness_mask"] for b in batch], dtype=torch.float32
        ),
        "willingness_label": [b["willingness_label"] for b in batch],
        "task_mask": {
            "fact": torch.tensor(
                [b["task_mask"]["fact"] for b in batch], dtype=torch.float32
            ),
            "emotion": torch.tensor(
                [b["task_mask"]["emotion"] for b in batch], dtype=torch.float32
            ),
            "willingness": torch.tensor(
                [b["task_mask"]["willingness"] for b in batch], dtype=torch.float32
            ),
        },
        "conversation_id": [b["conversation_id"] for b in batch],
        "turn_id": [b["turn_id"] for b in batch],
    }


def compute_fact_class_counts(
    samples: list[MultitaskSample],
    schema,
) -> dict[str, list[int]]:
    """Per-head class counts (supervised mask=1 rows only)."""
    counts = {h.name: [0] * h.n_classes for h in schema.heads}
    defaults = {h.name: h.values[-1] for h in schema.heads}
    v2i = {h.name: h.value_to_index() for h in schema.heads}
    for s in samples:
        for h in schema.heads:
            if int(s.fact_mask.get(h.name, 0)) == 0:
                continue
            lab = s.fact_labels.get(h.name, defaults[h.name])
            if lab == UNKNOWN or lab not in v2i[h.name]:
                continue
            counts[h.name][v2i[h.name][lab]] += 1
    return counts


def compute_label_counts(
    samples: list[MultitaskSample],
    vocab: list[str],
    *,
    kind: str,
) -> list[int]:
    """Emotion or willingness supervised class counts."""
    idx = {lab: i for i, lab in enumerate(vocab)}
    counts = [0] * len(vocab)
    for s in samples:
        lab = s.emotion if kind == "emotion" else s.willingness
        if lab is None or lab not in idx:
            continue
        counts[idx[lab]] += 1
    return counts
