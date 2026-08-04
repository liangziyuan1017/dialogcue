"""Per-head evaluation metrics for state multihead (evidence-only)."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from schema_loader import MultiheadSchema


def _f1(p: float, r: float) -> float:
    if p + r <= 0:
        return 0.0
    return 2 * p * r / (p + r)


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    return p, r, _f1(p, r)


def evaluate_predictions(
    schema: MultiheadSchema,
    y_true: dict[str, list[str]],
    y_pred: dict[str, list[str]],
    *,
    head_mask_rows: dict[str, list[int]] | None = None,
) -> dict[str, Any]:
    """
    y_true/y_pred: head -> list of value strings (per-head lengths may differ).
    Only pass evidence-supervised rows (caller filters unknown/mask=0).
    head_mask_rows: unused legacy hook (filtering is caller's job).
    """
    del head_mask_rows  # evidence filtering done upstream
    per_head: dict[str, Any] = {}
    macro_f1s: list[float] = []
    weighted_num = 0.0
    weighted_den = 0.0

    for h in schema.heads:
        truths = list(y_true.get(h.name) or [])
        preds = list(y_pred.get(h.name) or [])
        if len(truths) != len(preds):
            raise ValueError(
                f"{h.name}: y_true len {len(truths)} != y_pred len {len(preds)}"
            )
        labels = list(h.values)
        class_scores = {}
        f1s = []
        support_sum = 0
        for lab in labels:
            tp = fp = fn = 0
            for t, p in zip(truths, preds):
                if t == lab and p == lab:
                    tp += 1
                elif p == lab and t != lab:
                    fp += 1
                elif t == lab and p != lab:
                    fn += 1
            prec, rec, f1 = _prf(tp, fp, fn)
            support = sum(1 for t in truths if t == lab)
            class_scores[lab] = {
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1": round(f1, 4),
                "support": support,
                "tp": tp,
                "fp": fp,
                "fn": fn,
            }
            f1s.append(f1)
            support_sum += support

        default = h.values[-1]
        pos_labs = [v for v in labels if v != default]
        tp = fp = fn = 0
        for lab in pos_labs:
            for t, p in zip(truths, preds):
                if t == lab and p == lab:
                    tp += 1
                elif p == lab and t != lab:
                    fp += 1
                elif t == lab and p != lab:
                    fn += 1
        pos_p, pos_r, pos_f1 = _prf(tp, fp, fn)

        macro_f1 = sum(f1s) / len(f1s) if f1s else 0.0
        conf: Counter = Counter()
        for t, p in zip(truths, preds):
            if t != p:
                conf[f"{t}→{p}"] += 1

        n_h = len(truths)
        per_head[h.name] = {
            "kind": h.kind,
            "macro_f1": round(macro_f1, 4),
            "positive_f1": round(pos_f1, 4),
            "positive_precision": round(pos_p, 4),
            "positive_recall": round(pos_r, 4),
            "accuracy": round(
                sum(1 for t, p in zip(truths, preds) if t == p) / max(n_h, 1), 4
            ),
            "per_class": class_scores,
            "confusion_top": dict(conf.most_common(12)),
            "support": n_h,
        }
        if n_h > 0:
            macro_f1s.append(macro_f1)
            weighted_num += macro_f1 * max(support_sum, 1)
            weighted_den += max(support_sum, 1)

    overall_macro = sum(macro_f1s) / len(macro_f1s) if macro_f1s else 0.0
    overall_weighted = weighted_num / weighted_den if weighted_den else 0.0

    by_kind: dict[str, list[float]] = defaultdict(list)
    for h in schema.heads:
        if per_head[h.name]["support"] > 0:
            by_kind[h.kind].append(per_head[h.name]["macro_f1"])

    return {
        "n_samples_scored_note": "per-head support; lengths differ under evidence-only",
        "n_heads_scored": len(macro_f1s),
        "exact_match": None,  # not defined when heads have different supervised sets
        "macro_f1": round(overall_macro, 4),
        "weighted_macro_f1": round(overall_weighted, 4),
        "macro_f1_by_kind": {
            k: round(sum(v) / len(v), 4) if v else 0.0 for k, v in by_kind.items()
        },
        "per_head": per_head,
    }


def format_metrics_md(metrics: dict, schema: MultiheadSchema) -> str:
    lines = [
        "# State Multihead Eval",
        "",
        "- scoring: **evidence-only** (unknown / mask=0 excluded per head)",
        f"- macro-F1 (primary): **{metrics['macro_f1']}**",
        f"- weighted macro-F1: **{metrics['weighted_macro_f1']}**",
        f"- by kind: `{metrics.get('macro_f1_by_kind')}`",
        "",
        "## Per-head",
        "",
        "| head | kind | support | macro-F1 | pos-F1 | pos-P | pos-R | acc |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for h in schema.heads:
        m = metrics["per_head"][h.name]
        lines.append(
            f"| `{h.name}` | {m['kind']} | {m['support']} | {m['macro_f1']} | "
            f"{m['positive_f1']} | {m['positive_precision']} | "
            f"{m['positive_recall']} | {m['accuracy']} |"
        )
    lines.append("")
    lines.append("## Head confusion (top)")
    lines.append("")
    for h in schema.heads:
        conf = metrics["per_head"][h.name].get("confusion_top") or {}
        if not conf:
            continue
        lines.append(f"### {h.name}")
        for k, c in conf.items():
            lines.append(f"- `{k}`: {c}")
        lines.append("")
    return "\n".join(lines) + "\n"
