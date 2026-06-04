"""
round 2: polish the 催收员's part on its logic, since they replied base on a trained procedures where they are taught what to say in each circumstance in professional ways, we do not want to detect any emotions in them, we could do more logical rewrites.
"""
import json
import os
import sys
from pathlib import Path

from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "output_2.py"
OUTPUT_FILE = BASE_DIR / "output_logic.py"

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

Output valid JSON only.

Transcript:
"""


def create_client() -> OpenAI:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("Error: DEEPSEEK_API_KEY environment variable is not set.")
        sys.exit(1)
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")


def load_all_records() -> list[dict]:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        code = compile(f.read(), DATA_FILE, "exec")
        namespace = {}
        exec(code, namespace)
        data = namespace.get("results", [])

    records = []
    for item in data:
        records.append({
            "call_id": item.get("call_id", ""),
            "dialog": item.get("response", item),
            "custno": item.get("custno", ""),
        })

    print(f"Loaded {len(records)} records")
    return records


def call_llm(client: OpenAI, system_prompt: str, dialog: list[dict],
             max_tokens: int = 16384) -> dict:
    user_message = json.dumps(dialog, ensure_ascii=False)
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,
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
    if content.rstrip().endswith("}"):
        pass
    else:
        depth = 0
        in_str = False
        escape = False
        for i, ch in enumerate(content):
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
            content = content + '"'
        while depth > 0:
            content = content + '}'
            depth -= 1

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"  JSON repair failed: {e}")
        raise


def main() -> None:
    client = create_client()
    records = load_all_records()

    results = []
    for i, record in enumerate(records):
        print(f"  Processing record {i+1}/{len(records)} (call_id={record['call_id']})...")
        llm_response = call_llm(client, PROMPT, record["dialog"])
        results.append({
            "call_id": record["call_id"],
            "custno": record["custno"],
            "response": llm_response,
        })

    with open(OUTPUT_FILE, "w+", encoding="utf-8") as f:
        f.write("results = ")
        f.write(json.dumps(results, ensure_ascii=False, indent=2))
        f.write("\n")

    print(f"Output written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
