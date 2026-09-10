"""
Merge extra fields from the source JSONL into the pipeline output.
Matches records by call_id. Only copies fields that exist on the source record
(aside from dialog, which is replaced by the cleaned response).
"""
import json
import os
from pathlib import Path

from f007_infrastructure.jsonl_utils import load_jsonl, write_jsonl

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = _PROJECT_ROOT / "data" / "data_input"
OUTPUT_DIR = _PROJECT_ROOT / "data" / "data_output"
DATA_FILE = Path(os.environ.get("DATA_FILE", str(INPUT_DIR / "input_data.jsonl")))
OUTPUT_FILE = Path(os.environ.get("OUTPUT_FILE", str(OUTPUT_DIR / "output_merged.jsonl")))

# Never overwrite cleaned dialogue payloads with raw source dialog.
_SKIP_MERGE_FIELDS = {"dialog", "response"}


def load_source() -> dict:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    return {r["call_id"]: r for r in records if r.get("call_id")}


def load_results() -> list[dict]:
    if not OUTPUT_FILE.exists():
        return []
    return load_jsonl(OUTPUT_FILE)


def write_results(results: list[dict]) -> None:
    write_jsonl(OUTPUT_FILE, results)


def main() -> None:
    source_index = load_source()
    results = load_results()

    matched = 0
    unmatched = 0
    for r in results:
        cid = r.get("call_id", "")
        src = source_index.get(cid)
        if src is None:
            unmatched += 1
            print(f"  Unmatched: call_id={cid}")
            continue
        matched += 1
        for field, value in src.items():
            if field in _SKIP_MERGE_FIELDS:
                continue
            r[field] = value

    write_results(results)
    print(f"Done. Matched: {matched}, Unmatched: {unmatched}")


if __name__ == "__main__":
    main()
