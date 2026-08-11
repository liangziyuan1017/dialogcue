"""Willingness strict metrics."""

from __future__ import annotations

from typing import Any


def _f1(p: float, r: float) -> float:
    if p + r <= 0:
        return 0.0
    return 2 * p * r / (p + r)


def evaluate_willingness(
    y_true: list[str],
    y_pred: list[str],
    vocab: list[str],
) -> dict[str, Any]:
    if len(y_true) != len(y_pred):
        raise ValueError("length mismatch")
    n = len(y_true)
    if n == 0:
        return {
            "n": 0,
            "accuracy": 0.0,
            "macro_f1": 0.0,
            "weighted_f1": 0.0,
        }
    tp = {c: 0 for c in vocab}
    fp = {c: 0 for c in vocab}
    fn = {c: 0 for c in vocab}
    support = {c: 0 for c in vocab}
    ok = 0
    for t, p in zip(y_true, y_pred):
        support[t] = support.get(t, 0) + 1
        if t == p:
            ok += 1
            tp[t] += 1
        else:
            fn[t] += 1
            fp[p] += 1
    f1s = []
    w_num = 0.0
    w_den = 0
    for c in vocab:
        p = tp[c] / (tp[c] + fp[c]) if (tp[c] + fp[c]) else 0.0
        r = tp[c] / (tp[c] + fn[c]) if (tp[c] + fn[c]) else 0.0
        f1 = _f1(p, r)
        f1s.append(f1)
        w_num += f1 * support[c]
        w_den += support[c]
    return {
        "n": n,
        "accuracy": round(ok / n, 4),
        "macro_f1": round(sum(f1s) / len(f1s), 4) if f1s else 0.0,
        "weighted_f1": round(w_num / w_den, 4) if w_den else 0.0,
    }
