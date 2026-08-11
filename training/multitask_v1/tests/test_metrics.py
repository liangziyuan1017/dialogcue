"""Emotion adjacent metrics + willingness metrics."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from labels import emotion_labels, willingness_labels  # noqa: E402
from metrics_emotion import evaluate_emotion  # noqa: E402
from metrics_willingness import evaluate_willingness  # noqa: E402


def test_adjacent_credits_neighbor():
    vocab = emotion_labels()
    # gold complaint, pred irritation → strict wrong, adj correct
    y_true = ["complaint", "distress", "engagement"]
    y_pred = ["irritation", "distress", "negotiation"]
    m = evaluate_emotion(y_true, y_pred, vocab, eval_set="all_rule")
    assert m["n"] == 3
    assert m["strict_accuracy"] == round(1 / 3, 4)
    assert m["adj_accuracy"] >= m["strict_accuracy"]
    # irritation~complaint and negotiation~engagement are adjacent
    assert m["adj_accuracy"] == 1.0
    assert m["emotion_confusion_graph"]


def test_willingness_metrics():
    vocab = willingness_labels()
    m = evaluate_willingness(
        ["resistant", "strong", "weak"],
        ["resistant", "negotiating", "weak"],
        vocab,
    )
    assert m["n"] == 3
    assert m["accuracy"] == round(2 / 3, 4)
