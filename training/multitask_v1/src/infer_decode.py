"""Inference decode policies for multitask_v1 (no training masks at serve time).

Training masks mean "has supervision", not "model confidence".
At inference we always get class distributions; operational reporting uses:

Fact:
  - softmax + argmax
  - treat schema default (usually last value: none/no) as inactive / not reported
  - optional: binary heads require P(positive) >= threshold to fire

Emotion / Willingness:
  - always top-1 + confidence
  - optional abstain if max-prob < min_confidence
"""

from __future__ import annotations

from typing import Any

import torch
import torch.nn.functional as F


def _softmax_probs(logits: torch.Tensor) -> torch.Tensor:
    return F.softmax(logits.float(), dim=-1)


def decode_fact_heads(
    fact_logits: dict[str, torch.Tensor],
    schema,
    *,
    binary_positive_threshold: float = 0.5,
    fact_thresholds_per_head: dict[str, float] | None = None,
    batch_index: int = 0,
) -> dict[str, Any]:
    """
    Returns per-head dict with value/prob/active.
    active=False when prediction is the head default (none/no/…) OR
    (for binary) positive class prob below threshold.
    """
    per_head = fact_thresholds_per_head or {}
    out: dict[str, Any] = {}
    for h in schema.heads:
        logits = fact_logits[h.name][batch_index]
        probs = _softmax_probs(logits)
        pred_i = int(probs.argmax().item())
        value = h.values[pred_i]
        conf = float(probs[pred_i].item())
        default = h.values[-1]
        positive = h.values[0] if len(h.values) >= 1 else default
        thr = float(per_head.get(h.name, binary_positive_threshold))

        if h.type == "binary" or (len(h.values) == 2 and h.values[-1] in ("none", "no")):
            pos_p = float(probs[0].item())
            if value == positive and pos_p >= thr:
                active = True
                value = positive
                conf = pos_p
            elif value != default and conf >= thr:
                active = True
            else:
                active = False
                value = default
                conf = (
                    float(probs[h.values.index(default)].item())
                    if default in h.values
                    else conf
                )
        else:
            active = value != default

        out[h.name] = {
            "value": value,
            "prob": round(conf, 4),
            "active": bool(active),
            "default_value": default,
            "threshold_used": thr if (
                h.type == "binary"
                or (len(h.values) == 2 and h.values[-1] in ("none", "no"))
            ) else None,
            "probs": {v: round(float(probs[i].item()), 4) for i, v in enumerate(h.values)},
            "kind": h.kind,
            "type": h.type,
            "excluded_from_train": h.name == "IdentityProcess",
        }
    return out


def decode_single_label(
    logits: torch.Tensor,
    vocab: list[str],
    *,
    batch_index: int = 0,
    min_confidence: float = 0.0,
) -> dict[str, Any]:
    row = logits[batch_index]
    probs = _softmax_probs(row)
    pred_i = int(probs.argmax().item())
    conf = float(probs[pred_i].item())
    label = vocab[pred_i]
    abstain = conf < float(min_confidence)
    return {
        "label": None if abstain else label,
        "prob": round(conf, 4),
        "abstain": abstain,
        "probs": {lab: round(float(probs[i].item()), 4) for i, lab in enumerate(vocab)},
    }


def decode_multitask_output(
    model_out: dict[str, Any],
    *,
    schema,
    emotion_vocab: list[str],
    willingness_vocab: list[str],
    batch_index: int = 0,
    binary_positive_threshold: float = 0.5,
    fact_thresholds_per_head: dict[str, float] | None = None,
    emotion_min_confidence: float = 0.0,
    willingness_min_confidence: float = 0.0,
) -> dict[str, Any]:
    fact = decode_fact_heads(
        model_out["fact_logits"],
        schema,
        binary_positive_threshold=binary_positive_threshold,
        fact_thresholds_per_head=fact_thresholds_per_head,
        batch_index=batch_index,
    )
    emotion = decode_single_label(
        model_out["emotion_logits"],
        emotion_vocab,
        batch_index=batch_index,
        min_confidence=emotion_min_confidence,
    )
    willingness = decode_single_label(
        model_out["willingness_logits"],
        willingness_vocab,
        batch_index=batch_index,
        min_confidence=willingness_min_confidence,
    )
    active_facts = {k: v for k, v in fact.items() if v.get("active")}
    return {
        "fact": fact,
        "fact_active": active_facts,
        "emotion": emotion,
        "willingness": willingness,
        "policy": {
            "fact_inactive_rule": "predict_default_or_binary_below_threshold",
            "binary_positive_threshold": binary_positive_threshold,
            "fact_thresholds_per_head": fact_thresholds_per_head,
            "emotion_min_confidence": emotion_min_confidence,
            "willingness_min_confidence": willingness_min_confidence,
            "note": (
                "No training mask at inference. "
                "Inactive Fact ≈ schema default (none/no). "
                "Load thresholds.json from val calibration when available."
            ),
        },
    }
