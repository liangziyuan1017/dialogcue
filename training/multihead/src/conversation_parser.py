"""Load conversations from output_rewarded*.py (vendored; no training/src)."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


ROLE_TO_SPEAKER = {
    "客户": "customer",
    "催收员": "collector",
}


@dataclass
class Turn:
    turn_id: int
    speaker: str
    text: str
    raw_state: dict | None = None
    raw_role: str = ""


@dataclass
class Conversation:
    conversation_id: str
    turns: list[Turn]
    reward: int | None = None
    metadata: dict = field(default_factory=dict)


def _load_py_results(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    text = text.replace(": null", ": None")
    text = text.replace(": true", ": True")
    text = text.replace(": false", ": False")
    tree = ast.parse(text, filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id == "results":
                return ast.literal_eval(node.value)
    raise ValueError(f"No 'results' assignment found in {path}")


def _parse_turn(raw: dict) -> Turn:
    role = raw.get("role", "")
    speaker = ROLE_TO_SPEAKER.get(role, role)
    return Turn(
        turn_id=raw.get("turn_index", 0),
        speaker=speaker,
        text=raw.get("text", ""),
        raw_state=raw.get("state"),
        raw_role=role,
    )


def load_conversations(path: str | Path) -> list[Conversation]:
    path = Path(path)
    records = _load_py_results(path)
    conversations = []
    for record in records:
        turns = [_parse_turn(t) for t in record.get("turns_annotated", [])]
        conversations.append(
            Conversation(
                conversation_id=record.get("call_id", ""),
                turns=turns,
                reward=record.get("reward"),
                metadata={
                    "custno": record.get("custno"),
                    "call_date": record.get("call_date"),
                    "mob_typ": record.get("mob_typ"),
                },
            )
        )
    return conversations
