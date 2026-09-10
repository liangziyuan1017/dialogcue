import argparse
import json
import sys
from pathlib import Path

from check_data_format import check_record
from f007_infrastructure.jsonl_utils import load_jsonl

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
INPUT_DIR = DATA_DIR / "data_input"
INPUT_DATA_PATH = INPUT_DIR / "input_data.jsonl"
REWARDED_PATH = BASE_DIR / "f003_reward_labeling" / "data" / "output_rewarded.jsonl"


def _load_call_ids_from_jsonl(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            cid = record.get("call_id", "")
            if cid:
                ids.add(cid)
    return ids


def _load_existing_call_ids():
    existing = _load_call_ids_from_jsonl(INPUT_DATA_PATH)
    if REWARDED_PATH.exists():
        existing |= {r["call_id"] for r in load_jsonl(REWARDED_PATH) if r.get("call_id")}
    return existing


def _load_new_records(new_input_path):
    records = []
    parse_errors = []
    with open(new_input_path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                records.append((i, json.loads(line)))
            except json.JSONDecodeError as e:
                parse_errors.append(f"line {i + 1}: JSON parse error: {e}")
    return records, parse_errors


def check_new_records(new_input_path):
    existing_ids = _load_existing_call_ids()
    indexed_records, parse_errors = _load_new_records(new_input_path)

    errors = list(parse_errors)
    new_ids = []
    seen = set()

    for i, record in indexed_records:
        cid = record.get("call_id", "")
        if not cid:
            errors.append(f"record {i}: missing or empty call_id")
            continue
        if cid in existing_ids:
            errors.append(f"record {i}: call_id '{cid}' collides with existing data")
        if cid in seen:
            errors.append(f"record {i}: call_id '{cid}' duplicated within new batch")
        seen.add(cid)
        new_ids.append(cid)

        _fmt, fmt_errors = check_record(i, record)
        errors.extend(fmt_errors)

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return None, errors

    return new_ids, []


def main():
    parser = argparse.ArgumentParser(description="Pre-check new records for incremental append")
    parser.add_argument(
        "--new-input",
        default="data/data_input/new_data.jsonl",
        help="Path to new records JSONL file",
    )
    args = parser.parse_args()

    if not Path(args.new_input).exists():
        print(f"File not found: {args.new_input}", file=sys.stderr)
        sys.exit(1)

    new_ids, errors = check_new_records(args.new_input)
    if errors:
        print(f"Pre-check FAILED: {len(errors)} error(s)", file=sys.stderr)
        sys.exit(1)

    print(f"Pre-check PASSED: {len(new_ids)} new record(s)")
    for cid in new_ids:
        print(f"  call_id: {cid}")
    sys.exit(0)


if __name__ == "__main__":
    main()
