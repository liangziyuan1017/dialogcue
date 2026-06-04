"""
Stage 1a: Classify each dialogue turn as clean, emotional_disfluency, asr_noise, or asr_corruption.
"""

import sys

from llm_utils import (
    DATA_DIR,
    PROJECT_DIR,
    call_llm,
    create_client,
    load_source_records,
    parse_dialog_turns,
    save_json_records,
)

SOURCE_FILE = PROJECT_DIR / "data_0520.json"
OUTPUT_FILE = DATA_DIR / "stage1a_classifications.json"

PROMPT = """\
Role: ASR disfluency classifier for Mandarin phone call transcripts

Task:
Classify each dialogue turn into one of four categories based on whether
its non-standard speech is emotionally meaningful or ASR corruption.

Constraints:
- Category "emotional_disfluency": hesitation, stutter, repetition, restart,
  trailing thought that reflects real emotional state (stress, pleading, confusion)
- Category "asr_noise": meaningless filler repetition, garbled fragments,
  duplicated half-sentences, dangling conjunctions with no emotional value
- Category "asr_corruption": malformed numbers, nonsensical word combos,
  impossible sentence fragments, broken semantic structure
- Category "clean": grammatically acceptable, no artifacts

Evaluation criteria:
- Stutters under financial pressure → emotional_disfluency
- Tripled filler "就是说就是说就是说" → asr_noise
- Broken number "20026000多" → asr_corruption
- Normal complete sentence → clean

Required output format:
{
  "classifications": [
    {"index": 0, "category": "clean", "reason": "...", "preserve": true},
    {"index": 1, "category": "emotional_disfluency", "reason": "...", "preserve": true},
    {"index": 2, "category": "asr_noise", "reason": "...", "preserve": false}
  ]
}
"""


def prepare_input(record: dict) -> dict:
    dialog_raw = record.get("dialog", "")
    if isinstance(dialog_raw, list):
        turns = dialog_raw
    else:
        turns = parse_dialog_turns(dialog_raw)
    return {
        "call_id": record.get("call_id", ""),
        "dialog": turns,
    }


def run(records: list[dict]) -> list[dict]:
    client = create_client()
    results = []
    for i, record in enumerate(records):
        call_id = record.get("call_id", f"record_{i}")
        print(f"  [1a] Classifying record {i+1}/{len(records)} (call_id={call_id})...")
        user_data = prepare_input(record)
        result = call_llm(client, PROMPT, user_data, thinking_budget=0)
        result["call_id"] = call_id
        results.append(result)
    return results


def main(count: int = 0) -> None:
    records = load_source_records(SOURCE_FILE)
    if count > 0:
        records = records[:count]
    print(f"[Stage 1a] Classifying {len(records)} records...")
    results = run(records)
    save_json_records(results, OUTPUT_FILE)
    print(f"[Stage 1a] Output saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    main(n)
