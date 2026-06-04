"""
Stage 3a: Identify structural issues in the dialogue (fragmented turns, missing turns, etc.).
"""

import sys
from pathlib import Path

from llm_utils import (
    DATA_DIR,
    call_llm,
    create_client,
    load_json_records,
    save_json_records,
)

INPUT_FILE = DATA_DIR / "stage2c_validated.json"
OUTPUT_FILE = DATA_DIR / "stage3a_structures.json"

PROMPT = """\
Role: Dialogue structure analyst for Chinese debt-collection call transcripts

Task:
Analyze the dialogue turn sequence and identify structural problems:
fragmented turns, wrongly merged turns, misplaced turns, missing responses,
and garbage turns.

Constraints:
- Only identify structural issues, do not rewrite any text
- merge: consecutive same-speaker turns that are one utterance split by ASR
- split: one turn containing two distinct conversational intents
- reorder: a turn that is clearly a response to an earlier turn but appears later
- insert_missing: a point where a short response is clearly expected but absent
  (e.g., collector asks a question with no customer reply)
- delete_garbage: turn is pure ASR duplication with no semantic content
- Be conservative: only flag clear structural problems, not maybes

Evaluation criteria:
- Two consecutive 催收员 turns where second continues first's sentence → merge
- 催收员 asks "您看这样可以不吗" followed by another 催收员 turn → insert_missing (客户)
- Single turn with "嗯；那这样的话" → split

Required output format:
{
  "operations": [
    {"type": "merge", "indices": [5, 6], "reason": "fragments of one utterance"},
    {"type": "split", "index": 12, "after_char": 15, "reason": "two distinct intents"},
    {"type": "reorder", "index": 18, "move_after": 15, "reason": "misplaced response"},
    {"type": "insert_missing", "after_index": 9, "role": "客户", "reason": "collector asked question"},
    {"type": "delete_garbage", "index": 22, "reason": "duplicated fragment"}
  ]
}
"""


def run(records: list[dict]) -> list[dict]:
    client = create_client()
    results = []
    for i, record in enumerate(records):
        rec = record.get("record", record)
        call_id = rec.get("call_id", f"record_{i}")
        print(f"  [3a] Analyzing structure {i+1}/{len(records)} (call_id={call_id})...")

        user_data = {
            "call_id": call_id,
            "dialog": rec.get("dialog", []),
        }
        result = call_llm(client, PROMPT, user_data, thinking_budget=0)
        result["call_id"] = call_id
        results.append(result)
    return results


def main(count: int = 0) -> None:
    records = load_json_records(INPUT_FILE)
    if count > 0:
        records = records[:count]
    print(f"[Stage 3a] Analyzing structure of {len(records)} records...")
    results = run(records)
    save_json_records(results, OUTPUT_FILE)
    print(f"[Stage 3a] Output saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    main(n)
