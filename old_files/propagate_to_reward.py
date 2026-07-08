"""
Propagate canonical fields from f001 output_aligned.py into f003 output_rewarded.py.
Matches records by (call_id, cust_no).
Removes stale snake_case fields, adds canonical camelCase fields and context from aligned source.
"""
import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_FILE = _PROJECT_ROOT / "src" / "f001_schema_alignment" / "data" / "output_aligned.py"
TARGET_FILE = _PROJECT_ROOT / "src" / "f003_reward_labeling" / "data" / "output_rewarded.py"

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


def _python_dumps(obj, indent=2):
    text = json.dumps(obj, indent=indent, ensure_ascii=False)
    text = text.replace(": null", ": None")
    text = text.replace(": true", ": True")
    text = text.replace(": false", ": False")
    return text


def write_results(results: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("results = ")
        f.write(_python_dumps(results))
        f.write("\n")


def main() -> None:
    source = load_results(SOURCE_FILE)
    source_index = {(r["call_id"], r.get("cust_no", "")): r for r in source}

    results = load_results(TARGET_FILE)
    matched = 0
    unmatched = 0

    matched_results = []
    for r in results:
        for field in STALE_FIELDS:
            r.pop(field, None)
        key = (r["call_id"], r.get("cust_no", ""))
        src = source_index.get(key)
        if src is None:
            unmatched += 1
            continue
        matched += 1
        for field in CANONICAL_FIELDS:
            if field in src:
                r[field] = src[field]
        if "context" in src:
            r["context"] = src["context"]
        matched_results.append(r)

    write_results(matched_results, TARGET_FILE)
    print(f"{TARGET_FILE.name}: {matched} matched, {unmatched} unmatched (removed), {len(matched_results)} written")


if __name__ == "__main__":
    main()
