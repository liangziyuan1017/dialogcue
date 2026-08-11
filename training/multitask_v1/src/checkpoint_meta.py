"""Checkpoint metadata builder — contract fields for reproducibility."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _file_fingerprint(path: str | Path | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists() or not p.is_file():
        return str(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()[:16]}"


def build_checkpoint_metadata(
    *,
    contract: dict[str, Any],
    model_name: str,
    hidden_size: int,
    fact_schema_path: str,
    fact_schema_version: str,
    task_weights: dict[str, float],
    emotion_adjacent_eval_set: str,
    dataset_version: str | None = None,
    code_version: str | None = None,
    train_jsonl: str | None = None,
    tokenizer_name: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ctx = dict(contract.get("context") or {})
    enc = model_name
    tok = tokenizer_name or (None if enc == "__mock__" else enc)
    meta = {
        "fact": contract.get("fact", "v3.1.2-patch1"),
        "emotion": contract.get("emotion", "11v1"),
        "willingness": contract.get("willingness", "5v1"),
        "adjacency": contract.get("adjacency", "none"),
        "context": {
            "strategy": ctx.get("strategy", "window_only"),
            "max_turns": int(ctx.get("max_turns", 4)),
            "max_chars": int(ctx.get("max_chars", 200)),
        },
        "ontology": {
            "fact": contract.get("fact", "v3.1.2-patch1"),
            "emotion": contract.get("emotion", "11v1"),
            "willingness": contract.get("willingness", "5v1"),
        },
        "model": {
            "encoder": enc,
            "tokenizer": tok,
            "hidden_size": int(hidden_size),
        },
        "training": {
            "context": f"window{ctx.get('max_turns', 4)}x{ctx.get('max_chars', 200)}",
            "adjacency": contract.get("adjacency", "none"),
            "loss": {
                "fact": float(task_weights.get("fact", 1.0)),
                "emotion": float(task_weights.get("emotion", 1.0)),
                "willingness": float(task_weights.get("willingness", 1.0)),
            },
        },
        "loss": {
            "fact": "masked_categorical_ce",  # per-head CE; not BCE/flat MLC
            "emotion": "ce",
            "willingness": "ce",
            "task_weights": dict(task_weights),
            "adjacency_in_train": False,
            "unknown_policy": "mask_exclude_from_loss",
        },
        "schema_fact_path": fact_schema_path,
        "schema_fact_version": fact_schema_version,
        "emotion_adjacent_eval_set": emotion_adjacent_eval_set,
        "dataset_version": dataset_version or "multitask_v1_window4x200",
        "code_version": code_version or "multitask_v1",
        "dataset_fingerprint": _file_fingerprint(train_jsonl),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "namespaces": {
            "fact_commitment_resistant": "fact.Commitment.resistant",
            "willingness_resistant": "willingness.resistant",
        },
    }
    if extra:
        meta.update(extra)
    return meta
