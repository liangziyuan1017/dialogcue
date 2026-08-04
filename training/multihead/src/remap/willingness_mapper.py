"""Map raw willingness labels (slot-relocate only; not Softmax training)."""

from __future__ import annotations

from pathlib import Path

import yaml

WILLINGNESS_ORDER = ["resistant", "weak", "conditional", "negotiating", "strong"]


class WillingnessMapper:
    def __init__(self, ontology_path: Path):
        self.levels = set(WILLINGNESS_ORDER)
        self.alias_to_level: dict[str, str] = {}
        self._load(ontology_path)

    def _load(self, path: Path) -> None:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        ontology = data.get("ontology") or {}
        for level, aliases in ontology.items():
            if level not in self.levels:
                continue
            for alias in aliases or []:
                self.alias_to_level[str(alias)] = str(level)

    def map_label(self, raw: str | None) -> str | None:
        if not raw:
            return None
        if raw in self.levels:
            return raw
        return self.alias_to_level.get(raw)
