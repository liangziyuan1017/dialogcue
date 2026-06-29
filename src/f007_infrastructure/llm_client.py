import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from f007_infrastructure.config import get as _cfg

load_dotenv(Path(__file__).resolve().parent / ".env")


def _get_client():
    return OpenAI(api_key=os.environ.get("DEEPSEEK_API_KEY"), base_url=_cfg("llm.api_base", "https://api.deepseek.com"))


def call_deepseek(prompt: str, temperature: float = None) -> str:
    if temperature is None:
        temperature = _cfg("llm.temperature", 0.1)
    client = _get_client()
    resp = client.chat.completions.create(
        model=_cfg("llm.model", "deepseek-chat"),
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return resp.choices[0].message.content


def _strip_json(text: str) -> str:
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    return text.strip()


def call_deepseek_json(prompt: str, temperature: float = None) -> dict:
    if temperature is None:
        temperature = _cfg("llm.temperature", 0.1)
    text = call_deepseek(prompt, temperature)
    return json.loads(_strip_json(text))
