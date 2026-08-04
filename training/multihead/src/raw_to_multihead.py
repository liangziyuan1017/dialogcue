"""Map raw fact labels → multihead (head, value) via raw_to_multihead.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from schema_loader import MultiheadSchema, load_schema

MH_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAP = MH_ROOT / "configs" / "raw_to_multihead.yaml"


@dataclass
class HeadResolveResult:
    labels: dict[str, str]
    unmapped_facts: list[str] = field(default_factory=list)
    conflicts_resolved: list[dict[str, Any]] = field(default_factory=list)
    mapped_facts: list[str] = field(default_factory=list)
    fired: list[dict[str, str]] = field(default_factory=list)


class RawToMultiheadMapper:
    def __init__(
        self,
        schema: MultiheadSchema | None = None,
        map_path: Path | None = None,
    ):
        self.schema = schema or load_schema()
        path = map_path or DEFAULT_MAP
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        self.mappings: dict[str, list[dict[str, str]]] = data.get("mappings") or {}
        raw_pri = data.get("resolution_priority") or {}
        self.priority: dict[str, list[str]] = {
            str(h): [str(v) for v in vals] for h, vals in raw_pri.items()
        }
        self._defaults = self._default_labels()
        self._valid = {h.name: set(h.values) for h in self.schema.heads}

    def _default_labels(self) -> dict[str, str]:
        return {h.name: h.values[-1] for h in self.schema.heads}

    def map_raws(self, raws: list[str] | set[str]) -> HeadResolveResult:
        candidates: dict[str, list[str]] = {h.name: [] for h in self.schema.heads}
        unmapped: list[str] = []
        mapped: list[str] = []
        fired: list[dict[str, str]] = []

        for raw in raws:
            rules = self.mappings.get(raw)
            if rules is None:
                unmapped.append(raw)
                continue
            if not rules:
                # explicit drop
                continue
            mapped.append(raw)
            for rule in rules:
                head = str(rule["head"])
                value = str(rule["value"])
                if head not in candidates:
                    continue
                if value not in self._valid.get(head, set()):
                    continue
                candidates[head].append(value)
                fired.append(
                    {
                        "raw": raw,
                        "head": head,
                        "value": value,
                        "via": str(rule.get("via") or ""),
                    }
                )

        labels = dict(self._defaults)
        conflicts: list[dict[str, Any]] = []
        for head, values in candidates.items():
            if not values:
                continue
            uniq = list(dict.fromkeys(values))
            if len(uniq) == 1:
                labels[head] = uniq[0]
                continue
            chosen = self._resolve(head, uniq)
            labels[head] = chosen
            conflicts.append({"head": head, "candidates": uniq, "chosen": chosen})

        return HeadResolveResult(
            labels=labels,
            unmapped_facts=sorted(set(unmapped)),
            conflicts_resolved=conflicts,
            mapped_facts=sorted(set(mapped)),
            fired=fired,
        )

    def _resolve(self, head: str, values: list[str]) -> str:
        for p in self.priority.get(head) or []:
            if p in values:
                return p
        return values[0]


# Back-compat alias used by older call sites
FactToHeadMapper = RawToMultiheadMapper
