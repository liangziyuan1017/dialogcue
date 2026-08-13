"""
Merge extra fields from the source JSONL into the pipeline output.
Matches records by call_id and cust_no.
"""
import json
import os
from pathlib import Path

from f007_infrastructure.jsonl_utils import load_jsonl, write_jsonl

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = _PROJECT_ROOT / "data" / "data_input"
OUTPUT_DIR = _PROJECT_ROOT / "data" / "data_output"
DATA_FILE = Path(os.environ.get("DATA_FILE", str(INPUT_DIR / "matched_data.jsonl")))
OUTPUT_FILE = Path(os.environ.get("OUTPUT_FILE", str(OUTPUT_DIR / "output_merged.jsonl")))

EXTRA_FIELDS = [
    "custInfo",
    "dialDate",
    "connectDate",
    "dialType",
    "ringTime",
    "collUserId",
    "collId",
    "collArea",
    "collGroupId",
    "acNo",
    "isRecorded",
    "result",
    "talkTime",
    "channel",
    "corpCode",
    "calledNo",
    "mobTyp",
    "phoneRoute",
    "agentTalkTime",
    "call_date",
    "coll_user_id",
    "mob_typ",
    "talk_time",
    "plan_evaluation",
]

def _get_cust_no(record: dict) -> str:
    return record.get("cust_no") or record.get("custno") or ""

def load_source() -> dict:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    index = {}
    for r in records:
        key = (r["call_id"], _get_cust_no(r))
        index[key] = r
    return index


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
        key = (r["call_id"], _get_cust_no(r))
        src = source_index.get(key)
        if src is None:
            unmatched += 1
            print(f"  Unmatched: call_id={r['call_id']}, cust_no={r['cust_no']}")
            continue
        matched += 1
        for field in EXTRA_FIELDS:
            if field in src:
                r[field] = src[field]

    write_results(results)
    print(f"Done. Matched: {matched}, Unmatched: {unmatched}")


if __name__ == "__main__":
    main()
