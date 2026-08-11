"""Frozen Emotion 11 / Willingness 5 loaders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from paths import CONFIGS, load_yaml, resolve_under_mt

EMOTION_DEFAULT = CONFIGS / "labels_emotion.yaml"
WILLINGNESS_DEFAULT = CONFIGS / "labels_willingness.yaml"
ADJACENT_DEFAULT = CONFIGS / "emotion_adjacent.yaml"


def load_label_list(path: Path | None = None, *, kind: str) -> list[str]:
    if path is None:
        path = EMOTION_DEFAULT if kind == "emotion" else WILLINGNESS_DEFAULT
    data = load_yaml(resolve_under_mt(path) if not Path(path).is_absolute() else Path(path))
    labels = [str(x) for x in (data.get("labels") or [])]
    if not labels:
        raise ValueError(f"empty labels in {path}")
    return labels


def emotion_labels(path: Path | None = None) -> list[str]:
    return load_label_list(path, kind="emotion")


def willingness_labels(path: Path | None = None) -> list[str]:
    return load_label_list(path, kind="willingness")


def label_to_index(labels: list[str]) -> dict[str, int]:
    return {lab: i for i, lab in enumerate(labels)}


def load_adjacent_config(path: Path | None = None) -> dict[str, Any]:
    p = path or ADJACENT_DEFAULT
    p = resolve_under_mt(p) if not Path(p).is_absolute() else Path(p)
    return load_yaml(p)


def adjacent_pair_set(
    cfg: dict[str, Any] | None = None,
    *,
    eval_set: str = "all_rule",
) -> frozenset[frozenset[str]]:
    cfg = cfg or load_adjacent_config()
    if eval_set == "data_validated":
        pairs = cfg.get("data_validated") or []
    elif eval_set == "rule_only":
        pairs = cfg.get("rule_only") or []
    else:
        pairs = list(cfg.get("data_validated") or []) + list(cfg.get("rule_only") or [])
    out: set[frozenset[str]] = set()
    for pair in pairs:
        if not pair or len(pair) != 2:
            continue
        out.add(frozenset({str(pair[0]), str(pair[1])}))
    return frozenset(out)


def clusters_from_cfg(cfg: dict[str, Any] | None = None) -> dict[str, frozenset[str]]:
    cfg = cfg or load_adjacent_config()
    raw = cfg.get("clusters") or {}
    return {str(k): frozenset(str(x) for x in (v or [])) for k, v in raw.items()}
