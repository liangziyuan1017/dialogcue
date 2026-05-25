import json
import os
import re
import sys
from pathlib import Path

from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "(basic) data_0520.json"
OUTPUT_FILE = BASE_DIR / "output_2.py"

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

Output JSON only.

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
        data = json.load(f)

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
            "calldate": record.get("calldate", ""),
            "custno": record.get("custno", ""),
            "colluserid": record.get("colluserid", ""),
        })

    print(f"Loaded {len(records)} records")
    return records


def call_llm(client: OpenAI, system_prompt: str, user_data: dict,
             max_tokens: int = 16384) -> dict:
    user_message = json.dumps(user_data, ensure_ascii=False)
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
        result = call_llm(client, PROMPT, {"record": record})
        results.append(result)

    with open(OUTPUT_FILE, "w+", encoding="utf-8") as f:
        f.write("results = ")
        f.write(json.dumps(results, ensure_ascii=False, indent=2))
        f.write("\n")

    print(f"Output written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
