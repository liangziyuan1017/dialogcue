#!/usr/bin/env python3
"""Build multihead current-state dataset (recent 4 turns + 200 chars).

Maps conversation raw facts → 19-head labels via raw_to_multihead.yaml.
Label scope (v3.1.2+): **window-supported only** — raws from the same
turn_ids that enter `encode_recent_window` after char-budget trim.
Cumulative dialogue memory is NOT used for Softmax supervision
(persistent memory is a merge concern at inference).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

MH_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MH_ROOT / "src"))

from context_encode import encode_recent_window  # noqa: E402
from conversation_parser import load_conversations  # noqa: E402
from label_mask import UNKNOWN, build_labels_and_masks, flatten_label_mask_fields  # noqa: E402
from raw_to_multihead import RawToMultiheadMapper  # noqa: E402
from schema_loader import load_schema  # noqa: E402
from slot_relocate import SlotRelocator, build_slot_relocator  # noqa: E402
from state_reports import write_state_audit_reports  # noqa: E402


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _resolve(base: Path, p: str | Path) -> Path:
    """Resolve path relative to config dir (base)."""
    path = Path(p)
    if path.is_absolute():
        return path
    return (base / path).resolve()


def _split_conversations(
    conv_ids: list[str],
    *,
    seed: int,
    train_ratio: float,
    val_ratio: float,
) -> dict[str, str]:
    ids = list(conv_ids)
    rng = random.Random(seed)
    rng.shuffle(ids)
    n = len(ids)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)
    out: dict[str, str] = {}
    for i, cid in enumerate(ids):
        if i < n_train:
            out[cid] = "train"
        elif i < n_train + n_val:
            out[cid] = "val"
        else:
            out[cid] = "test"
    return out


def _window_raws_for_turn_ids(
    conversation,
    turn_ids: list[int],
    relocator: SlotRelocator,
) -> tuple[list[str], list[dict[str, str]]]:
    """Collect unique facts from customer turns that survived the text window."""
    by_id = {int(t.turn_id): t for t in conversation.turns}
    raws: list[str] = []
    seen: set[str] = set()
    relocated: list[dict[str, str]] = []
    for tid in turn_ids:
        turn = by_id.get(int(tid))
        if turn is None or turn.speaker != "customer":
            continue
        slot = relocator.collect_facts(turn.raw_state)
        relocated.extend(slot.relocated)
        for raw in slot.facts:
            if raw not in seen:
                seen.add(raw)
                raws.append(raw)
    return raws, relocated


def build_samples_for_conversation(
    conversation,
    mapper: RawToMultiheadMapper,
    schema,
    relocator: SlotRelocator,
    *,
    window_turns: int,
    char_budget: int,
) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    for idx, turn in enumerate(conversation.turns):
        if turn.speaker != "customer":
            continue

        # Text window first — label raws must use the same turn_ids (after trim).
        win = encode_recent_window(
            conversation.turns,
            idx,
            window_turns=window_turns,
            char_budget=char_budget,
        )
        window_raws, window_relocated = _window_raws_for_turn_ids(
            conversation, win.turn_ids, relocator
        )
        resolved = mapper.map_raws(window_raws)
        labels, head_mask = build_labels_and_masks(schema, resolved.labels)

        samples.append(
            {
                "conversation_id": conversation.conversation_id,
                "turn_id": turn.turn_id,
                "input": {
                    "context_window": win.text,
                    "window_turns": window_turns,
                    "char_budget": char_budget,
                    "char_len": win.char_len,
                    "truncated": win.truncated,
                    "n_turns_selected": win.n_turns_selected,
                    "turn_ids": win.turn_ids,
                    "pinned_evidence": None,
                },
                "labels": labels,
                "head_mask": head_mask,
                # flat twin for human review / external tools
                "labels_flat": flatten_label_mask_fields(labels, head_mask),
                "meta": {
                    "context_mode": "recent_turns_char_budget",
                    "label_scope": "window",
                    "label_source": "raw_to_multihead_v1",
                    "supervision": "window_evidence_nondefault_mask1_unknown_mask0",
                    "unknown_token": UNKNOWN,
                    "window_raws": list(window_raws),
                    # Back-compat alias for older report readers
                    "memory_raws": list(window_raws),
                    "mapped_raws": resolved.mapped_facts,
                    "unmapped_raws": resolved.unmapped_facts,
                    "conflicts_resolved": resolved.conflicts_resolved,
                    "fired": resolved.fired,
                    "relocated_labels": window_relocated,
                    "reward": conversation.reward,
                },
            }
        )
    return samples


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build multihead state dataset")
    ap.add_argument(
        "--config",
        type=Path,
        default=MH_ROOT / "configs" / "build_state_dataset.yaml",
    )
    ap.add_argument("--limit-conversations", type=int, default=0)
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if quality gate has errors",
    )
    args = ap.parse_args()

    cfg = _load_yaml(args.config.resolve())
    cfg_dir = args.config.resolve().parent

    input_path = _resolve(cfg_dir, cfg["input_path"])
    out_dir = _resolve(cfg_dir, cfg.get("output_dir", "data/state"))
    reports_dir = _resolve(cfg_dir, cfg.get("reports_dir", "data/reports"))
    out_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    schema = load_schema(str(_resolve(cfg_dir, cfg.get("schema_path", "configs/schema_v3.1.yaml"))))
    map_path = _resolve(cfg_dir, cfg.get("raw_to_multihead", "raw_to_multihead.yaml"))
    mapper = RawToMultiheadMapper(schema, map_path)

    ont = cfg.get("ontology") or {}
    relocator = build_slot_relocator(
        mapper,
        _resolve(cfg_dir, ont["emotion_mapping"]),
        _resolve(cfg_dir, ont["willingness_ontology"]),
    )

    tp = cfg.get("train_policy") or {}
    window_turns = int(tp.get("window_turns", schema.raw.get("train_policy", {}).get("window_turns", 5)))
    char_budget = int(tp.get("char_budget", schema.raw.get("train_policy", {}).get("char_budget", 250)))

    print(f"Loading conversations from {input_path}")
    conversations = load_conversations(input_path)
    if args.limit_conversations > 0:
        conversations = conversations[: args.limit_conversations]
    print(
        f"conversations={len(conversations)} map={map_path.name} "
        f"slot_relocate=on label_scope=window"
    )

    split_cfg = cfg.get("split") or {}
    split_map = _split_conversations(
        [c.conversation_id for c in conversations],
        seed=int(split_cfg.get("seed", 42)),
        train_ratio=float(split_cfg.get("train_ratio", 0.8)),
        val_ratio=float(split_cfg.get("val_ratio", 0.1)),
    )

    buckets: dict[str, list[dict]] = defaultdict(list)
    for conv in conversations:
        rows = build_samples_for_conversation(
            conv,
            mapper,
            schema,
            relocator,
            window_turns=window_turns,
            char_budget=char_budget,
        )
        split = split_map.get(conv.conversation_id, "train")
        for r in rows:
            r["split"] = split
            buckets[split].append(r)

    for split, rows in buckets.items():
        path = out_dir / f"state_{split}.jsonl"
        write_jsonl(path, rows)
        print(f"wrote {path} n={len(rows)}")

    all_rows = [r for rows in buckets.values() for r in rows]
    audit = write_state_audit_reports(
        reports_dir,
        all_rows,
        schema,
        split_map=split_map,
        summary_extra={
            "window_turns": window_turns,
            "char_budget": char_budget,
            "schema": schema.version,
            "label_source": "raw_to_multihead_v1",
            "label_scope": "window",
            "raw_map": str(map_path),
        },
        quality_cfg=cfg.get("quality") or {},
    )
    print(f"Reports: {reports_dir / 'summary.md'}")
    q = audit["quality"]
    if q["errors"]:
        print(f"Quality errors ({len(q['errors'])}):")
        for e in q["errors"][:10]:
            print(f"  - {e}")
    if q["warnings"]:
        print(f"Quality warnings ({len(q['warnings'])}):")
        for w in q["warnings"][:10]:
            print(f"  - {w}")
    print(json.dumps(audit["summary"], ensure_ascii=False, indent=2))
    if args.strict and q["errors"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
