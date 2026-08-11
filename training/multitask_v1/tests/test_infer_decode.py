"""Decode policy unit tests (inference without training masks)."""

from __future__ import annotations

import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from infer_decode import decode_fact_heads, decode_multitask_output  # noqa: E402
from labels import emotion_labels, willingness_labels  # noqa: E402
from paths import load_fact_schema  # noqa: E402


def test_fact_default_is_inactive():
    schema = load_fact_schema()
    # craft logits: every head strongly prefers last (default) value
    fact_logits = {}
    for h in schema.heads:
        logits = torch.full((1, h.n_classes), -5.0)
        logits[0, -1] = 5.0
        fact_logits[h.name] = logits
    decoded = decode_fact_heads(fact_logits, schema, binary_positive_threshold=0.5)
    assert all(not v["active"] for v in decoded.values())


def test_fact_positive_fires_when_confident():
    schema = load_fact_schema()
    h = schema.head_by_name()["Income"]  # unavailable, none
    logits = {name: torch.full((1, hh.n_classes), -5.0) for name, hh in schema.head_by_name().items()}
    for name, hh in schema.head_by_name().items():
        logits[name][0, -1] = 5.0  # default
    logits["Income"] = torch.tensor([[5.0, -5.0]])  # unavailable
    decoded = decode_fact_heads(logits, schema, binary_positive_threshold=0.5)
    assert decoded["Income"]["active"] is True
    assert decoded["Income"]["value"] == "unavailable"


def test_multitask_bundle_decode():
    schema = load_fact_schema()
    emo = emotion_labels()
    will = willingness_labels()
    fact_logits = {
        h.name: torch.zeros(1, h.n_classes) for h in schema.heads
    }
    out = {
        "fact_logits": fact_logits,
        "emotion_logits": torch.zeros(1, len(emo)),
        "willingness_logits": torch.zeros(1, len(will)),
    }
    # peak emotion on complaint
    out["emotion_logits"][0, emo.index("complaint")] = 3.0
    out["willingness_logits"][0, will.index("strong")] = 3.0
    decoded = decode_multitask_output(
        out,
        schema=schema,
        emotion_vocab=emo,
        willingness_vocab=will,
    )
    assert decoded["emotion"]["label"] == "complaint"
    assert decoded["willingness"]["label"] == "strong"
    assert "policy" in decoded
