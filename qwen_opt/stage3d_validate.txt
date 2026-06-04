"""
Stage 3d: Validate dialogue coherence — check logic, emotion, turn alternation, facts.
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

ORIGINAL_FILE = DATA_DIR / "stage2c_validated.json"
RECONSTRUCTED_FILE = DATA_DIR / "stage3c_cleaned.json"
OUTPUT_FILE = DATA_DIR / "stage3d_final.json"

PROMPT = """\
Role: Dialogue coherence validator for Chinese debt-collection call transcripts

Task:
Compare original and reconstructed dialogues. Verify that:
1. Negotiation logic is preserved (amounts, terms, outcomes)
2. Emotional flow is continuous (no sudden tone shifts)
3. Turn alternation is natural (no long monologues without response)
4. No factual changes to amounts, dates, or legal terms
5. Inserted turns (label="1") are plausible

Constraints:
- Only flag genuine coherence problems
- Problem types: logic_broken, emotion_discontinuity, monologue_run,
  fact_changed, implausible_insert, missing_context
- If all checks pass, status = "accepted"
- If minor issues, status = "accepted" with issues noted
- If critical issues (fact_changed, logic_broken), status = "needs_revision"

Evaluation criteria:
- Any repayment amount changed → fact_changed (critical)
- 5+ consecutive same-speaker turns → monologue_run
- Customer suddenly calm after expressing distress → emotion_discontinuity

Required output format:
{
  "status": "accepted",
  "metrics": {
    "turn_count_original": 28,
    "turn_count_reconstructed": 32,
    "inserted_turns": 4,
    "deleted_turns": 0,
    "merged_groups": 2
  },
  "issues": []
}
or:
{
  "status": "needs_revision",
  "metrics": {...},
  "issues": [
    {"type": "fact_changed", "turn_index": 8, "description": "amount changed from 26000 to 28000"}
  ]
}
"""


FIX_PROMPT = """\
Role: Targeted coherence fixer for Chinese debt-collection call transcripts

Task:
Apply the following specific fixes to the reconstructed dialogue.
Only change the text at the specified turn indices. Do not modify any other turns.

Constraints:
- Only modify turns at the specified indices
- Use the suggested text exactly as provided
- Do not change any other turn
- Preserve all JSON structure and label fields

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


def apply_fixes(client, recon_rec: dict, issues: list[dict], call_id: str) -> dict:
    user_data = {
        "record": {
            "call_id": call_id,
            "dialog": recon_rec.get("dialog", []),
        },
        "fixes": [
            {"turn_index": i.get("turn_index"), "new_text": i.get("suggested", i.get("description", ""))}
            for i in issues
        ],
    }
    return call_llm(client, FIX_PROMPT, user_data)


def run(records_orig: list[dict], records_recon: list[dict]) -> list[dict]:
    client = create_client()
    results = []
    for i, (orig, recon) in enumerate(zip(records_orig, records_recon)):
        orig_rec = orig.get("record", orig)
        recon_rec = recon.get("record", recon)
        call_id = orig_rec.get("call_id", f"record_{i}")
        print(f"  [3d] Validating coherence {i+1}/{len(records_recon)} (call_id={call_id})...")

        user_data = {
            "call_id": call_id,
            "original_dialog": orig_rec.get("dialog", []),
            "reconstructed_dialog": recon_rec.get("dialog", []),
        }
        validation = call_llm(client, PROMPT, user_data, thinking_budget=0)

        if validation.get("status") == "needs_revision":
            issues = validation.get("issues", [])
            print(f"    Found {len(issues)} coherence issues, applying fixes via LLM...")
            fixed = apply_fixes(client, recon_rec, issues, call_id)
            recon_rec = fixed.get("record", fixed)

            reval_data = {
                "call_id": call_id,
                "original_dialog": orig_rec.get("dialog", []),
                "reconstructed_dialog": recon_rec.get("dialog", []),
            }
            revalidation = call_llm(client, PROMPT, reval_data, thinking_budget=0)
            final_status = revalidation.get("status", validation.get("status", "unknown"))
            final_metrics = revalidation.get("metrics", validation.get("metrics", {}))
            final_issues = revalidation.get("issues", issues)
            print(f"    Re-validation: {final_status}")
        else:
            final_status = validation.get("status", "accepted")
            final_metrics = validation.get("metrics", {})
            final_issues = validation.get("issues", [])

        result = recon_rec.copy() if isinstance(recon_rec, dict) else recon_rec
        result["validation"] = {
            "status": final_status,
            "metrics": final_metrics,
            "issues": final_issues,
        }
        results.append(result)
    return results


def main(count: int = 0) -> None:
    records_orig = load_json_records(ORIGINAL_FILE)
    records_recon = load_json_records(RECONSTRUCTED_FILE)
    if count > 0:
        records_orig = records_orig[:count]
        records_recon = records_recon[:count]
    print(f"[Stage 3d] Validating coherence of {len(records_recon)} records...")
    results = run(records_orig, records_recon)
    save_json_records(results, OUTPUT_FILE)
    print(f"[Stage 3d] Output saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    main(n)
