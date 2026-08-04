"""Load multihead schema v3.1 for P0/P1/P2 training."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

MULTIHEAD_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = MULTIHEAD_ROOT / "configs" / "schema_v3.1.yaml"


@dataclass(frozen=True)
class HeadSpec:
    name: str
    kind: str  # state | event
    type: str  # binary | softmax
    values: tuple[str, ...]
    exclusive: bool = False
    map: dict[str, str] = field(default_factory=dict)
    note: str = ""

    @property
    def n_classes(self) -> int:
        return len(self.values)

    def value_to_index(self) -> dict[str, int]:
        return {v: i for i, v in enumerate(self.values)}


@dataclass(frozen=True)
class MultiheadSchema:
    version: str
    evidence_rule: str
    heads: tuple[HeadSpec, ...]
    rule_signals: dict[str, str]
    memory_fields: dict[str, str]
    p0_exclude_heads: tuple[str, ...]
    default_head_mask: dict[str, int] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def head_names(self) -> list[str]:
        return [h.name for h in self.heads]

    @property
    def n_heads(self) -> int:
        return len(self.heads)

    def head_by_name(self) -> dict[str, HeadSpec]:
        return {h.name: h for h in self.heads}

    def p0_supervised_head_names(self) -> list[str]:
        excl = set(self.p0_exclude_heads)
        return [h.name for h in self.heads if h.name not in excl]

    def state_head_names(self) -> list[str]:
        return [h.name for h in self.heads if h.kind == "state"]

    def head_mask_for_sample(self) -> dict[str, int]:
        """Default mask: 1 for all heads except those in default_head_mask."""
        out = {h.name: 1 for h in self.heads}
        out.update(self.default_head_mask)
        return out

    def positive_train_labels(self) -> list[tuple[str, str, str]]:
        out: list[tuple[str, str, str]] = []
        for h in self.heads:
            for v, kid in (h.map or {}).items():
                out.append((h.name, v, kid))
        return out


def _as_str_list(values: Any) -> tuple[str, ...]:
    if not isinstance(values, list):
        return tuple()
    return tuple(str(v) for v in values)


@lru_cache(maxsize=4)
def load_schema(path: str | None = None) -> MultiheadSchema:
    p = Path(path) if path else DEFAULT_SCHEMA
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    heads: list[HeadSpec] = []
    for name, meta in (data.get("heads") or {}).items():
        if not isinstance(meta, dict):
            continue
        heads.append(
            HeadSpec(
                name=str(name),
                kind=str(meta.get("kind") or "state"),
                type=str(meta.get("type") or "binary"),
                values=_as_str_list(meta.get("values")),
                exclusive=bool(meta.get("exclusive")),
                map={str(k): str(v) for k, v in (meta.get("map") or {}).items()},
                note=str(meta.get("note") or ""),
            )
        )
    p0 = data.get("p0_policy") or {}
    train_pol = data.get("train_policy") or {}
    exclude = p0.get("p0_exclude_heads") or ["IdentityProcess"]
    exclude_heads = [str(x) for x in exclude if str(x) != "event"]
    if not exclude_heads:
        exclude_heads = ["IdentityProcess"]
    default_mask = {
        str(k): int(v) for k, v in (train_pol.get("default_head_mask") or {}).items()
    }
    return MultiheadSchema(
        version=str(data.get("version") or ""),
        evidence_rule=str(data.get("evidence_rule") or "").strip(),
        heads=tuple(heads),
        rule_signals={str(k): str(v) for k, v in (data.get("rule_signals") or {}).items()},
        memory_fields={str(k): str(v) for k, v in (data.get("memory_fields") or {}).items()},
        p0_exclude_heads=tuple(exclude_heads),
        default_head_mask=default_mask,
        raw=data,
    )
