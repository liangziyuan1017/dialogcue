"""Fact evidence-only eval bridge (read-only multihead metrics)."""

from __future__ import annotations

from typing import Any

from paths import multihead_state_metrics


def evaluate_fact_evidence_only(
    schema,
    y_true: dict[str, list[str]],
    y_pred: dict[str, list[str]],
) -> dict[str, Any]:
    """Caller must already filter to evidence-only rows (mask=1, label≠unknown)."""
    mod = multihead_state_metrics()
    return mod.evaluate_predictions(schema, y_true, y_pred)
