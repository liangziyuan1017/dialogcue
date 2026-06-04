import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

from openai import OpenAI

CALL_DELAY = 0.5

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
MODEL = "qwen3-30b-a3b-2507"


def load_env() -> None:
    env_path = PROJECT_DIR / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


def create_client() -> OpenAI:
    load_env()
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        print("Error: DASHSCOPE_API_KEY not set in .env or environment.")
        sys.exit(1)
    return OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )


def repair_json(content: str) -> str:
    if content.rstrip().endswith("}"):
        return content
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
        content = content + '"'
    while depth > 0:
        content = content + '}'
        depth -= 1
    return content


def strip_thinking(content: str) -> str:
    return re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()


def call_llm(
    client: OpenAI,
    system_prompt: str,
    user_data: dict,
    max_tokens: int = 16384,
    thinking_budget: Optional[int] = None,
    temperature: float = 0.1,
) -> dict:
    user_message = json.dumps(user_data, ensure_ascii=False)
    kwargs = dict(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_message},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    if thinking_budget is not None:
        kwargs["extra_body"] = {"thinking_budget": thinking_budget}

    content = _do_api_call(client, kwargs)

    content = strip_thinking(content)

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    print("  Attempting to repair truncated JSON...")
    content = repair_json(content)
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"  JSON repair failed: {e}")
        raise


def _do_api_call(client: OpenAI, kwargs: dict) -> str:
    try:
        response = client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        if response.choices[0].finish_reason == "length":
            print("  Warning: response truncated")
        time.sleep(CALL_DELAY)
        return content
    except Exception as e:
        if "response_format" in str(e).lower() or "json_object" in str(e).lower():
            print("  response_format not supported, retrying without it...")
            fallback_kwargs = {k: v for k, v in kwargs.items() if k != "response_format"}
            fallback_kwargs["messages"][-1]["content"] += (
                "\n\nOutput valid JSON only. No markdown fences."
            )
            response = client.chat.completions.create(**fallback_kwargs)
            content = response.choices[0].message.content
            if response.choices[0].finish_reason == "length":
                print("  Warning: response truncated")
            time.sleep(CALL_DELAY)
            return content
        raise


def load_source_records(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    if path.suffix == ".json":
        data = json.loads(raw)
    else:
        namespace: dict = {}
        exec(compile(raw, path, "exec"), namespace)
        data = namespace.get("results", [])
    records = []
    for item in data:
        record = item.get("record", item)
        records.append(record)
    return records


def load_json_records(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json_records(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
        f.write("\n")


def parse_dialog_turns(dialog_raw: str) -> list[dict]:
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
    return turns
