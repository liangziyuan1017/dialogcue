"""Context window contract: 4 turns / 200 chars."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from context import encode_window  # noqa: E402
from context_encode import TurnLike  # noqa: E402


def test_window_respects_turns_and_chars():
    turns = [
        TurnLike(0, "collector", "您好，请问您是张三吗？" + ("详" * 80)),
        TurnLike(1, "customer", "是的。"),
        TurnLike(2, "collector", "您的账单已逾期，需要和您确认还款计划。" + ("细" * 80)),
        TurnLike(3, "customer", "我现在没钱，最近刚失业。"),
        TurnLike(4, "collector", "理解，那我们看看能不能分期。"),
        TurnLike(5, "customer", "可以商量一下。"),
    ]
    r = encode_window(turns, 5, max_turns=4, max_chars=200)
    assert r.n_turns_selected <= 4
    assert r.char_len <= 200
    assert 5 in r.turn_ids


def test_rejects_non_window_strategy():
    turns = [TurnLike(0, "customer", "hi")]
    try:
        encode_window(turns, 0, strategy="full_dialog")
        assert False, "expected ValueError"
    except ValueError as e:
        assert "window_only" in str(e)
