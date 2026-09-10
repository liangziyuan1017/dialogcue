"""F000 wrapper: apply data/data_labels canonical relabel to labeled records.

Delegates to f007_infrastructure.label_relabel, which loads and calls
data/data_labels/llm_relabel_{facts,emotions}.py (plus descriptions + CSV maps).
"""

from __future__ import annotations

from f007_infrastructure.label_relabel import relabel_label_list
from f007_infrastructure.logging import get_logger as _get_logger

_log = _get_logger(__name__)

__all__ = ["relabel_label_list", "relabel_records"]


def relabel_records(records: list[dict]) -> dict:
    """In-place: rewrite state.facts / state.emotions to canonical labels."""
    stats = {
        "facts_in": 0,
        "facts_out": 0,
        "emotions_in": 0,
        "emotions_out": 0,
        "turns_touched": 0,
    }
    for record in records:
        dialog = record.get("response", {}).get("dialog", [])
        for turn in dialog:
            state = turn.get("state")
            if not isinstance(state, dict):
                continue
            changed = False
            if "facts" in state and state["facts"]:
                before = list(state["facts"])
                stats["facts_in"] += len(before)
                after = relabel_label_list(before, "facts")
                stats["facts_out"] += len(after)
                if after:
                    state["facts"] = after
                else:
                    state.pop("facts", None)
                changed = True
            if "emotions" in state and state["emotions"]:
                before = list(state["emotions"])
                stats["emotions_in"] += len(before)
                after = relabel_label_list(before, "emotions")
                stats["emotions_out"] += len(after)
                if after:
                    state["emotions"] = after
                else:
                    state.pop("emotions", None)
                changed = True
            if changed:
                stats["turns_touched"] += 1
            if state is not None and not state:
                turn.pop("state", None)
    return stats
