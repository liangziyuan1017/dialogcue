"""
Merge extra fields from the source JSONL into the pipeline output.
Matches records by call_id and cust_no.
"""
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = Path(os.environ.get("DATA_FILE", str(BASE_DIR / "matched_data.jsonl")))
OUTPUT_FILE = Path(os.environ.get("OUTPUT_FILE", str(BASE_DIR / "output_merge.py")))

EXTRA_FIELDS = [
    "call_date",
    "coll_user_id",
    "mob_typ",
    "talk_time",
    "plan_evaluation",
    "customer_info",
]


def load_source() -> dict:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    index = {}
    for r in records:
        key = (r["call_id"], r["cust_no"])
        index[key] = r
    return index


def load_results() -> list[dict]:
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        code = compile(f.read(), OUTPUT_FILE, "exec")
        namespace = {}
        exec(code, namespace)
        return namespace.get("results", [])


def write_results(results: list[dict]) -> None:
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("results = ")
        f.write(json.dumps(results, ensure_ascii=False, indent=2))
        f.write("\n")


def main() -> None:
    source_index = load_source()
    results = load_results()

    matched = 0
    unmatched = 0
    for r in results:
        key = (r["call_id"], r["custno"])
        src = source_index.get(key)
        if src is None:
            unmatched += 1
            print(f"  Unmatched: call_id={r['call_id']}, custno={r['custno']}")
            continue
        matched += 1
        for field in EXTRA_FIELDS:
            if field in src:
                r[field] = src[field]

    write_results(results)
    print(f"Done. Matched: {matched}, Unmatched: {unmatched}")


if __name__ == "__main__":
    main()
