"""
Propagate extra fields from output_merged.py into output_labeled.
Matches records by (call_id, cust_no).
Removes stale snake_case fields, adds canonical camelCase fields from merged source.
"""
import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
MERGED_FILE = _PROJECT_ROOT / "data" / "data_output" / "output_merged.py"

TARGET_FILES = [
    _PROJECT_ROOT / "src" / "f000_keyword_discovery" / "data" / "output_labeled.py",
]

CANONICAL_FIELDS = [
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

STALE_FIELDS = [
    "customer_info",
    "call_date",
    "coll_user_id",
    "mob_typ",
    "talk_time",
    "plan_evaluation",
]


def load_results(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        code = compile(f.read(), path, "exec")
        namespace = {}
        exec(code, namespace)
        return namespace.get("results", [])


def write_results(results: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("results = ")
        f.write(json.dumps(results, ensure_ascii=False, indent=2))
        f.write("\n")


def main() -> None:
    merged = load_results(MERGED_FILE)
    merged_index = {(r["call_id"], r.get("cust_no", "")): r for r in merged}

    for target_path in TARGET_FILES:
        if not target_path.exists():
            print(f"  SKIP (not found): {target_path}")
            continue

        results = load_results(target_path)
        matched = 0
        unmatched = 0

        for r in results:
            key = (r["call_id"], r.get("cust_no", ""))
            src = merged_index.get(key)
            if src is None:
                unmatched += 1
                continue
            matched += 1
            for field in STALE_FIELDS:
                r.pop(field, None)
            for field in CANONICAL_FIELDS:
                if field in src:
                    r[field] = src[field]

        write_results(results, target_path)
        print(f"{target_path.name}: {matched} matched, {unmatched} unmatched, {len(results)} total")


if __name__ == "__main__":
    main()
