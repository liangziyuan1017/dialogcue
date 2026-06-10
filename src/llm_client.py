import json
import os
from openai import OpenAI


def _get_client():
    return OpenAI(api_key=os.environ.get("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")


def call_deepseek(prompt: str, temperature: float = 0.1) -> str:
    client = _get_client()
    resp = client.chat.completions.create(
        model="deepseek-chat",
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


def call_deepseek_json(prompt: str, temperature: float = 0.1) -> dict:
    text = call_deepseek(prompt, temperature)
    return json.loads(_strip_json(text))
