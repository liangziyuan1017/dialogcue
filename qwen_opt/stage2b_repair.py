"""
Stage 2b: Repair identified ASR corruptions in 催收员 turns.
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

INPUT_FILE = DATA_DIR / "stage1b_rewritten.json"
CORRUPTIONS_FILE = DATA_DIR / "stage2a_corruptions.json"
OUTPUT_FILE = DATA_DIR / "stage2b_repaired.json"

PROMPT = """\
Role: ASR corruption repairer for Chinese debt-collection collector speech

Task:
Apply the identified corruption repairs to the 催收员 turns.
Use the likely_intended field as a strong hint but verify against context.

Constraints:
- Only modify 催收员 turns at the specified indices and spans
- Do NOT modify any 客户 turn
- Do NOT modify spans not listed in the corruption report
- Do NOT over-formalize: keep conversational tone
- Do NOT remove natural fillers (嗯, 呃, 就是说, 嘛)
- Preserve emotional pacing, hesitation, interruptions
- If a likely_intended value seems wrong given context, use your own judgment

Evaluation criteria:
- "嗯，因为您这个卡片是流通卡嘛，这边还是建议您先把最低还款还了。" → GOOD (conversational)
- "由于您的卡属于流通卡，因此建议您偿还最低还款额。" → BAD (over-formalized)

Required output format:
{
  "record": {
    "call_id": "...",
    "dialog": [
      {"index": 0, "role": "催收员", "text": "..."},
      {"index": 1, "role": "客户", "text": "..."}
    ]
  }
}
"""


def run(records: list[dict], corruptions: list[dict]) -> list[dict]:
    client = create_client()
    results = []
    for i, (record, corr) in enumerate(zip(records, corruptions)):
        rec = record.get("record", record)
        call_id = rec.get("call_id", f"record_{i}")
        print(f"  [2b] Repairing {i+1}/{len(records)} (call_id={call_id})...")

        user_data = {
            "record": {
                "call_id": call_id,
                "dialog": rec.get("dialog", []),
            },
            "corruptions": corr.get("corruptions", []),
        }
        result = call_llm(client, PROMPT, user_data)
        results.append(result)
    return results


def main(count: int = 0) -> None:
    records = load_json_records(INPUT_FILE)
    corruptions = load_json_records(CORRUPTIONS_FILE)
    if count > 0:
        records = records[:count]
        corruptions = corruptions[:count]
    print(f"[Stage 2b] Repairing {len(records)} records...")
    results = run(records, corruptions)
    save_json_records(results, OUTPUT_FILE)
    print(f"[Stage 2b] Output saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    main(n)
