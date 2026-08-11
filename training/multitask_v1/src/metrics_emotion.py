"""Emotion metrics: strict + adjacent (eval only; no train effect)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from labels import adjacent_pair_set, clusters_from_cfg, load_adjacent_config


def _f1(p: float, r: float) -> float:
    if p + r <= 0:
        return 0.0
    return 2 * p * r / (p + r)


def _prf_from_counts(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    return p, r, _f1(p, r)


def _is_adjacent(
    true_l: str,
    pred_l: str,
    pairs: frozenset[frozenset[str]],
) -> bool:
    if true_l == pred_l:
        return True
    return frozenset({true_l, pred_l}) in pairs


def evaluate_emotion(
    y_true: list[str],
    y_pred: list[str],
    vocab: list[str],
    *,
    eval_set: str = "all_rule",
    adjacent_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Strict metrics are primary for v1 decisions.
    Adjacent metrics are reported for interpretability / v1.1 baseline.
    """
    if len(y_true) != len(y_pred):
        raise ValueError("y_true/y_pred length mismatch")
    cfg = adjacent_cfg or load_adjacent_config()
    pairs = adjacent_pair_set(cfg, eval_set=eval_set)
    clusters = clusters_from_cfg(cfg)

    n = len(y_true)
    if n == 0:
        return {
            "n": 0,
            "strict_accuracy": 0.0,
            "strict_macro_f1": 0.0,
            "strict_weighted_f1": 0.0,
            "adj_accuracy": 0.0,
            "adj_macro_f1": 0.0,
            "cluster_accuracy": 0.0,
            "emotion_adjacent_eval_set": eval_set,
            "confusion": {},
            "emotion_confusion_graph": [],
        }

    strict_ok = 0
    adj_ok = 0
    cluster_ok = 0
    conf: Counter[tuple[str, str]] = Counter()

    def cluster_of(lab: str) -> str | None:
        for name, members in clusters.items():
            if lab in members:
                return name
        return None

    # per-class for strict
    tp = {c: 0 for c in vocab}
    fp = {c: 0 for c in vocab}
    fn = {c: 0 for c in vocab}
    support = {c: 0 for c in vocab}

    # adjacent soft credit: treat adjacent pred as TP for both gold and pred? 
    # For adj_macro_f1 we use: correct if exact OR adjacent pair.
    # Per-class: count as TP for gold class when pred exact or adjacent; else FN.
    # FP: pred class when not exact and not adjacent to gold.
    adj_tp = {c: 0 for c in vocab}
    adj_fp = {c: 0 for c in vocab}
    adj_fn = {c: 0 for c in vocab}

    for t, p in zip(y_true, y_pred):
        conf[(t, p)] += 1
        support[t] = support.get(t, 0) + 1
        if t == p:
            strict_ok += 1
            tp[t] = tp.get(t, 0) + 1
        else:
            fn[t] = fn.get(t, 0) + 1
            fp[p] = fp.get(p, 0) + 1

        if _is_adjacent(t, p, pairs):
            adj_ok += 1
            adj_tp[t] = adj_tp.get(t, 0) + 1
        else:
            adj_fn[t] = adj_fn.get(t, 0) + 1
            adj_fp[p] = adj_fp.get(p, 0) + 1

        ct, cp = cluster_of(t), cluster_of(p)
        if ct is not None and ct == cp:
            cluster_ok += 1

    strict_f1s = []
    weighted_num = 0.0
    weighted_den = 0
    for c in vocab:
        _, _, f1 = _prf_from_counts(tp.get(c, 0), fp.get(c, 0), fn.get(c, 0))
        strict_f1s.append(f1)
        s = support.get(c, 0)
        weighted_num += f1 * s
        weighted_den += s

    adj_f1s = []
    for c in vocab:
        _, _, f1 = _prf_from_counts(adj_tp.get(c, 0), adj_fp.get(c, 0), adj_fn.get(c, 0))
        adj_f1s.append(f1)

    graph = [
        {"gold": a, "pred": b, "count": n_}
        for (a, b), n_ in conf.most_common(30)
        if a != b
    ]

    return {
        "n": n,
        "strict_accuracy": round(strict_ok / n, 4),
        "strict_macro_f1": round(sum(strict_f1s) / len(strict_f1s), 4) if strict_f1s else 0.0,
        "strict_weighted_f1": round(weighted_num / weighted_den, 4) if weighted_den else 0.0,
        "adj_accuracy": round(adj_ok / n, 4),
        "adj_macro_f1": round(sum(adj_f1s) / len(adj_f1s), 4) if adj_f1s else 0.0,
        "cluster_accuracy": round(cluster_ok / n, 4),
        "emotion_adjacent_eval_set": eval_set,
        "confusion": {f"{a}->{b}": n_ for (a, b), n_ in conf.items()},
        "emotion_confusion_graph": graph,
        "n_adjacent_pairs": len(pairs),
    }
