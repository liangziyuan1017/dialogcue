#!/usr/bin/env python3
"""v3.1.2-patch1 boundary gate: forbidden raw→head edges + Commitment resistant count.

Fails (--strict) if:
1. Pollution raws still map into Contactability / Asset.available (housing status)
2. Train jsonl Commitment.resistant support < --resistant-min (default 50)

Usage:
  python training/multihead/scripts/audit_patch1_boundary.py
  python training/multihead/scripts/audit_patch1_boundary.py \\
    --map training/multihead/configs/raw_to_multihead.yaml \\
    --train-jsonl training/multihead/data/state/state_train.jsonl \\
    --strict
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

MH = Path(__file__).resolve().parents[1]

# Must NOT land on these heads/values after patch1
FORBIDDEN: list[tuple[str, str | None, str | None]] = [
    # raw, forbidden_head, forbidden_value (None = any value on head)
    ("time_constraint", "Contactability", None),
    ("busy", "Contactability", None),
    ("location", "Contactability", None),
    ("contact_difficulty", "Contactability", None),
    ("missed_communication", "Contactability", None),
    ("payment_deadline", "Contactability", None),
    ("complaint", "Contactability", None),
    ("self_residence", "Asset", "available"),
    ("housing", "Asset", "available"),
    ("housing_situation", "Asset", "available"),
    ("staying_with_friend", "Asset", "available"),
    ("family_house", "Asset", "available"),
    ("borrowed_residence", "Asset", "available"),
    ("no_overdue_mortgage", "Asset", "unavailable"),
]

# Must land here after remap
REQUIRED: list[tuple[str, str, str]] = [
    ("staying_with_friend", "Asset", "unavailable"),
    ("family_house", "Asset", "unavailable"),
    ("borrowed_residence", "Asset", "unavailable"),
]


def _load_map(path: Path) -> dict[str, list[dict]]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return dict(doc.get("mappings") or {})


def check_mappings(mappings: dict[str, list[dict]]) -> list[str]:
    errs: list[str] = []
    for raw, head, val in FORBIDDEN:
        rules = mappings.get(raw) or []
        for e in rules:
            if e.get("head") != head:
                continue
            if val is None or e.get("value") == val:
                errs.append(
                    f"FORBIDDEN still mapped: {raw} → {e.get('head')}.{e.get('value')} "
                    f"(via={e.get('via')})"
                )
    for raw, head, val in REQUIRED:
        rules = mappings.get(raw) or []
        ok = any(e.get("head") == head and e.get("value") == val for e in rules)
        if not ok:
            errs.append(f"REQUIRED missing: {raw} → {head}.{val} (got {rules})")
    return errs


def count_resistant(train_jsonl: Path) -> int:
    if not train_jsonl.exists():
        return -1
    n = 0
    with train_jsonl.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            labels = row.get("labels") or {}
            mask = row.get("head_mask") or {}
            if (
                str(labels.get("Commitment")) == "resistant"
                and int(mask.get("Commitment") or 0) == 1
            ):
                n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--map",
        type=Path,
        default=MH / "configs" / "raw_to_multihead.yaml",
    )
    ap.add_argument(
        "--train-jsonl",
        type=Path,
        default=MH / "data" / "state" / "state_train.jsonl",
    )
    ap.add_argument("--resistant-min", type=int, default=50)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument(
        "--out",
        type=Path,
        default=MH / "data" / "reports" / "patch1_boundary_audit.json",
    )
    args = ap.parse_args()

    mappings = _load_map(args.map)
    map_errs = check_mappings(mappings)
    resistant_n = count_resistant(args.train_jsonl)
    resist_err = None
    if resistant_n < 0:
        resist_err = f"train jsonl missing: {args.train_jsonl}"
    elif resistant_n < args.resistant_min:
        resist_err = (
            f"Commitment.resistant supervised={resistant_n} "
            f"< min {args.resistant_min} (path-A gate)"
        )

    report = {
        "patch": "v3.1.2-patch1",
        "map_path": str(args.map),
        "map_errors": map_errs,
        "n_map_errors": len(map_errs),
        "commitment_resistant_supervised": resistant_n,
        "resistant_min": args.resistant_min,
        "resistant_error": resist_err,
        "pass": not map_errs and resist_err is None,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    failed = bool(map_errs) or resist_err is not None
    if args.strict and failed:
        sys.exit(1)
    if failed:
        print("WARN: patch1 boundary gate not green (re-export map / rebuild /补 resistant)", flush=True)
    else:
        print("OK: patch1 boundary gate green", flush=True)


if __name__ == "__main__":
    main()
