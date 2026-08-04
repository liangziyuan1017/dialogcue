#!/usr/bin/env python3
"""Export raw → multihead (head, value) from training_ontology_v3.

Primary source: each train label's include_raw (+ absorbed knowledge include_raw).
Schema v3.1 addition: Contactability.denied from Contact/contact_denied_or_withholding.
Optional overrides: fix known include_raw pollution / Stage2 alias gaps.
Optional legacy bridge: expand via old Stage2 mapping when trainable name hits include_raw.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[3]
MH = REPO / "training" / "multihead"
DEFAULT_ONT = REPO / "label_handler" / "ontology_v2" / "training_ontology_v3.yaml"
DEFAULT_PROPOSED = REPO / "label_handler" / "ontology_v2" / "proposed_ontology.yaml"
DEFAULT_OVERRIDES = MH / "configs" / "raw_to_multihead_overrides.yaml"
DEFAULT_LEGACY = REPO / "label_handler" / "fact" / "raw_to_trainable_mapping.yaml"
DEFAULT_OUT = MH / "configs" / "raw_to_multihead.yaml"
DEFAULT_SCHEMA = MH / "configs" / "schema_v3.1.yaml"

# Same-head multi-value priority (first wins)
DEFAULT_PRIORITY = {
    "Employment": ["disrupted"],
    "Income": ["unavailable"],
    "Asset": ["unavailable", "available"],
    "Contactability": ["denied", "unreachable", "reachable"],
    "RepaymentCapability": ["insufficient", "partial"],
    "Commitment": ["resistant", "committed"],
    "LegalProceeding": ["yes"],
    "ComplianceRisk": ["yes"],
    "FinancialHardship": ["yes"],
    "Health": ["yes"],
    "FamilyBurden": ["yes"],
    "Responsibility": ["denying"],
    "DebtDispute": ["yes"],
    "BankConstraint": ["yes"],
    "ObjectiveBlocker": ["yes"],
    "CognitiveSupport": ["yes"],
    "NegotiationRequest": ["yes"],
    "Grievance": ["yes"],
}


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _knowledge_include_raw(proposed: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for domain, facts in (proposed.get("domains") or {}).items():
        for fid, meta in (facts or {}).items():
            if isinstance(meta, dict):
                out[f"{domain}/{fid}"] = [str(x) for x in (meta.get("include_raw") or [])]
    return out


def _add(
    inv: dict[str, list[dict[str, str]]],
    raw: str,
    *,
    head: str,
    value: str,
    train_label: str,
    via: str,
) -> None:
    raw = str(raw).strip()
    if not raw:
        return
    entry = {
        "head": head,
        "value": str(value),
        "train_label": train_label,
        "via": via,
    }
    bucket = inv.setdefault(raw, [])
    key = (entry["head"], entry["value"], entry["train_label"])
    if any((e["head"], e["value"], e["train_label"]) == key for e in bucket):
        return
    bucket.append(entry)


def build_inventory(
    ont: dict,
    proposed: dict,
    *,
    overrides: dict | None = None,
    legacy_path: Path | None = None,
    compose_legacy: bool = True,
) -> tuple[dict[str, list[dict[str, str]]], dict[str, Any]]:
    kid_raws = _knowledge_include_raw(proposed)
    inv: dict[str, list[dict[str, str]]] = {}
    stats: dict[str, Any] = {
        "n_train_labels": 0,
        "n_include_raw_edges": 0,
        "n_absorbed_edges": 0,
        "n_denied_edges": 0,
        "n_override_raws": 0,
        "n_legacy_bridge_raws": 0,
    }

    for train_label, meta in (ont.get("labels") or {}).items():
        if not isinstance(meta, dict):
            continue
        head = str(meta.get("train_head") or "")
        value = str(meta.get("train_value") or "")
        if not head or not value:
            continue
        # train:false (e.g. IdentityProcess) still exported for eval/memory labeling,
        # but excluded from n_train_labels Softmax inventory count.
        is_train = meta.get("train") is not False
        if is_train:
            stats["n_train_labels"] += 1
        else:
            stats["n_eval_only_labels"] = int(stats.get("n_eval_only_labels") or 0) + 1
        for raw in meta.get("include_raw") or []:
            _add(
                inv,
                raw,
                head=head,
                value=value,
                train_label=str(train_label),
                via="include_raw" if is_train else "include_raw_eval_only",
            )
            stats["n_include_raw_edges"] += 1
        for abs_ in (meta.get("frequency") or {}).get("absorbed_from") or []:
            src = abs_.get("from") if isinstance(abs_, dict) else None
            if not src:
                continue
            for raw in kid_raws.get(str(src)) or []:
                _add(
                    inv,
                    raw,
                    head=head,
                    value=value,
                    train_label=str(train_label),
                    via=f"absorbed:{src}" if is_train else f"absorbed_eval_only:{src}",
                )
                stats["n_absorbed_edges"] += 1

    # schema v3.1: denied is a Contactability value (Rule in v3 merge map)
    for raw in kid_raws.get("Contact/contact_denied_or_withholding") or []:
        _add(
            inv,
            raw,
            head="Contactability",
            value="denied",
            train_label="Contactability.denied",
            via="schema_v3.1_denied",
        )
        stats["n_denied_edges"] += 1

    # overrides: replace all targets for listed raws
    ov = (overrides or {}).get("overrides") or {}
    for raw, rules in ov.items():
        inv[str(raw)] = []
        for rule in rules or []:
            _add(
                inv,
                str(raw),
                head=str(rule["head"]),
                value=str(rule["value"]),
                train_label=str(rule.get("train_label") or f"{rule['head']}.{rule['value']}"),
                via="override",
            )
        stats["n_override_raws"] += 1

    if compose_legacy and legacy_path and legacy_path.exists():
        legacy = _load_yaml(legacy_path)
        # trainable → head targets (from current inv)
        trainable_hits = {
            t: inv[t] for t in list(inv.keys()) if t in inv
        }
        for _k, meta in (legacy.get("mappings") or {}).items():
            if not isinstance(meta, dict):
                continue
            raw = meta.get("raw_label")
            trainable = meta.get("trainable_fact")
            if meta.get("drop") or not raw or not trainable:
                continue
            raw = str(raw)
            trainable = str(trainable)
            if raw in inv:
                continue  # already covered by include_raw / override
            if trainable not in trainable_hits:
                continue
            for e in trainable_hits[trainable]:
                _add(
                    inv,
                    raw,
                    head=e["head"],
                    value=e["value"],
                    train_label=e["train_label"],
                    via=f"legacy_bridge:{trainable}",
                )
            stats["n_legacy_bridge_raws"] += 1

    return inv, stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ontology", type=Path, default=DEFAULT_ONT)
    ap.add_argument("--proposed", type=Path, default=DEFAULT_PROPOSED)
    ap.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES)
    ap.add_argument("--legacy", type=Path, default=DEFAULT_LEGACY)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--no-legacy-bridge", action="store_true")
    args = ap.parse_args()

    ont = _load_yaml(args.ontology)
    proposed = _load_yaml(args.proposed)
    overrides = _load_yaml(args.overrides) if args.overrides.exists() else {}

    inv, stats = build_inventory(
        ont,
        proposed,
        overrides=overrides,
        legacy_path=None if args.no_legacy_bridge else args.legacy,
        compose_legacy=not args.no_legacy_bridge,
    )

    # conflict report: same raw → multiple values on same head
    same_head_conflicts = []
    multi_head = 0
    for raw, rules in inv.items():
        by_head: dict[str, set[str]] = defaultdict(set)
        for e in rules:
            by_head[e["head"]].add(e["value"])
        if len(by_head) > 1:
            multi_head += 1
        for h, vals in by_head.items():
            if len(vals) > 1:
                same_head_conflicts.append({"raw": raw, "head": h, "values": sorted(vals)})

    schema = _load_yaml(DEFAULT_SCHEMA)
    head_values = {
        name: [str(v) for v in (meta.get("values") or [])]
        for name, meta in (schema.get("heads") or {}).items()
        if isinstance(meta, dict)
    }

    # drop invalid head/value vs schema; keep explicit empty overrides (drop list)
    explicit_drops = {
        str(k)
        for k, v in ((overrides or {}).get("overrides") or {}).items()
        if not v
    }
    cleaned: dict[str, list[dict[str, str]]] = {}
    dropped_invalid = 0
    for raw, rules in inv.items():
        keep = []
        for e in rules:
            allowed = head_values.get(e["head"])
            if allowed is None or e["value"] not in allowed:
                dropped_invalid += 1
                continue
            keep.append(e)
        if keep or raw in explicit_drops:
            cleaned[raw] = keep

    out_doc = {
        "version": "raw_to_multihead_v1",
        "source_ontology": str(args.ontology.as_posix()),
        "source_ontology_version": ont.get("version"),
        "schema": "stage2_multihead_v3.1",
        "evidence_rule": ont.get("evidence_rule"),
        "note": (
            "Invert training_ontology_v3 include_raw (+ absorbed + Contactability.denied). "
            "Overrides replace polluted/missing Stage2 aliases. "
            "Legacy bridge expands inventory raws via Stage2 trainable names that hit include_raw."
        ),
        "resolution_priority": overrides.get("resolution_priority") or DEFAULT_PRIORITY,
        "stats": {
            **stats,
            "n_raw_keys": len(cleaned),
            "n_multi_head_raws": multi_head,
            "n_same_head_conflicts": len(same_head_conflicts),
            "n_dropped_invalid_vs_schema": dropped_invalid,
        },
        "same_head_conflicts": same_head_conflicts[:50],
        "mappings": {k: cleaned[k] for k in sorted(cleaned)},
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        yaml.safe_dump(out_doc, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    report = MH / "data" / "reports" / "raw_to_multihead_export.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(out_doc["stats"], ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out_doc["stats"], ensure_ascii=False, indent=2))
    print(f"wrote {args.out}")
    print(f"wrote {report}")


if __name__ == "__main__":
    main()
