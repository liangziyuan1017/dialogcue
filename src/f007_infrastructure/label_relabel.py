"""Shared ADR-026 relabel runtime over data/data_labels.

Loads and uses:
  - facts_descriptions.py / emotions_descriptions.py  (canonical TAG_LABELS)
  - facts_relabeled.csv / emotions_relabeled.csv       (cached mappings)
  - llm_relabel_facts.py / llm_relabel_emotions.py     (prompts + classify_batch)

Both F000 (batch labeling) and F008 (online extraction) should call this module
instead of re-implementing the pipeline.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
import threading
from pathlib import Path

from f007_infrastructure.config import get as _cfg
from f007_infrastructure.llm_client import _get_client, call_deepseek_json
from f007_infrastructure.logging import get_logger as _get_logger

_log = _get_logger(__name__)

_DATA_LABELS_DIR = Path(__file__).resolve().parents[2] / "data" / "data_labels"
_relabel_lock = threading.Lock()

_FACT_CSV_MAP: dict[str, str] | None = None
_EMOTION_CSV_MAP: dict[str, str] | None = None
_FACT_DESCRIPTIONS: dict | None = None
_EMOTION_DESCRIPTIONS: dict | None = None
_FACT_RELABEL_MODULE = None
_EMOTION_RELABEL_MODULE = None

_STEM_SUFFIXES = ("ing", "ed", "es", "s", "d")


def _stem(token: str) -> str:
    for suf in _STEM_SUFFIXES:
        if token.endswith(suf) and len(token) - len(suf) >= 3:
            return token[: -len(suf)]
    return token


def _tokens(tag: str) -> frozenset[str]:
    parts = tag.lower().replace("-", "_").split("_")
    return frozenset(_stem(p) for p in parts if len(p) >= 2)


def hard_match(tag: str, candidates) -> str | None:
    cand_list = list(candidates)
    if not cand_list:
        return None
    t = tag.lower().strip()
    for c in cand_list:
        if c.lower() == t:
            return c
    for c in cand_list:
        cl = c.lower()
        if len(cl) >= 4 and (cl in t or t in cl):
            return c
    tt = _tokens(t)
    if not tt:
        return None
    best = None
    best_score = 0
    for c in cand_list:
        ct = _tokens(c)
        if not ct:
            continue
        overlap = len(tt & ct)
        threshold = max(1, (len(ct) + 1) // 2)
        if overlap >= threshold and overlap > best_score:
            best = c
            best_score = overlap
    return best


def _load_py_module(path: Path, name: str):
    if not path.exists():
        return None
    if str(_DATA_LABELS_DIR) not in sys.path:
        sys.path.insert(0, str(_DATA_LABELS_DIR))
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_descriptions() -> tuple[dict, dict]:
    global _FACT_DESCRIPTIONS, _EMOTION_DESCRIPTIONS
    if _FACT_DESCRIPTIONS is None:
        mod = _load_py_module(_DATA_LABELS_DIR / "facts_descriptions.py", "facts_desc")
        _FACT_DESCRIPTIONS = getattr(mod, "TAG_LABELS", {}) if mod else {}
    if _EMOTION_DESCRIPTIONS is None:
        mod = _load_py_module(_DATA_LABELS_DIR / "emotions_descriptions.py", "emotions_desc")
        _EMOTION_DESCRIPTIONS = getattr(mod, "TAG_LABELS", {}) if mod else {}
    return _FACT_DESCRIPTIONS or {}, _EMOTION_DESCRIPTIONS or {}


def load_csv_relabel_maps() -> tuple[dict[str, str], dict[str, str]]:
    global _FACT_CSV_MAP, _EMOTION_CSV_MAP
    if _FACT_CSV_MAP is not None and _EMOTION_CSV_MAP is not None:
        return _FACT_CSV_MAP, _EMOTION_CSV_MAP
    _FACT_CSV_MAP = {}
    _EMOTION_CSV_MAP = {}
    for category, target in (("facts", _FACT_CSV_MAP), ("emotions", _EMOTION_CSV_MAP)):
        path = _DATA_LABELS_DIR / f"{category}_relabeled.csv"
        if not path.exists():
            continue
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                tag = (row.get("tag") or "").strip()
                new = (row.get("new_label") or "").strip()
                if tag and new:
                    target[tag] = new
    return _FACT_CSV_MAP, _EMOTION_CSV_MAP


def load_relabel_module(name: str):
    """Load data/data_labels/llm_relabel_{name}.py."""
    global _FACT_RELABEL_MODULE, _EMOTION_RELABEL_MODULE
    if name == "facts":
        if _FACT_RELABEL_MODULE is None:
            _FACT_RELABEL_MODULE = _load_py_module(
                _DATA_LABELS_DIR / "llm_relabel_facts.py", "llm_relabel_facts"
            )
        return _FACT_RELABEL_MODULE
    if name == "emotions":
        if _EMOTION_RELABEL_MODULE is None:
            _EMOTION_RELABEL_MODULE = _load_py_module(
                _DATA_LABELS_DIR / "llm_relabel_emotions.py", "llm_relabel_emotions"
            )
        return _EMOTION_RELABEL_MODULE
    return None


def append_relabel_to_csv(category: str, mappings: dict[str, str]) -> None:
    if not mappings:
        return
    path = _DATA_LABELS_DIR / f"{category}_relabeled.csv"
    with _relabel_lock:
        file_exists = path.exists()
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["tag", "example", "count", "old_label", "new_label"]
            )
            if not file_exists:
                writer.writeheader()
            for tag, new_label in mappings.items():
                writer.writerow(
                    {
                        "tag": tag,
                        "example": "",
                        "count": 1,
                        "old_label": tag,
                        "new_label": new_label,
                    }
                )


def relabel_via_llm(items: list[str], category: str) -> tuple[list[str], dict[str, str]]:
    """Classify free-form tags via llm_relabel_{facts,emotions}.classify_batch."""
    if not items:
        return [], {}
    mod = load_relabel_module(category)
    if mod is None:
        _log.warning("llm_relabel_%s.py missing; leaving %d tags unmapped", category, len(items))
        return items, {}

    # Row shape expected by llm_relabel_*.format_tags_for_prompt / classify_batch
    batch = [[tag, "", str(i + 1), tag] for i, tag in enumerate(items)]
    try:
        categories_block = mod.build_categories_block()
    except Exception as e:
        _log.error("build_categories_block failed for %s: %s", category, e)
        return items, {}

    mapping: dict = {}
    try:
        if hasattr(mod, "classify_batch"):
            client = _get_client()
            model = _cfg("llm.model", "deepseek-chat")
            mapping = mod.classify_batch(client, model, batch, categories_block) or {}
        else:
            tags_block = "\n".join(f"{i + 1}. `{t}`" for i, t in enumerate(items))
            system = mod.SYSTEM_PROMPT.format(categories=categories_block)
            user = mod.USER_PROMPT_TEMPLATE.format(count=len(items), tags=tags_block)
            mapping = call_deepseek_json(f"{system}\n\n{user}", temperature=0.0) or {}
    except Exception as e:
        _log.error("llm_relabel_%s classify failed for %d tags: %s", category, len(items), e)
        return items, {}

    if not isinstance(mapping, dict):
        _log.warning("llm_relabel_%s returned %s, expected dict", category, type(mapping).__name__)
        return items, {}

    if hasattr(mod, "validate_mapping"):
        issues = mod.validate_mapping(mapping, batch)
        if issues:
            _log.warning("llm_relabel_%s validation: %s", category, "; ".join(issues))

    valid_keys = set(getattr(mod, "TAG_LABELS", {}).keys())
    result: list[str] = []
    seen: set[str] = set()
    new_mappings: dict[str, str] = {}
    for item in items:
        new = mapping.get(item, item)
        if new not in valid_keys:
            _log.warning(
                "llm_relabel_%s mapped %r -> %r (not canonical); dropping",
                category,
                item,
                new,
            )
            continue
        new_mappings[item] = new
        if new not in seen:
            result.append(new)
            seen.add(new)
    return result, new_mappings


def relabel_label_list(items: list[str], category: str) -> list[str]:
    """Map free-form labels → canonical set (descriptions → CSV → llm_relabel_*)."""
    if not items:
        return []
    fact_desc, emotion_desc = load_descriptions()
    fact_map, emotion_map = load_csv_relabel_maps()

    if category == "facts":
        canonical = set(fact_desc.keys())
        csv_map = fact_map
    else:
        canonical = set(emotion_desc.keys())
        csv_map = emotion_map

    kept: list[str] = []
    unknown: list[str] = []
    seen: set[str] = set()

    for item in items:
        if not item:
            continue
        canonical_hit = hard_match(item, canonical)
        if canonical_hit is not None:
            resolved: str | None = canonical_hit
        else:
            csv_hit = hard_match(item, csv_map.keys())
            resolved = csv_map[csv_hit] if csv_hit is not None else None
            if resolved is not None:
                # Prefer canonical spelling when CSV target hard-matches descriptions
                canon_resolved = hard_match(resolved, canonical)
                if canon_resolved is not None:
                    resolved = canon_resolved
                # else keep CSV new_label as-is (cached mapping is authoritative)
        if resolved is not None:
            if resolved not in seen:
                kept.append(resolved)
                seen.add(resolved)
        elif item not in unknown:
            unknown.append(item)

    if unknown:
        llm_relabeled, new_mappings = relabel_via_llm(unknown, category)
        # relabel_via_llm already validated against llm_relabel_*.TAG_LABELS
        for item in llm_relabeled:
            if item not in seen:
                kept.append(item)
                seen.add(item)
        if new_mappings:
            append_relabel_to_csv(category, new_mappings)
            with _relabel_lock:
                csv_map.update(new_mappings)

    return kept


def apply_relabel(result: dict) -> None:
    """In-place relabel of a state dict with optional facts/emotions lists (F008)."""
    for key in ("facts", "emotions"):
        items = result.get(key, [])
        if not items:
            continue
        result[key] = relabel_label_list(list(items), key)
