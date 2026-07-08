"""
Remove records from f004/f005 data files that don't belong to the valid call_id set.
Valid IDs are loaded from ids.md (103 call_ids from f003 output).
"""
import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
IDS_FILE = _PROJECT_ROOT / "ids.md"
DIALOG_RECORDS_FILE = _PROJECT_ROOT / "src" / "f004_decision_tree" / "data" / "dialog_records.json"
MERGE_DECISIONS_FILE = _PROJECT_ROOT / "src" / "f004_decision_tree" / "data" / "merge_decisions.json"


def load_valid_ids() -> set:
    with open(IDS_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def prune_dialog_records(valid_ids: set) -> None:
    with open(DIALOG_RECORDS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    before = len(data)
    data = [r for r in data if r["call_id"] in valid_ids]
    after = len(data)
    with open(DIALOG_RECORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"dialog_records.json: {before} → {after} (removed {before - after})")


def prune_merge_decisions(valid_ids: set) -> None:
    with open(MERGE_DECISIONS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    before = len(data)
    before_ids = set(k.split(":")[0] for k in data.keys())
    data = {k: v for k, v in data.items() if k.split(":")[0] in valid_ids}
    after = len(data)
    after_ids = set(k.split(":")[0] for k in data.keys())
    with open(MERGE_DECISIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"merge_decisions.json: {before} keys ({len(before_ids)} call_ids) → {after} keys ({len(after_ids)} call_ids) (removed {before - after} keys)")


def main() -> None:
    valid_ids = load_valid_ids()
    print(f"Valid IDs: {len(valid_ids)}")
    prune_dialog_records(valid_ids)
    prune_merge_decisions(valid_ids)


if __name__ == "__main__":
    main()
