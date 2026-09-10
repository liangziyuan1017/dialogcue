"""
round 2: polish the 催收员's part on its logic, since they replied base on a trained procedures where they are taught what to say in each circumstance in professional ways, we do not want to detect any emotions in them, we could do more logical rewrites.
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from f007_infrastructure.config import get as _cfg
from f007_infrastructure.jsonl_utils import load_jsonl, write_jsonl
from f007_infrastructure.llm_client import _get_client
from f007_infrastructure.retry import retry_call

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = _PROJECT_ROOT / "data" / "data_input"
OUTPUT_DIR = _PROJECT_ROOT / "data" / "data_output"
load_dotenv(_PROJECT_ROOT / ".env")
DATA_FILE = Path(os.environ.get("DATA_FILE", str(OUTPUT_DIR / "output_clean.jsonl")))
OUTPUT_FILE = Path(os.environ.get("OUTPUT_FILE", str(OUTPUT_DIR / "output_logic.jsonl")))

PROMPT = """
You are repairing corrupted ASR transcription in Chinese debt-collection phone call dialogues.

Your task is ONLY to repair utterances spoken by:
- 催收员

IMPORTANT:
This task is NOT proofreading.
This task is NOT summarization.
This task is NOT formal rewriting.

If a phrase is clearly unrecoverable ASR corruption,
DO NOT preserve the original wording.

Instead:
- infer the intended meaning from surrounding dialogue
- reconstruct a natural spoken utterance
- keep the same conversational tone
- keep the same intent
- keep the same emotional pacing

Examples of unrecoverable corruption:
- malformed numbers
- nonsensical word combinations
- impossible sentence fragments
- duplicated ASR artifacts
- broken semantic structure

In these cases:
semantic reconstruction is preferred over literal preservation.

This is:
# conversational ASR semantic repair

Your goal:
Repair corrupted or nonsensical ASR spans so the dialogue becomes logically understandable and naturally spoken.

You MUST preserve:
- spoken-language style
- emotional pacing
- hesitation
- fillers
- interruptions
- repeated words caused by emotion
- colloquial customer-service tone

You MAY aggressively repair:
- corrupted ASR phrases
- malformed numbers
- broken wording
- impossible grammar
- semantically broken spans
- duplicated garbage tokens
- logically inconsistent fragments

Examples of corrupted spans that SHOULD be repaired:
- “如话” → “不是”
- “需帮利交违约金” → “利息和违约金”
- “卡卡卡片” → “卡片”
- “合动卡” → “冻卡”
- “20026000多” → “26000多”

IMPORTANT:
When a span is clearly ASR corruption,
prioritize semantic correctness over literal preservation.

But:
DO NOT over-formalize.
DO NOT rewrite into written Chinese.
DO NOT remove natural conversational rhythm.

GOOD:
“嗯，因为您这个卡片是流通卡嘛，然后这边的话还是建议您先把最低还款还了。”

BAD:
“由于您的卡属于流通卡，因此建议您偿还最低还款额。”

Preserve conversational texture such as:
- “嗯”
- “呃”
- “就是说”
- “嘛”
- “这边的话”
- partial repetition
- emotional pauses

DO NOT modify:
- 客户 utterances
- JSON structure

{"dialog": [
    {
      "role": "催收员",
      "text": "唉，您好，请问是……喂，您好，请问是。"
    },
    {
      "role": "客户",
      "text": "喂。"
    },
    {
      "role": "催收员",
      "text": "请问是张先生吗？"
    }
]}

Transcript:
"""


def create_client() -> OpenAI:
    return _get_client()


def load_all_records() -> list[dict]:
    data = load_jsonl(DATA_FILE)

    records = []
    for item in data:
        entry = {
            "call_id": item.get("call_id", ""),
            "dialog": item.get("response", item),
        }
        if "custInfo" in item:
            entry["custInfo"] = item["custInfo"]
        records.append(entry)

    print(f"Loaded {len(records)} records")
    return records


def repair_json(content: str) -> str:
    import re as _re
    last_complete = _re.rfind(content, '},')
    if last_complete != -1:
        truncated = content[:last_complete + 1]
        if '"dialog"' in truncated:
            depth = 0
            in_str = False
            escape = False
            for ch in truncated:
                if escape:
                    escape = False
                    continue
                if ch == '\\':
                    escape = True
                    continue
                if ch == '"' and not escape:
                    in_str = not in_str
                    continue
                if in_str:
                    continue
                if ch in '{[':
                    depth += 1
                elif ch in '}]':
                    depth -= 1
            if in_str:
                truncated += '"'
            while depth > 0:
                truncated += ']}' if depth >= 2 else '}'
                depth -= 2 if depth >= 2 else 1
            return truncated
    depth = 0
    in_str = False
    escape = False
    for ch in content:
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"' and not escape:
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in '{[':
            depth += 1
        elif ch in '}]':
            depth -= 1
    if in_str:
        content += '"'
    while depth > 0:
        content += '}'
        depth -= 1
    return content


def call_llm(client: OpenAI, system_prompt: str, dialog: list[dict],
             max_tokens: int = _cfg("llm.max_tokens", 16384)) -> dict:
    user_message = json.dumps(dialog, ensure_ascii=False)
    response = client.chat.completions.create(
        model=_cfg("llm.model", "deepseek-chat"),
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_message},
        ],
        temperature=_cfg("llm.temperature", 0.1),
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    if response.choices[0].finish_reason == "length":
        print("  Warning: response truncated")
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    print("  Attempting to fix truncated JSON...")
    repaired = repair_json(content)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError as e:
        print(f"  JSON repair failed: {e}")
        raise


def load_existing_results() -> list[dict]:
    if not OUTPUT_FILE.exists():
        return []
    return load_jsonl(OUTPUT_FILE)


def write_results(results: list[dict]) -> None:
    write_jsonl(OUTPUT_FILE, results)


def main() -> None:
    client = create_client()
    records = load_all_records()
    results = load_existing_results()
    existing_call_ids = {r["call_id"] for r in results}

    BATCH_SIZE = _cfg("batch_size.data_cleaning", 1)
    batch = []

    for i, record in enumerate(records):
        if record["call_id"] in existing_call_ids:
            print(f"  Skipping record {i+1}/{len(records)} (call_id={record['call_id']}) - already processed")
            continue
        print(f"  Processing record {i+1}/{len(records)} (call_id={record['call_id']})...")
        def _process():
            llm_response = call_llm(client, PROMPT, record["dialog"])
            out = {
                "call_id": record["call_id"],
                "response": llm_response,
            }
            if "custInfo" in record:
                out["custInfo"] = record["custInfo"]
            return out

        def _on_fail(exc):
            print(f"  SKIPPED record {i+1}/{len(records)} (call_id={record['call_id']}) after 3 retries: {exc}")
            return None

        result = retry_call(_process, on_fail=_on_fail)
        if result is None:
            continue
        results.append(result)
        batch.append(result)

        if len(batch) >= BATCH_SIZE:
            write_results(results)
            print(f"  Checkpoint: {len(results)} results written to {OUTPUT_FILE}")
            batch.clear()

    if batch:
        write_results(results)
        print(f"  Final: {len(results)} results written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
