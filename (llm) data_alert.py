"""
Check every "text" field in dialog turns for potential ASR transcription errors.
Add "alert" field only when errors are found.
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DATA_FILE = Path(os.environ.get("DATA_FILE", str(BASE_DIR / "output_polish.py")))
OUTPUT_FILE = Path(os.environ.get("OUTPUT_FILE", str(BASE_DIR / "output_alert.py")))

PROMPT = """
You are auditing Chinese debt-collection phone call transcripts for ASR (speech-to-text) transcription errors.

For each numbered turn below, check the text for these types of ASR errors:

1. MIXED NUMBER FORMATS: Arabic digits mixed with Chinese number words in ways that
   don't match spoken language. Examples:
   - "30000几" should be "三万几" (nobody says "三零零零零几" out loud)
   - "三、34000" is broken — spoken would be "三万几，三万四"
   - "20026000多" is garbled — likely "26000多" or "20000多"
   - "22000多" when context says "2000多" (extra digit from ASR)

2. GARBLED NUMBERS: Numbers that are clearly corrupted by ASR:
   - "20000万6000" → should be "26000" or "20000多"
   - "462块6毛一" when context says "26462" → digit dropped
   - "107476" when followed by "157010.66" — check if sum makes sense
   - "121999" — check if this matches other mentions of the same amount

3. WORD-LEVEL ASR ERRORS: Words that are phonetically similar but wrong:
   - "如话" → "不是" or "如果"
   - "需帮利交" → "利息和"
   - "合动卡" → "冻卡" or "核冻卡"
   - "能够办理" as standalone fragment → likely truncated
   - "再钱话现在的话出后" → garbled, needs repair
   - "后面话" → fragment, likely "好的" or similar
   - "到了" as standalone → likely truncated fragment
   - "要" / "谢" / "好没" / "为该理说" → single-char or garbled fragments
   - "呃这样的个方可抵消时哈" → garbled ASR
   - "做做完天" → "做完" or "昨天"
   - "检系统" → "系统"
   - "合合动卡" → "冻卡"
   - "利求" → "利息"
   - "高网" → "高昂"
   - "续续" → "后续"
   - "量" → "两" (in number context like "6000量" → "6000两")
   - "调子上不调纸账单不用" → garbled
   - "接" as standalone → likely truncated
   - "号好" → likely "好" or "嗯好"

4. SEMANTIC INCONSISTENCIES: Numbers or amounts that contradict nearby context:
   - "利息2000多" in one turn but "2200多" in another for the same thing
   - "总欠款61000多" vs "121999" — check if these refer to different things

5. TRUNCATED FRAGMENTS: Very short turns (1-3 chars) that are likely ASR fragments:
   - "要", "谢", "好没", "接", "到了", "号好"
   These are not errors per se but are likely incomplete captures.

RULES:
- Only flag REAL errors, not stylistic choices
- Hesitations like "嗯", "呃", "唉" are NOT errors
- Fillers like "就是说", "然后" are NOT errors
- Emotional repetition like "对对对", "好好好" is NOT an error
- Partial self-corrections like "我、我" are NOT errors
- Natural spoken numbers like "26000多", "2000多" are NOT errors
- "块X毛Y" format is NOT an error (it's natural spoken Chinese)
- <PERSON> placeholders are NOT errors

OUTPUT FORMAT:
Return a JSON object. Keys are the turn numbers (as strings).
Values are the alert description explaining what's wrong.
Only include turns that HAVE errors. If a turn is fine, omit it.

Example output:
{
  "3": "30000几 should be 三万几 — mixed Arabic/Chinese number format not matching spoken language",
  "7": "三、34000块钱 is garbled — spoken form would be 三万几，三万四",
  "12": "20026000多 is garbled number, likely 26000多 or 20000多"
}

If no errors found in any turn, return: {}

Turns to check:
"""


def create_client() -> OpenAI:
    return OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")


def repair_json(content: str) -> str:
    import re as _re
    try:
        json.loads(content)
        return content
    except json.JSONDecodeError:
        pass
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


def call_llm(client: OpenAI, system_prompt: str, user_message: str,
             max_tokens: int = 8192) -> dict:
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
    repaired = repair_json(content)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError as e:
        print(f"  JSON repair failed: {e}")
        raise


def load_results() -> list[dict]:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        code = compile(f.read(), DATA_FILE, "exec")
        namespace = {}
        exec(code, namespace)
        return namespace.get("results", [])


def write_results(results: list[dict]) -> None:
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("results = ")
        f.write(json.dumps(results, ensure_ascii=False, indent=2))
        f.write("\n")


def check_dialog(client: OpenAI, dialog: list[dict]) -> dict:
    numbered = []
    for i, t in enumerate(dialog):
        numbered.append(f"{i+1}. [{t['role']}] {t['text']}")
    user_message = "\n".join(numbered)
    return call_llm(client, PROMPT, user_message)


def main() -> None:
    client = create_client()
    results = load_results()

    total_alerts = 0
    for i, record in enumerate(results):
        call_id = record["call_id"]
        dialog = record["response"]["dialog"]
        print(f"  Checking record {i+1}/{len(results)} (call_id={call_id}, {len(dialog)} turns)...")

        try:
            alerts = check_dialog(client, dialog)
        except Exception as e:
            print(f"    LLM call failed: {e}, skipping")
            continue

        count = 0
        for key, alert_text in alerts.items():
            idx = int(key) - 1
            if 0 <= idx < len(dialog):
                dialog[idx]["alert"] = alert_text
                count += 1

        if count:
            print(f"    Found {count} alerts")
        total_alerts += count

    write_results(results)
    print(f"\nDone. Total alerts: {total_alerts}")


if __name__ == "__main__":
    main()
