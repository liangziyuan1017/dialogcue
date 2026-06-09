"""
round 4: for long 催收员 turns (>100 Chinese chars), determine if missing customer replies
caused prolonged continuous 催收员 speech. If so, split the turn and insert inferred customer turns.
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DATA_FILE = Path(os.environ.get("DATA_FILE", str(BASE_DIR / "output_complete.py")))
OUTPUT_FILE = Path(os.environ.get("OUTPUT_FILE", str(BASE_DIR / "output_polish.py")))

PROMPT = """
You are repairing Chinese debt-collection phone call transcripts where ASR has
failed to capture short customer interjections, producing artificially long
催收员 monologues.

CRITICAL CONTEXT:
Real phone conversations are rapid back-and-forth. In debt collection calls,
the average 催收员 utterance is 20-60 Chinese characters. A 催收员 turn
exceeding 100 characters is ALMOST CERTAINLY missing customer replies that
ASR failed to pick up.

A turn exceeding 200 characters is DEFINITELY missing multiple customer replies.
A turn exceeding 500 characters is missing MANY customer replies.

YOUR DEFAULT STANCE: SPLIT AGGRESSIVELY.
Every long 催收员 turn should be split. Only leave a turn unsplit if it is
truly a single coherent utterance with no natural break points — this is rare
for turns over 100 characters.

SPLIT TRIGGERS — split at EVERY occurrence of these patterns:

1. QUESTION → 催收员 asks a question (吗？/对吧？/好不好？/行不行？/是不是？/多少？)
   → customer answer is missing, ALWAYS split here

2. ACKNOWLEDGMENT → 催收员 says 嗯/对/好的/明白/了解 mid-utterance
   → this is the 催收员 reacting to an unheard customer reply, split BEFORE the acknowledgment

3. TOPIC SHIFT → 催收员 changes subject or negotiation angle
   → customer reaction triggered the shift, split at the shift point

4. INTERRUPTION MARKER → 催收员 says 您听我说/先生/先别急/您先听
   → customer tried to interrupt, split before the marker

6. PERSUASION PIVOT → 催收员 transitions from explaining facts to pressing for commitment
   → customer hesitation or objection is implied, split at the pivot

7. REPETITION → 催收员 repeats or rephrases the same point
   → customer expressed doubt or didn't respond, split at the repetition

8. NAMING → 催收员 addresses customer by name or title mid-utterance (先生/女士/张先生)
   → re-engaging after customer went silent, split before the name

9. CONJUNCTION RESTART → 催收员 starts a new clause with 而且/然后/另外/就是说/就是说哈
   after completing a point → new conversational unit, split

10. SILENCE FILL → 催收员 says 呃/嗯 filler then starts new topic
    → filling silence from missing customer reply, split

SPLITTING RULES:

- Split at EVERY trigger point, not just the most obvious one
- For a 200+ char turn, expect 3-6 splits minimum
- For a 500+ char turn, expect 6-12 splits minimum
- Each 催收员 fragment should be 20-80 Chinese characters ideally
- Split at natural sentence/clause boundaries, never mid-phrase
- Do NOT merge or rewrite the 催收员 text — only split at boundaries

INSERTED CUSTOMER TURN RULES:

- Keep SHORT: 2-15 Chinese characters
- Sound like real phone-call speech, not written text
- Types by context:
  * After question: 嗯/对/不是/我不知道/可能吧
  * After explanation: 嗯/好的/明白/噢
  * After pressure: 我知道/但是/能不能/唉/太难了
  * After threat/warning: 嗯/我知道了/那怎么办
  * After topic shift: 嗯？/什么/然后呢
  * After repetition: 我知道/嗯/对
- Must fit the emotional context of the conversation
- Must NOT contradict what 催收员 says next
- Add "label": "1" to EVERY inserted customer turn

DO NOT:
- Modify any existing 催收员 text
- Add label to original 催收员 turns
- Leave long turns unsplit unless truly no break points exist
- Make inserted customer turns longer than 15 characters
- Insert turns that contradict the following 催收员 text

OUTPUT FORMAT:

Return valid JSON:
{
  "turns": [
    {"role": "催收员", "text": "first fragment"},
    {"role": "客户", "text": "inferred reply", "label": "1"},
    {"role": "催收员", "text": "second fragment"},
    {"role": "客户", "text": "another reply", "label": "1"},
    {"role": "催收员", "text": "remaining fragment"}
  ]
}

If truly no split is needed (very rare for >100 chars):
{
  "turns": [
    {"role": "催收员", "text": "original text unchanged"}
  ]
}

Long 催收员 turn:
"""


def create_client() -> OpenAI:
    return OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")


def count_chinese_chars(text: str) -> int:
    return sum(1 for c in text if '\u4e00' <= c <= '\u9fff')


def repair_json(content: str) -> str:
    import re as _re
    last_complete = _re.rfind(content, '},')
    if last_complete != -1:
        truncated = content[:last_complete + 1]
        if '"turns"' in truncated:
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


def call_llm(client: OpenAI, system_prompt: str, turn_text: str,
             max_tokens: int = 16384) -> dict:
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": turn_text},
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


def split_long_turn(client: OpenAI, text: str, depth: int = 0) -> list[dict]:
    max_depth = 3
    try:
        result = call_llm(client, PROMPT, text, max_tokens=16384)
    except Exception as e:
        print(f"      LLM call failed: {e}")
        return [{"role": "催收员", "text": text}]

    turns = result.get("turns", [])
    if not turns:
        return [{"role": "催收员", "text": text}]

    valid = all(
        t.get("role") in ("催收员", "客户") and t.get("text", "").strip()
        for t in turns
    )
    if not valid:
        print("      Invalid turns structure")
        return [{"role": "催收员", "text": text}]

    expanded = []
    needs_recurse = False
    for t in turns:
        entry = {"role": t["role"], "text": t["text"]}
        if t.get("label") == "1":
            entry["label"] = "1"
            expanded.append(entry)
        elif t["role"] == "催收员" and count_chinese_chars(t["text"]) > 100 and depth < max_depth:
            needs_recurse = True
            print(f"      Recursive split: fragment still {count_chinese_chars(t['text'])} cn chars (depth={depth+1})")
            sub = split_long_turn(client, t["text"], depth + 1)
            expanded.extend(sub)
        else:
            expanded.append(entry)

    return expanded


def process_dialog(client: OpenAI, dialog: list[dict]) -> list[dict]:
    new_dialog = []
    changed = False
    for turn in dialog:
        role = turn.get("role", "")
        text = turn.get("text", "")

        if role == "催收员" and count_chinese_chars(text) > 100:
            cn = count_chinese_chars(text)
            print(f"    Long 催收员 turn ({cn} cn chars), analyzing...")
            expanded = split_long_turn(client, text)

            has_inserted = any(t.get("label") == "1" for t in expanded)
            if has_inserted or len(expanded) > 1:
                inserted_count = sum(1 for t in expanded if t.get("label") == "1")
                print(f"    Split into {len(expanded)} turns (inserted {inserted_count} customer replies)")
                changed = True
                new_dialog.extend(expanded)
            else:
                print("    No split needed")
                new_dialog.append(turn)
        else:
            new_dialog.append(turn)

    return new_dialog, changed


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

        dialog = record["dialog"].get("dialog", record["dialog"]) if isinstance(record["dialog"], dict) else record["dialog"]
        new_dialog, changed = process_dialog(client, dialog)

        if changed:
            if isinstance(record["dialog"], dict):
                new_response = {**record["dialog"], "dialog": new_dialog}
            else:
                new_response = {"dialog": new_dialog}
        else:
            new_response = record["dialog"]

        result = {
            "call_id": record["call_id"],
            "custno": record["custno"],
            "response": new_response,
        }
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
