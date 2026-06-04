"""
Stage 1b: Rewrite turns classified as asr_noise or asr_corruption, preserving all others.
"""

import sys

from llm_utils import (
    DATA_DIR,
    PROJECT_DIR,
    call_llm,
    create_client,
    load_json_records,
    load_source_records,
    parse_dialog_turns,
    save_json_records,
)

SOURCE_FILE = PROJECT_DIR / "data_0520.json"
CLASSIFICATION_FILE = DATA_DIR / "stage1a_classifications.json"
OUTPUT_FILE = DATA_DIR / "stage1b_rewritten.json"

PROMPT = """\
Role: ASR noise editor for Mandarin debt-collection call transcripts

Task:
Rewrite turns classified as "asr_noise" or "asr_corruption" into natural
spoken Mandarin. Preserve turns classified as "clean" or "emotional_disfluency"
exactly as-is.

Constraints:
- Do NOT modify any turn where preserve=true
- Do NOT over-clean emotional disfluency into formal prose
- Do NOT remove hesitation markers (嗯, 呃, 唉) that carry emotion
- Do NOT compress vulnerable customer speech into concise sentences
- DO remove meaningless filler repetition
- DO repair garbled fragments using surrounding context
- Keep spoken rhythm: 就是……, 那个……, sentence restarts, trailing phrases
- Customer should sound: stressed, anxious, negotiating, thinking aloud
- Collector should sound: procedural, pressuring, professionally restrained

Evaluation criteria:
- "我……我是真的一下子拿不出来" must survive unchanged (emotional_disfluency)
- "就是说就是说就是说" must be removed or collapsed (asr_noise)
- Repaired turns must sound like natural spoken Mandarin, not written Chinese

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


def run(records: list[dict], classifications: list[dict]) -> list[dict]:
    client = create_client()
    results = []
    for i, (record, cls) in enumerate(zip(records, classifications)):
        call_id = record.get("call_id", f"record_{i}")
        print(f"  [1b] Rewriting record {i+1}/{len(records)} (call_id={call_id})...")

        dialog_raw = record.get("dialog", "")
        if isinstance(dialog_raw, list):
            turns = dialog_raw
        else:
            turns = parse_dialog_turns(dialog_raw)

        user_data = {
            "record": {
                "call_id": call_id,
                "dialog": turns,
            },
            "classifications": cls.get("classifications", []),
        }
        result = call_llm(client, PROMPT, user_data)
        results.append(result)
    return results


def main(count: int = 0) -> None:
    records = load_source_records(SOURCE_FILE)
    classifications = load_json_records(CLASSIFICATION_FILE)
    if count > 0:
        records = records[:count]
        classifications = classifications[:count]
    print(f"[Stage 1b] Rewriting {len(records)} records...")
    results = run(records, classifications)
    save_json_records(results, OUTPUT_FILE)
    print(f"[Stage 1b] Output saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    main(n)
