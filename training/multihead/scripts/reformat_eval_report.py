#!/usr/bin/env python3
"""Rebuild v3.2 eval report from an existing eval_*.json — no model inference.

Keeps the original JSON/MD untouched; writes:
  eval_test_v32.md
  eval_test_v32.json

Usage:
  python training/multihead/scripts/reformat_eval_report.py \\
    --metrics training/multihead/checkpoints/state_v312/eval_test.json

Also copy (required dependency):
  training/multihead/src/metrics/state_metrics.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

MH_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MH_ROOT / "src"))

from metrics.state_metrics import enrich_metrics_from_per_head, format_metrics_md  # noqa: E402
from schema_loader import load_schema  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--metrics", type=Path, required=True, help="eval_*.json from eval_state")
    ap.add_argument(
        "--schema",
        type=Path,
        default=MH_ROOT / "configs" / "schema_v3.1.yaml",
    )
    ap.add_argument("--model", type=str, default="state_best.pt")
    ap.add_argument("--split", type=str, default=None, help="default: infer from filename")
    ap.add_argument("--ontology", type=str, default="v3.1.2 freeze")
    args = ap.parse_args()

    raw = json.loads(args.metrics.read_text(encoding="utf-8"))
    schema = load_schema(str(args.schema))
    metrics = enrich_metrics_from_per_head(raw, schema)

    stem = args.metrics.stem  # e.g. eval_test
    split = args.split
    if split is None:
        split = "test" if stem.endswith("test") else "val" if stem.endswith("val") else "unknown"

    meta = {
        "ontology": args.ontology,
        "model": args.model,
        "split": split,
    }
    md = format_metrics_md(metrics, schema, meta=meta)

    out_md = args.metrics.with_name(f"{stem}_v32.md")
    out_json = args.metrics.with_name(f"{stem}_v32.json")
    out_md.write_text(md, encoding="utf-8")
    out_json.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"wrote {out_md}  (original {args.metrics.with_suffix('.md')} unchanged)")
    print(f"wrote {out_json}  (original {args.metrics} unchanged)")
    print(
        json.dumps(
            {
                "weighted_positive_f1": metrics.get("weighted_positive_f1"),
                "weighted_positive_precision": metrics.get("weighted_positive_precision"),
                "weighted_positive_recall": metrics.get("weighted_positive_recall"),
                "legacy_macro_f1": metrics.get("macro_f1"),
                "evidence_samples": metrics.get("evidence_samples"),
                "head_level_evidence_instances": metrics.get(
                    "head_level_evidence_instances"
                ),
                "report_version": metrics.get("report_version"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
