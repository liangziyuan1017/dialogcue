"""Map raw emotion labels (slot-relocate only; not a Softmax training target)."""

from __future__ import annotations

from pathlib import Path

import yaml


class EmotionMapper:
    """Self-contained: vocab = trainable names from mapping file (no tag_labels)."""

    def __init__(self, mapping_path: Path, emotion_vocab: list[str] | None = None):
        self.raw_to_trainable: dict[str, str] = {}
        self.drop_labels: set[str] = set()
        self._load(mapping_path)
        self.emotion_vocab = set(emotion_vocab or [])
        self.emotion_vocab |= set(self.raw_to_trainable.values())
        self.emotion_vocab |= {
            r for r, t in self.raw_to_trainable.items() if r == t
        }

    def _load(self, path: Path) -> None:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        mappings = data.get("mappings") or {}
        for _key, meta in mappings.items():
            raw = meta.get("raw_label")
            if not raw:
                continue
            trainable = meta.get("trainable_emotion")
            if meta.get("drop") is True or trainable is None:
                self.drop_labels.add(str(raw))
                continue
            self.raw_to_trainable[str(raw)] = str(trainable)

    def is_dropped(self, raw: str) -> bool:
        return raw in self.drop_labels

    def map_label(self, raw: str) -> str | None:
        if raw in self.emotion_vocab:
            return raw
        if self.is_dropped(raw):
            return None
        return self.raw_to_trainable.get(raw)
