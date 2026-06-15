import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from llm_client import _get_client
from retry import retry_call

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DATA_FILE = Path(os.environ.get("DATA_FILE", str(BASE_DIR / "matched_data.jsonl")))
OUTPUT_FILE = Path(os.environ.get("OUTPUT_FILE", str(BASE_DIR / "output_2.py")))

PROMPT = """ 
You are editing noisy ASR-transcribed Mandarin phone calls into readable but emotionally authentic spoken dialogue.

Your task is NOT to produce clean prose.

Your task is to preserve:
- emotional pressure,
- hesitation,
- social discomfort,
- negotiation tension,
- pleading,
- fatigue,
- confusion,
- defensiveness,
- and spontaneous spoken rhythm.

The final dialogue should feel like:
a real stressful phone call between two real people.

IMPORTANT:
Emotion in spoken Mandarin is often carried through:
- repetition,
- hesitation,
- restarting sentences,
- filler words,
- incomplete phrasing,
- self-correction,
- trailing thoughts,
- and uneven pacing.

DO NOT over-clean these away.

However:
DO remove obvious ASR corruption and meaningless duplication.

DISTINGUISH BETWEEN:

A) Emotionally meaningful disfluency (KEEP)
Examples:
- “我……我是真的一下子拿不出来。”
- “不是，我的意思是……”
- “唉，我也很痛苦啊。”
- “那、那我下个月怎么办啊？”
- “我不是不还，我是真的现在压力很大。”

B) Meaningless ASR noise (REMOVE or REWRITE)
Examples:
- “就是说就是说就是说……”
- “然后然后然后……”
- broken fragments with no emotional value
- duplicated half-sentences
- malformed interruptions
- random dangling conjunctions

EDITING PRINCIPLES:
1. Preserve emotional cadence over grammatical perfection.
2. Preserve spoken realism over textual cleanliness.
3. Preserve negotiation dynamics over concise wording.
4. Keep the conversation sounding LIVE, not summarized.
5. Keep some natural repetition if it reflects stress or thinking.
6. Keep pauses and hesitations when emotionally meaningful.
7. Avoid flattening emotionally charged speech into efficient sentences.
8. Do not compress emotionally vulnerable turns.

VERY IMPORTANT:
Do NOT rewrite the customer into calm, concise language.

The customer should still sound:
- financially stressed,
- embarrassed,
- anxious,
- trying to negotiate,
- trying to explain themselves while thinking in real time.

The collector should still sound:
- procedural,
- repetitive,
- slightly pressuring,
- professionally restrained,
- but still conversational.

NATURAL SPEECH STYLE:
Use natural Mandarin spoken rhythm:
- “就是……”
- “那个……”
- “唉”
- “嗯”
- “我、我”
- “那、那”
- sentence restarts
- trailing phrases

—but ONLY when they contribute emotional realism.

DO NOT:
- turn the dialogue into polished writing,
- summarize,
- over-compress,
- normalize all hesitations,
- or make everyone sound emotionally flat.

TARGET STYLE:
A professionally cleaned real call transcript with emotional texture preserved.

Output valid JSON only.
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
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = [json.loads(line) for line in f if line.strip()]

    records = []
    for record in data:
        dialog_raw = record.get("dialog", "")
        turns = []
        for seg in re.split(r"[；;]", dialog_raw):
            seg = seg.strip()
            if not seg:
                continue
            m = re.match(r"^(催收员|客户)[：:]\s*(.*)", seg)
            if m:
                turns.append({"role": m.group(1), "text": m.group(2).strip()})
            elif turns:
                turns[-1]["text"] += seg

        for i, t in enumerate(turns):
            t["index"] = i

        records.append({
            "call_id": record.get("call_id", ""),
            "dialog": turns,
            "calldate": record.get("call_date", ""),
            "cust_no": record.get("cust_no", ""),
            "colluserid": record.get("coll_user_id", ""),
        })

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


def call_llm(client: OpenAI, system_prompt: str, dialog: list[dict],max_tokens: int = 16384) -> dict:
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
    repaired = repair_json(content)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError as e:
        print(f"  JSON repair failed: {e}")
        raise


def load_existing_results() -> list[dict]:
    if not OUTPUT_FILE.exists():
        return []
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        code = compile(f.read(), OUTPUT_FILE, "exec")
        namespace = {}
        exec(code, namespace)
        return namespace.get("results", [])


def write_results(results: list[dict]) -> None:
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("results = ")
        f.write(json.dumps(results, ensure_ascii=False, indent=2))
        f.write("\n")


def main() -> None:
    client = create_client()
    records = load_all_records()
    results = load_existing_results()
    existing_call_ids = {r["call_id"] for r in results}

    BATCH_SIZE = 1
    batch = []

    for i, record in enumerate(records):
        if record["call_id"] in existing_call_ids:
            print(f"  Skipping record {i+1}/{len(records)} (call_id={record['call_id']}) - already processed")
            continue
        print(f"  Processing record {i+1}/{len(records)} (call_id={record['call_id']})...")

        def _process():
            llm_response = call_llm(client, PROMPT, record["dialog"])
            return {
                "call_id": record["call_id"],
                "cust_no": record["cust_no"],
                "response": llm_response,
            }

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
