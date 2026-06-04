"""
Stage 3c: Final ASR corruption repair pass on remaining issues.
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

INPUT_FILE = DATA_DIR / "stage3b_restructured.json"
OUTPUT_FILE = DATA_DIR / "stage3c_cleaned.json"

PROMPT = """\
Role: Final ASR corruption repairer for Chinese debt-collection dialogues

Task:
After structural repairs, scan all turns for remaining ASR corruption
that was not addressed by structure changes. Repair corrupted spans
while preserving spoken style and emotional texture.

Constraints:
- This is the final text-level cleanup pass
- Repair: malformed numbers, garbled fragments, homophone errors,
  duplicated garbage tokens, broken semantic spans
- Preserve: spoken fillers (嗯, 呃, 就是说, 嘛), hesitation,
  emotional repetition, conversational rhythm
- Do NOT over-formalize into written Chinese
- Do NOT modify turns marked with "label": "1" (just-inserted turns)
- Keep customer sounding: stressed, anxious, negotiating
- Keep collector sounding: procedural, restrained, conversational

Evaluation criteria:
- "20000万6000嗯，462块6毛一" → "26462块6毛1"
- "后面话。好的就是说" → "好的，就是说"
- "嗯，先生，这边的话目前确实没有这个方案。" → unchanged (already natural)

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


def run(records: list[dict]) -> list[dict]:
    client = create_client()
    results = []
    for i, record in enumerate(records):
        rec = record.get("record", record)
        call_id = rec.get("call_id", f"record_{i}")
        print(f"  [3c] Final cleanup {i+1}/{len(records)} (call_id={call_id})...")

        user_data = {
            "record": {
                "call_id": call_id,
                "dialog": rec.get("dialog", []),
            }
        }
        result = call_llm(client, PROMPT, user_data)
        results.append(result)
    return results


def main(count: int = 0) -> None:
    records = load_json_records(INPUT_FILE)
    if count > 0:
        records = records[:count]
    print(f"[Stage 3c] Final cleanup on {len(records)} records...")
    results = run(records)
    save_json_records(results, OUTPUT_FILE)
    print(f"[Stage 3c] Output saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    main(n)
