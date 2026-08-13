import argparse
import json
import os
import sys
from pathlib import Path

from check_data_format import check_record
from f007_infrastructure.jsonl_utils import load_jsonl


def _load_existing_call_ids():
    rewarded_path = os.path.join(
        os.path.dirname(__file__), "f003_reward_labeling", "data", "output_rewarded.jsonl"
    )
    if not os.path.exists(rewarded_path):
        return set()
    return {r["call_id"] for r in load_jsonl(Path(rewarded_path))}


def _load_new_records(new_input_path):
    records = []
    with open(new_input_path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def check_new_records(new_input_path):
    existing_ids = _load_existing_call_ids()
    new_records = _load_new_records(new_input_path)

    errors = []
    new_ids = []
    seen = set()

    for i, record in enumerate(new_records):
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

        fmt, fmt_errors = check_record(i, record)
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
