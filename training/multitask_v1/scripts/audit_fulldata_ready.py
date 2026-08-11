#!/usr/bin/env python3
"""Pre-flight checks before full-data multitask train.

Validates JSONL presence, contract context, and optionally reuses multihead
map/patch audits (read-only; does not modify multihead).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

MT_ROOT = Path(__file__).resolve().parents[1]
MH_ROOT = MT_ROOT.parent / "multihead"
SRC = MT_ROOT / "src"
sys.path.insert(0, str(SRC))

from paths import load_yaml, resolve_under_mt  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--config",
        type=Path,
        default=MT_ROOT / "configs" / "train_multitask.yaml",
    )
    ap.add_argument(
        "--run-multihead-audits",
        action="store_true",
        help="Also run multihead audit_v31_consistency (+ optional patch1)",
    )
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    cfg = load_yaml(args.config.resolve())
    errors: list[str] = []
    warnings: list[str] = []

    data = cfg.get("data") or {}
    for key in ("train_jsonl", "val_jsonl", "test_jsonl"):
        rel = data.get(key)
        if not rel:
            if key == "test_jsonl":
                rel = "data/multitask_test.jsonl"
            else:
                errors.append(f"missing data.{key}")
                continue
        path = resolve_under_mt(rel)
        # also try relative to config parent
        if not path.exists():
            alt = (args.config.resolve().parent / rel).resolve()
            path = alt if alt.exists() else path
        if not path.exists():
            errors.append(f"{key} not found: {path}")
        else:
            n = sum(1 for _ in path.open(encoding="utf-8") if _.strip())
            print(f"OK {key}: {path} n={n}")
            if n == 0:
                errors.append(f"{key} empty: {path}")

    if data.get("use_mock_if_missing", False):
        warnings.append("use_mock_if_missing=true — disable for full-data")

    ctx = cfg.get("context") or {}
    if int(ctx.get("max_turns", 0)) != 4 or int(ctx.get("max_chars", 0)) != 200:
        warnings.append(f"context not frozen 4x200: {ctx}")
    if str(ctx.get("strategy", "")) != "window_only":
        warnings.append(f"strategy != window_only: {ctx.get('strategy')}")

    model = cfg.get("model_name")
    if model in (None, "", "__mock__"):
        warnings.append("model_name is __mock__ — full-data should use HF/local encoder")

    schema = resolve_under_mt(
        cfg.get("fact_schema_path") or "../multihead/configs/schema_v3.1.yaml"
    )
    if not schema.exists():
        errors.append(f"fact schema missing: {schema}")
    else:
        print(f"OK schema: {schema}")

    for w in warnings:
        print(f"WARN: {w}")
    for e in errors:
        print(f"ERROR: {e}")

    if args.run_multihead_audits:
        audits = [
            MH_ROOT / "scripts" / "audit_v31_consistency.py",
            MH_ROOT / "scripts" / "audit_patch1_boundary.py",
        ]
        for script in audits:
            if not script.exists():
                warnings.append(f"audit script missing: {script}")
                continue
            print(f"+ python {script}", flush=True)
            rc = subprocess.run([sys.executable, str(script)], cwd=str(MH_ROOT)).returncode
            if rc != 0:
                errors.append(f"audit failed rc={rc}: {script.name}")

    report = {
        "errors": errors,
        "warnings": warnings,
        "ok": not errors,
    }
    out = MT_ROOT / "data" / "reports" / "fulldata_ready.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.strict and errors:
        return 2
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
