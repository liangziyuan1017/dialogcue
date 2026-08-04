"""Encode recent-turn window with Chinese char budget (train/infer shared)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence


@dataclass
class TurnLike:
    turn_id: int
    speaker: str
    text: str


@dataclass
class WindowEncodeResult:
    text: str
    n_turns_selected: int
    char_len: int
    truncated: bool
    turn_ids: list[int]


_SPEAKER = {
    "collector": "collector",
    "customer": "customer",
    "Agent": "collector",
    "Customer": "customer",
}


def _zh_len(s: str) -> int:
    """Count characters (Chinese + others); budget is on this length."""
    return len(s)


def _format_line(turn: TurnLike) -> str:
    sp = _SPEAKER.get(turn.speaker, turn.speaker)
    return f"[{sp}] {turn.text.strip()}"


def encode_recent_window(
    turns: Sequence[Any],
    anchor_index: int,
    *,
    window_turns: int = 5,
    char_budget: int = 250,
) -> WindowEncodeResult:
    """
    Take up to `window_turns` ending at anchor_index (inclusive), then trim
    from the oldest turn until char_budget is met. Always try to keep the
    anchor turn.
    """
    if anchor_index < 0 or anchor_index >= len(turns):
        raise IndexError(f"anchor_index {anchor_index} out of range for {len(turns)} turns")

    start = max(0, anchor_index - window_turns + 1)
    selected = list(turns[start : anchor_index + 1])

    def to_turn(t: Any) -> TurnLike:
        if isinstance(t, TurnLike):
            return t
        return TurnLike(
            turn_id=int(getattr(t, "turn_id", 0)),
            speaker=str(getattr(t, "speaker", "")),
            text=str(getattr(t, "text", "") or ""),
        )

    selected_tl = [to_turn(t) for t in selected]
    truncated = False

    def render(ts: list[TurnLike]) -> str:
        return "\n".join(_format_line(t) for t in ts if t.text.strip())

    text = render(selected_tl)
    # Drop oldest turns while over budget (keep at least last/anchor)
    while _zh_len(text) > char_budget and len(selected_tl) > 1:
        truncated = True
        selected_tl = selected_tl[1:]
        text = render(selected_tl)

    # If single turn still too long, hard-truncate text from the end (keep tail)
    if _zh_len(text) > char_budget:
        truncated = True
        # keep suffix so current utterance end remains
        text = text[-char_budget:]

    return WindowEncodeResult(
        text=text,
        n_turns_selected=len(selected_tl),
        char_len=_zh_len(text),
        truncated=truncated,
        turn_ids=[t.turn_id for t in selected_tl],
    )
