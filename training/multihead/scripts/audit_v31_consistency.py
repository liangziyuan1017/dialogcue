#!/usr/bin/env python3
"""v3.1 consistency audit (colleague RC1 gate).

Checks:
1. raw → multi-head conflict (same raw hits >1 head)
2. same-head polarity conflict (e.g. Asset.available + unavailable)
3. orphan raws (override emptied / no Softmax落点)
4. optional: supervision row consistency from head_supervision_stats.json

Exit 0 always unless --strict (then conflicts → non-zero).
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

MH = Path(__file__).resolve().parents[1]
DEFAULT_MAP = MH / "configs" / "raw_to_multihead.yaml"
DEFAULT_OVERRIDES = MH / "configs" / "raw_to_multihead_overrides.yaml"
DEFAULT_OUT = MH / "data" / "reports" / "v31_consistency_audit.json"
DEFAULT_MD = MH / "data" / "reports" / "v31_consistency_audit.md"
DEFAULT_SUP = MH / "data" / "reports" / "head_supervision_stats.json"


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def audit_mappings(
    mappings: dict[str, list[dict]],
    *,
    explicit_drops: set[str],
) -> dict[str, Any]:
    multi_head: list[dict] = []
    polarity: list[dict] = []
    orphans: list[str] = []

    for raw, rules in mappings.items():
        rules = rules or []
        if not rules:
            orphans.append(raw)
            continue
        by_head: dict[str, set[str]] = defaultdict(set)
        for e in rules:
            by_head[str(e["head"])].add(str(e["value"]))
        if len(by_head) > 1:
            multi_head.append(
                {
                    "raw": raw,
                    "heads": sorted(by_head.keys()),
                    "targets": [
                        {"head": h, "values": sorted(vs)} for h, vs in sorted(by_head.items())
                    ],
                }
            )
        for h, vals in by_head.items():
            if len(vals) > 1:
                polarity.append({"raw": raw, "head": h, "values": sorted(vals)})

    # overrides emptied but missing from mappings entirely
    missing_drop_keys = sorted(explicit_drops - set(mappings.keys()))

    return {
        "n_raw_keys": len(mappings),
        "n_multi_head_conflicts": len(multi_head),
        "n_polarity_conflicts": len(polarity),
        "n_orphan_raws": len(orphans),
        "n_explicit_drop_missing_from_map": len(missing_drop_keys),
        "multi_head_conflicts": multi_head,
        "polarity_conflicts": polarity,
        "orphan_raws": orphans,
        "explicit_drop_missing_from_map": missing_drop_keys,
        "orphan_note": (
            "orphan = mapping targets empty (usually intentional override drop). "
            "Review periodically; not a Softmax training bug by itself."
        ),
    }


def audit_supervision(sup_path: Path) -> dict[str, Any] | None:
    if not sup_path.exists():
        return None
    doc = json.loads(sup_path.read_text(encoding="utf-8"))
    n = int(doc.get("n_samples") or 0)
    issues: list[str] = []
    per = []
    for head, row in (doc.get("per_head") or {}).items():
        pos = int(row.get("positive") or 0)
        neg = int(row.get("negative") or 0)
        unk = int(row.get("unknown") or 0)
        total = pos + neg + unk
        ok = total == n
        if not ok:
            issues.append(f"{head}: pos+neg+unk={total} != n_samples={n}")
        per.append(
            {
                "head": head,
                "positive": pos,
                "negative": neg,
                "unknown": unk,
                "sum": total,
                "consistent": ok,
            }
        )
    return {
        "n_samples": n,
        "all_consistent": len(issues) == 0,
        "issues": issues,
        "per_head": per,
    }


def write_md(path: Path, report: dict) -> None:
    m = report["mapping_audit"]
    lines = [
        "# v3.1 Consistency Audit",
        "",
        f"- map: `{report.get('map_path')}`",
        f"- multi-head conflicts: **{m['n_multi_head_conflicts']}**",
        f"- polarity conflicts: **{m['n_polarity_conflicts']}**",
        f"- orphan raws (empty targets): **{m['n_orphan_raws']}**",
        "",
        "## Multi-head conflicts",
        "",
    ]
    if not m["multi_head_conflicts"]:
        lines.append("- (none)")
    else:
        for row in m["multi_head_conflicts"][:50]:
            lines.append(f"- `{row['raw']}` → {row['heads']}")
    lines.extend(["", "## Polarity conflicts", ""])
    if not m["polarity_conflicts"]:
        lines.append("- (none)")
    else:
        for row in m["polarity_conflicts"][:50]:
            lines.append(f"- `{row['raw']}` / `{row['head']}` → {row['values']}")
    lines.extend(
        [
            "",
            "## Orphan raws (sample)",
            "",
            m.get("orphan_note") or "",
            "",
        ]
    )
    sample = m["orphan_raws"][:40]
    if not sample:
        lines.append("- (none)")
    else:
        for r in sample:
            lines.append(f"- `{r}`")
        if m["n_orphan_raws"] > 40:
            lines.append(f"- … +{m['n_orphan_raws'] - 40} more")

    s = report.get("supervision_audit")
    lines.extend(["", "## Supervision consistency", ""])
    if s is None:
        lines.append("- (no head_supervision_stats.json — build dataset first)")
    else:
        lines.append(f"- all_consistent: **{s['all_consistent']}**")
        for iss in s.get("issues") or []:
            lines.append(f"- ERROR: {iss}")
        if s["all_consistent"]:
            lines.append("- pos + neg + unknown == n_samples for all heads")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="v3.1 consistency audit")
    ap.add_argument("--map", type=Path, default=DEFAULT_MAP)
    ap.add_argument("--overrides", type=Path, default=DEFAULT_OVERRIDES)
    ap.add_argument("--supervision", type=Path, default=DEFAULT_SUP)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--md", type=Path, default=DEFAULT_MD)
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if multi-head or polarity conflicts exist",
    )
    args = ap.parse_args()

    doc = _load_yaml(args.map)
    mappings = doc.get("mappings") or {}
    ov = _load_yaml(args.overrides) if args.overrides.exists() else {}
    explicit_drops = {
        str(k) for k, v in (ov.get("overrides") or {}).items() if not v
    }

    mapping_audit = audit_mappings(mappings, explicit_drops=explicit_drops)
    supervision_audit = audit_supervision(args.supervision)

    report = {
        "version": "v3.1-rc1",
        "map_path": str(args.map),
        "mapping_audit": mapping_audit,
        "supervision_audit": supervision_audit,
        "passed_conflicts": (
            mapping_audit["n_multi_head_conflicts"] == 0
            and mapping_audit["n_polarity_conflicts"] == 0
        ),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_md(args.md, report)

    print(
        json.dumps(
            {
                "passed_conflicts": report["passed_conflicts"],
                "n_multi_head": mapping_audit["n_multi_head_conflicts"],
                "n_polarity": mapping_audit["n_polarity_conflicts"],
                "n_orphans": mapping_audit["n_orphan_raws"],
                "supervision_ok": None
                if supervision_audit is None
                else supervision_audit["all_consistent"],
                "out": str(args.out),
                "md": str(args.md),
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    if args.strict and not report["passed_conflicts"]:
        raise SystemExit(1)
    if args.strict and supervision_audit and not supervision_audit["all_consistent"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
