"""Window-only context encode — contract: max_turns=4, max_chars=200.

Uses local context_encode.py (vendored). Does not runtime-import multihead.
"""

from __future__ import annotations

from typing import Any, Sequence

from context_encode import encode_recent_window

DEFAULT_MAX_TURNS = 4
DEFAULT_MAX_CHARS = 200
DEFAULT_STRATEGY = "window_only"


def encode_window(
    turns: Sequence[Any],
    anchor_index: int,
    *,
    max_turns: int = DEFAULT_MAX_TURNS,
    max_chars: int = DEFAULT_MAX_CHARS,
    strategy: str = DEFAULT_STRATEGY,
):
    if strategy != "window_only":
        raise ValueError(f"unsupported context strategy: {strategy!r} (v1 freezes window_only)")
    return encode_recent_window(
        turns,
        anchor_index,
        window_turns=int(max_turns),
        char_budget=int(max_chars),
    )
