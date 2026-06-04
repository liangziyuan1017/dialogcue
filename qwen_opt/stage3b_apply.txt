"""
Stage 3b: Apply structural operations (merge, split, reorder, insert, delete).
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
STRUCTURES_FILE = DATA_DIR / "stage3a_structures.json"
OUTPUT_FILE = DATA_DIR / "stage3b_restructured.json"

PROMPT = """\
Role: Dialogue structure repairer for Chinese debt-collection call transcripts

Task:
Apply the identified structural operations to the dialogue.
For merge/split/reorder/delete: modify turn boundaries.
For insert_missing: infer a short natural response and mark it with "label": "1".

Constraints:
- For merge: concatenate texts, keep first turn's index
- For split: divide text at the identified point into two turns
- For reorder: move turn to specified position
- For delete_garbage: remove the turn entirely
- For insert_missing: generate a short (≤15 char) natural response
  - Allowed customer responses: 嗯, 对, 好, 是, 知道了, 明白, 噢, 啊,
    那怎么办, 我现在确实困难, 能不能重新分期, 一次性拿不出来, 利息太高了
  - Allowed collector responses: 嗯, 好的, 明白
  - Mark ALL inserted turns with "label": "1"
- Do NOT rewrite existing turn text (only change boundaries)
- Preserve all original turn content within new boundaries

Evaluation criteria:
- Merged turns must read as one natural utterance
- Inserted turns must be short and contextually appropriate
- No existing text content is lost (only re-bounded or removed if garbage)

Required output format:
{
  "record": {
    "call_id": "...",
    "dialog": [
      {"index": 0, "role": "催收员", "text": "...", "label": "0"},
      {"index": 1, "role": "客户", "text": "...", "label": "1"}
    ]
  }
}
"""


def run(records: list[dict], structures: list[dict]) -> list[dict]:
    client = create_client()
    results = []
    for i, (record, struct) in enumerate(zip(records, structures)):
        rec = record.get("record", record)
        call_id = rec.get("call_id", f"record_{i}")
        print(f"  [3b] Applying structure {i+1}/{len(records)} (call_id={call_id})...")

        user_data = {
            "record": {
                "call_id": call_id,
                "dialog": rec.get("dialog", []),
            },
            "operations": struct.get("operations", []),
        }
        result = call_llm(client, PROMPT, user_data)
        results.append(result)
    return results


def main(count: int = 0) -> None:
    records = load_json_records(INPUT_FILE)
    structures = load_json_records(STRUCTURES_FILE)
    if count > 0:
        records = records[:count]
        structures = structures[:count]
    print(f"[Stage 3b] Applying structural changes to {len(records)} records...")
    results = run(records, structures)
    save_json_records(results, OUTPUT_FILE)
    print(f"[Stage 3b] Output saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    main(n)
