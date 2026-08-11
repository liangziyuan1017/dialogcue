"""Threshold sweep helpers."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from threshold_calib import (  # noqa: E402
    calibrate_from_collected,
    load_thresholds,
    sweep_abstain_min_prob,
    sweep_binary_threshold,
    thresholds_for_decode,
    write_thresholds,
)


def test_sweep_binary_prefers_separating_threshold():
    # perfect separator at 0.6
    y = [1, 1, 0, 0]
    p = [0.9, 0.8, 0.2, 0.1]
    best = sweep_binary_threshold(y, p)
    assert best["f1"] == 1.0
    assert best["threshold"] <= 0.8


def test_abstain_sweep_returns_fields():
    y = [0, 1, 0]
    probs = [[0.9, 0.1], [0.2, 0.8], [0.6, 0.4]]
    out = sweep_abstain_min_prob(y, probs, min_coverage=0.3)
    assert "min_prob" in out
    assert out["n"] == 3


def test_thresholds_roundtrip(tmp_path):
    schema_heads = type("S", (), {"heads": []})()
    payload = calibrate_from_collected(
        {
            "fact_y": {},
            "fact_p": {},
            "emo_y": [0],
            "emo_probs": [[0.9, 0.1]],
            "will_y": [0],
            "will_probs": [[0.8, 0.2]],
        },
        schema_heads,
        checkpoint="x.pt",
        split="val",
    )
    path = tmp_path / "thresholds.json"
    write_thresholds(path, payload)
    loaded = load_thresholds(path)
    kw = thresholds_for_decode(loaded)
    assert "binary_positive_threshold" in kw
    assert kw["emotion_min_confidence"] >= 0.0
