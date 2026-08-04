"""Label/mask policy for state multihead supervision (v3.1).

Rules (colleague P0):
- unknown is storage-only; never a CE class.
- head_mask=0 → do not contribute to loss.
- head_mask=1 only when the head has a non-default (evidenced) value.
- IdentityProcess: always mask=0 (event; eval-only).
"""

from __future__ import annotations

from typing import Any

UNKNOWN = "unknown"


def default_value_for_head(schema, head_name: str) -> str:
    h = schema.head_by_name()[head_name]
    return h.values[-1]


def is_nondefault(schema, head_name: str, value: str) -> bool:
    if value in (None, "", UNKNOWN):
        return False
    return str(value) != default_value_for_head(schema, head_name)


def build_labels_and_masks(
    schema,
    resolved_labels: dict[str, str],
    *,
    always_mask_zero: frozenset[str] | None = None,
) -> tuple[dict[str, str], dict[str, int]]:
    """
    Convert mapper defaults → (labels with unknown, head_mask).

    Returns labels suitable for JSONL storage and masks for training loss.
    """
    zero = always_mask_zero or frozenset(
        (schema.raw.get("train_policy") or {}).get("default_head_mask", {}).keys()
    )
    # also force IdentityProcess
    zero = frozenset(set(zero) | {"IdentityProcess"})

    labels: dict[str, str] = {}
    masks: dict[str, int] = {}
    for h in schema.heads:
        raw_val = str(resolved_labels.get(h.name, default_value_for_head(schema, h.name)))
        if h.name in zero:
            labels[h.name] = raw_val if is_nondefault(schema, h.name, raw_val) else UNKNOWN
            masks[h.name] = 0
            continue
        if is_nondefault(schema, h.name, raw_val):
            labels[h.name] = raw_val
            masks[h.name] = 1
        else:
            labels[h.name] = UNKNOWN
            masks[h.name] = 0
    return labels, masks


def flatten_label_mask_fields(labels: dict[str, str], masks: dict[str, int]) -> dict[str, Any]:
    """Optional flat view: Employment, Employment_mask, ..."""
    out: dict[str, Any] = {}
    for h, v in labels.items():
        out[h] = v
        out[f"{h}_mask"] = int(masks.get(h, 0))
    return out
