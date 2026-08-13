#!/usr/bin/env python3
"""Convert .py literal result files (results = [...]) to JSONL format.

Usage:
    python3 src/scripts/convert_py_to_jsonl.py [--dry-run]

Converts:
    src/f000_keyword_discovery/data/output_labeled.py  → .jsonl
    src/f001_schema_alignment/data/output_aligned.py    → .jsonl
    src/f003_reward_labeling/data/output_rewarded.py    → .jsonl
"""
import argparse
import ast
import json
import sys
from pathlib import Path


def load_py_results(path: Path) -> list[dict]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "results"
            for target in statement.targets
        ):
            value = ast.literal_eval(statement.value)
            if isinstance(value, list) and all(isinstance(record, dict) for record in value):
                return value
            break
    raise ValueError(f"{path} does not contain a literal results = [...] assignment")


def convert_one(py_path: Path, dry_run: bool = False) -> Path:
    jsonl_path = py_path.with_suffix(".jsonl")
    records = load_py_results(py_path)
    if not dry_run:
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"{'[DRY-RUN] ' if dry_run else ''}{py_path} → {jsonl_path} ({len(records)} records)")
    return jsonl_path


DEFAULT_TARGETS = [
    "src/f000_keyword_discovery/data/output_labeled.py",
    "src/f001_schema_alignment/data/output_aligned.py",
    "src/f003_reward_labeling/data/output_rewarded.py",
]


def main():
    parser = argparse.ArgumentParser(description="Convert .py literal files to JSONL")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be converted without writing")
    parser.add_argument("--targets", nargs="*", default=None, help="Specific .py files to convert")
    args = parser.parse_args()

    targets = args.targets or DEFAULT_TARGETS
    base = Path(__file__).resolve().parent.parent.parent

    for rel in targets:
        py_path = (base / rel).resolve()
        if not py_path.exists():
            print(f"SKIP (not found): {py_path}", file=sys.stderr)
            continue
        convert_one(py_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
