"""
Stage 2a: Identify specific corrupted spans in 催收员 turns.
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
OUTPUT_FILE = DATA_DIR / "stage2a_corruptions.json"

PROMPT = """\
Role: ASR corruption detector for Chinese debt-collection collector speech

Task:
Scan each 催收员 turn and identify specific spans that are ASR corruption.
Output a list of corruptions with their location, type, and likely intended text.

Constraints:
- Only analyze 催收员 turns; ignore 客户 turns completely
- Only flag spans that are clearly ASR errors, not natural spoken disfluency
- Natural fillers (嗯, 呃, 就是说, 嘛, 这边的话) are NOT corruption
- Emotional hesitation is NOT corruption
- Assign confidence: "high" (unambiguous error) or "low" (possibly intentional)

Corruption types:
- homophone: wrong characters with same/similar pronunciation
- malformed_number: broken or garbled numeric expression
- garbled_fragment: nonsensical word combination
- duplicated_token: repeated garbage tokens (e.g. 卡卡卡片)
- broken_grammar: impossible grammatical structure
- semantic_error: phrase that breaks the logical flow of negotiation

Evaluation criteria:
- "需帮利交违约金" → corruption (garbled_fragment), likely "利息和违约金"
- "嗯，这边的话就是说" → NOT corruption (natural filler)
- "卡卡卡片" → corruption (duplicated_token), likely "卡片"
- "20026000多" → corruption (malformed_number), likely "26000多"

Required output format:
{
  "corruptions": [
    {
      "turn_index": 5,
      "span": "如话",
      "corruption_type": "homophone",
      "likely_intended": "如果",
      "confidence": "high"
    }
  ]
}
"""


def run(records: list[dict]) -> list[dict]:
    client = create_client()
    results = []
    for i, record in enumerate(records):
        rec = record.get("record", record)
        call_id = rec.get("call_id", f"record_{i}")
        print(f"  [2a] Identifying corruptions {i+1}/{len(records)} (call_id={call_id})...")

        collector_turns = [
            t for t in rec.get("dialog", []) if t.get("role") == "催收员"
        ]
        user_data = {
            "call_id": call_id,
            "collector_turns": collector_turns,
        }
        result = call_llm(client, PROMPT, user_data, thinking_budget=0)
        result["call_id"] = call_id
        results.append(result)
    return results


def main(count: int = 0) -> None:
    records = load_json_records(INPUT_FILE)
    if count > 0:
        records = records[:count]
    print(f"[Stage 2a] Identifying corruptions in {len(records)} records...")
    results = run(records)
    save_json_records(results, OUTPUT_FILE)
    print(f"[Stage 2a] Output saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    main(n)
