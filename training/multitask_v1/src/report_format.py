"""Eval report formatting for multitask v1."""

from __future__ import annotations

from typing import Any


def format_multitask_metrics_md(
    metrics: dict[str, Any],
    *,
    metadata: dict[str, Any] | None = None,
    split: str = "",
) -> str:
    meta = metadata or {}
    emo = metrics.get("emotion") or {}
    will = metrics.get("willingness") or {}
    fact = metrics.get("fact") or {}
    lines = [
        "# Multitask v1 eval report",
        "",
        f"- split: `{split}`",
        f"- fact: `{meta.get('fact', '')}`",
        f"- emotion: `{meta.get('emotion', '')}` adjacency_train=`{meta.get('adjacency', 'none')}`",
        f"- willingness: `{meta.get('willingness', '')}`",
        f"- context: `{meta.get('context', {})}`",
        "",
        "## Emotion (strict + adjacent)",
        "",
        f"| metric | value |",
        f"|---|---|",
        f"| n | {emo.get('n')} |",
        f"| strict_accuracy | {emo.get('strict_accuracy')} |",
        f"| strict_macro_f1 | {emo.get('strict_macro_f1')} |",
        f"| strict_weighted_f1 | {emo.get('strict_weighted_f1')} |",
        f"| adj_accuracy | {emo.get('adj_accuracy')} |",
        f"| adj_macro_f1 | {emo.get('adj_macro_f1')} |",
        f"| adjacent_eval_set | {emo.get('emotion_adjacent_eval_set')} |",
        "",
        "## Willingness (strict)",
        "",
        f"| metric | value |",
        f"|---|---|",
        f"| n | {will.get('n')} |",
        f"| accuracy | {will.get('accuracy')} |",
        f"| macro_f1 | {will.get('macro_f1')} |",
        f"| weighted_f1 | {will.get('weighted_f1')} |",
        "",
        "## Fact (evidence-only)",
        "",
        f"| metric | value |",
        f"|---|---|",
        f"| head_level_evidence_instances | {fact.get('head_level_evidence_instances') or fact.get('evidence_samples')} |",
        f"| weighted_positive_f1 | {fact.get('weighted_positive_f1')} |",
        f"| macro_f1 | {fact.get('macro_f1')} |",
        f"| weighted_macro_f1 | {fact.get('weighted_macro_f1')} |",
        "",
    ]
    graph = emo.get("emotion_confusion_graph") or []
    if graph:
        lines.extend(["## Emotion confusion (top)", ""])
        for row in graph[:15]:
            lines.append(
                f"- {row.get('gold')} → {row.get('pred')}: {row.get('count')}"
            )
        lines.append("")
    return "\n".join(lines)
