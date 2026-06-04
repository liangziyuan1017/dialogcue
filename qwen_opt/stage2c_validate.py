"""
Stage 2c: Validate that repairs did not over-formalize or modify customer turns.
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

ORIGINAL_FILE = DATA_DIR / "stage1b_rewritten.json"
REPAIRED_FILE = DATA_DIR / "stage2b_repaired.json"
OUTPUT_FILE = DATA_DIR / "stage2c_validated.json"

PROMPT = """\
Role: Quality validator for ASR-repaired debt-collection dialogues

Task:
Compare the original and repaired dialogues. Flag any repairs that
over-formalize, change customer turns, remove natural fillers, or
alter negotiation logic.

Constraints:
- Only flag actual problems; do not nitpick
- Problem types: over_formalized, customer_modified, filler_removed,
  logic_changed, tone_shifted, span_not_repaired
- If status is "needs_revision", provide exact suggested corrections
- If 0-1 minor issues, status may still be "accepted"

Evaluation criteria:
- Any 客户 turn modified → customer_modified (critical)
- Formal written Chinese replacing spoken style → over_formalized
- Removed 呃/嗯 that was in original → filler_removed

Required output format:
{
  "status": "accepted",
  "issues": []
}
or:
{
  "status": "needs_revision",
  "issues": [
    {
      "turn_index": 8,
      "problem": "over_formalized",
      "current": "...",
      "suggested": "..."
    }
  ]
}
"""


REVISION_PROMPT = """\
Role: Targeted revision applier for ASR-repaired debt-collection dialogues

Task:
Apply the following specific revisions to the dialogue. Only change the
text at the specified turn indices. Do not modify any other turns.

Constraints:
- Only modify turns at the specified indices
- Use the suggested text exactly as provided
- Do not change any other turn
- Preserve all JSON structure

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


def apply_revisions(client, repaired: dict, issues: list[dict], call_id: str) -> dict:
    rep_rec = repaired.get("record", repaired)
    user_data = {
        "record": {
            "call_id": call_id,
            "dialog": rep_rec.get("dialog", []),
        },
        "revisions": [
            {"turn_index": i.get("turn_index"), "new_text": i.get("suggested")}
            for i in issues
            if i.get("suggested")
        ],
    }
    result = call_llm(client, REVISION_PROMPT, user_data)
    return result


def run(records_orig: list[dict], records_repaired: list[dict]) -> list[dict]:
    client = create_client()
    results = []
    for i, (orig, repaired) in enumerate(zip(records_orig, records_repaired)):
        orig_rec = orig.get("record", orig)
        rep_rec = repaired.get("record", repaired)
        call_id = orig_rec.get("call_id", f"record_{i}")
        print(f"  [2c] Validating {i+1}/{len(records_repaired)} (call_id={call_id})...")

        user_data = {
            "call_id": call_id,
            "original_dialog": orig_rec.get("dialog", []),
            "repaired_dialog": rep_rec.get("dialog", []),
        }
        validation = call_llm(client, PROMPT, user_data, thinking_budget=0)

        if validation.get("status") == "needs_revision":
            issues = validation.get("issues", [])
            print(f"    Found {len(issues)} issues, applying revisions via LLM...")
            repaired = apply_revisions(client, repaired, issues, call_id)

            rep_rec_rev = repaired.get("record", repaired)
            reval_data = {
                "call_id": call_id,
                "original_dialog": orig_rec.get("dialog", []),
                "repaired_dialog": rep_rec_rev.get("dialog", []),
            }
            revalidation = call_llm(client, PROMPT, reval_data, thinking_budget=0)
            final_status = revalidation.get("status", validation.get("status", "unknown"))
            final_issues = revalidation.get("issues", issues)
            print(f"    Re-validation: {final_status}")
        else:
            final_status = validation.get("status", "accepted")
            final_issues = validation.get("issues", [])

        result = repaired if isinstance(repaired, dict) else {"record": repaired}
        result["validation"] = {
            "status": final_status,
            "issues": final_issues,
        }
        results.append(result)
    return results


def main(count: int = 0) -> None:
    records_orig = load_json_records(ORIGINAL_FILE)
    records_repaired = load_json_records(REPAIRED_FILE)
    if count > 0:
        records_orig = records_orig[:count]
        records_repaired = records_repaired[:count]
    print(f"[Stage 2c] Validating {len(records_repaired)} records...")
    results = run(records_orig, records_repaired)
    save_json_records(results, OUTPUT_FILE)
    print(f"[Stage 2c] Output saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    main(n)
