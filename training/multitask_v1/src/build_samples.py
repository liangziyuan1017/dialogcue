"""Build multitask samples from conversations (window-aligned Fact + Emotion + Will)."""

from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from context import encode_window
from labels import emotion_labels, willingness_labels
from paths import (
    DEFAULT_FACT_SCHEMA,
    MULTIHEAD_ROOT,
    ensure_multihead_on_path,
    load_fact_schema,
    load_yaml,
    resolve_from_cfg,
)

ensure_multihead_on_path()

from label_mask import UNKNOWN, build_labels_and_masks  # noqa: E402
from raw_to_multihead import RawToMultiheadMapper  # noqa: E402
from slot_relocate import SlotRelocator, build_slot_relocator  # noqa: E402


@dataclass
class TaskLabelPick:
    label: str | None
    raws_considered: list[str]
    mapped: list[dict[str, str]]
    policy: str


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


def _window_fact_raws(
    conversation,
    turn_ids: Sequence[int],
    relocator: SlotRelocator,
) -> tuple[list[str], list[dict[str, str]]]:
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


def _emotion_raws(raw_state: dict | None) -> list[str]:
    if not raw_state:
        return []
    return [str(x) for x in (raw_state.get("emotions") or []) if x]


def _willingness_raws(raw_state: dict | None) -> list[str]:
    if not raw_state:
        return []
    willingness_raw = raw_state.get("willingness")
    if willingness_raw is None:
        willingness_raw = raw_state.get("willing_to_pay")
    if isinstance(willingness_raw, list):
        return [str(x) for x in willingness_raw if x]
    if willingness_raw is not None and str(willingness_raw).strip():
        return [str(willingness_raw)]
    return []


def pick_task_label(
    conversation,
    turn_ids: Sequence[int],
    anchor_turn_id: int,
    relocator: SlotRelocator,
    *,
    kind: str,
    policy: str = "anchor_then_window_last",
) -> TaskLabelPick:
    """
    kind: 'emotion' | 'willingness'
    policy: anchor_then_window_last (frozen for v1)
    """
    if policy != "anchor_then_window_last":
        raise ValueError(f"unsupported label policy: {policy!r}")

    by_id = {int(t.turn_id): t for t in conversation.turns}
    mapped_events: list[dict[str, str]] = []
    raws_all: list[str] = []

    def consider(tid: int) -> None:
        turn = by_id.get(int(tid))
        if turn is None or turn.speaker != "customer":
            return
        raws = (
            _emotion_raws(turn.raw_state)
            if kind == "emotion"
            else _willingness_raws(turn.raw_state)
        )
        for raw in raws:
            raws_all.append(raw)
            # Fact-only misplaced labels: relocate path owns them; skip as task target
            if kind == "emotion":
                if relocator.is_fact_raw(raw) and not relocator.is_emotion_raw(raw):
                    continue
                lab = relocator.emotion_mapper.map_label(raw)
            else:
                if relocator.is_fact_raw(raw) and not relocator.is_willingness_raw(raw):
                    continue
                lab = relocator.willingness_mapper.map_label(raw)
            if lab:
                mapped_events.append(
                    {"turn_id": str(tid), "raw": raw, "label": str(lab)}
                )

    for tid in turn_ids:
        consider(int(tid))

    if not mapped_events:
        return TaskLabelPick(
            label=None, raws_considered=raws_all, mapped=[], policy=policy
        )

    anchor_hits = [e for e in mapped_events if int(e["turn_id"]) == int(anchor_turn_id)]
    chosen = (anchor_hits or mapped_events)[-1]
    return TaskLabelPick(
        label=chosen["label"],
        raws_considered=raws_all,
        mapped=mapped_events,
        policy=policy,
    )


def build_samples_for_conversation(
    conversation,
    mapper: RawToMultiheadMapper,
    schema,
    relocator: SlotRelocator,
    *,
    max_turns: int,
    max_chars: int,
    emotion_policy: str,
    willingness_policy: str,
    emotion_vocab: set[str],
    willingness_vocab: set[str],
) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for idx, turn in enumerate(conversation.turns):
        if turn.speaker != "customer":
            continue
        win = encode_window(
            conversation.turns,
            idx,
            max_turns=max_turns,
            max_chars=max_chars,
            strategy="window_only",
        )
        window_raws, window_relocated = _window_fact_raws(
            conversation, win.turn_ids, relocator
        )
        resolved = mapper.map_raws(window_raws)
        fact_labels, fact_mask = build_labels_and_masks(schema, resolved.labels)

        emo = pick_task_label(
            conversation,
            win.turn_ids,
            turn.turn_id,
            relocator,
            kind="emotion",
            policy=emotion_policy,
        )
        will = pick_task_label(
            conversation,
            win.turn_ids,
            turn.turn_id,
            relocator,
            kind="willingness",
            policy=willingness_policy,
        )

        emotion = emo.label if emo.label in emotion_vocab else None
        willingness = will.label if will.label in willingness_vocab else None

        samples.append(
            {
                "conversation_id": conversation.conversation_id,
                "turn_id": turn.turn_id,
                "input": {
                    "context_window": win.text,
                    "window_turns": max_turns,
                    "char_budget": max_chars,
                    "char_len": win.char_len,
                    "truncated": win.truncated,
                    "n_turns_selected": win.n_turns_selected,
                    "turn_ids": win.turn_ids,
                    "strategy": "window_only",
                },
                "fact_labels": fact_labels,
                "fact_mask": fact_mask,
                "labels": fact_labels,
                "head_mask": fact_mask,
                "emotion": emotion,
                "willingness": willingness,
                "meta": {
                    "label_scope": "window",
                    "context_mode": "window_only",
                    "emotion_policy": emotion_policy,
                    "willingness_policy": willingness_policy,
                    "unknown_token": UNKNOWN,
                    "window_raws": list(window_raws),
                    "mapped_raws": resolved.mapped_facts,
                    "unmapped_raws": resolved.unmapped_facts,
                    "conflicts_resolved": resolved.conflicts_resolved,
                    "fired": resolved.fired,
                    "relocated_labels": window_relocated,
                    "emotion_raws": emo.raws_considered,
                    "emotion_mapped": emo.mapped,
                    "willingness_raws": will.raws_considered,
                    "willingness_mapped": will.mapped,
                    "reward": getattr(conversation, "reward", None),
                },
            }
        )
    return samples


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    emo_n = sum(1 for r in rows if r.get("emotion"))
    will_n = sum(1 for r in rows if r.get("willingness"))
    fact_pos = 0
    for r in rows:
        mask = r.get("fact_mask") or r.get("head_mask") or {}
        fact_pos += sum(1 for v in mask.values() if int(v) == 1)
    return {
        "n_samples": n,
        "emotion_supervised": emo_n,
        "emotion_coverage": round(emo_n / n, 4) if n else 0.0,
        "willingness_supervised": will_n,
        "willingness_coverage": round(will_n / n, 4) if n else 0.0,
        "fact_mask1_head_instances": fact_pos,
    }


def make_smoke_conversations():
    """Minimal synthetic conversations (no output_rewarded.py needed)."""
    ensure_multihead_on_path()
    from conversation_parser import Conversation, Turn

    def conv(cid: str, turns: list[Turn], reward: int = 1) -> Conversation:
        return Conversation(conversation_id=cid, turns=turns, reward=reward)

    # Use trainable emotion names + willingness aliases that exist in slot_relocate maps
    c0 = conv(
        "smoke_c0",
        [
            Turn(0, "collector", "您好，请问是张先生吗？", raw_state=None),
            Turn(
                1,
                "customer",
                "是我，最近失业了没什么收入。",
                raw_state={
                    "facts": ["unemployed", "no_income"],
                    "emotions": ["distress"],
                    "willingness": ["refusal_to_pay"],
                },
            ),
            Turn(2, "collector", "理解，我们看看能不能分期。", raw_state=None),
            Turn(
                3,
                "customer",
                "可以商量一下条件，但现在真的很难。",
                raw_state={
                    "facts": ["request_installment"],
                    "emotions": ["complaint", "negotiation"],
                    "willingness": ["conditional_willingness"],
                },
            ),
        ],
    )
    c1 = conv(
        "smoke_c1",
        [
            Turn(0, "collector", "请确认还款计划。", raw_state=None),
            Turn(
                1,
                "customer",
                "我下周发工资就还。",
                raw_state={
                    "facts": ["promise_to_pay_after_payday"],
                    "emotions": ["engagement"],
                    "willingness": ["promise_to_pay_after_payday"],
                },
            ),
        ],
    )
    return [c0, c1]


def build_from_config(
    cfg: dict[str, Any],
    *,
    cfg_dir: Path,
    conversations: list | None = None,
    limit_conversations: int = 0,
) -> dict[str, Any]:
    """
    Build split JSONL + summary.
    If conversations is None, load from cfg['input_path'].
    """
    schema_path = resolve_from_cfg(
        cfg_dir, cfg.get("fact_schema_path") or DEFAULT_FACT_SCHEMA
    )
    if not schema_path.exists():
        schema_path = DEFAULT_FACT_SCHEMA
    schema = load_fact_schema(schema_path)

    map_path = resolve_from_cfg(
        cfg_dir,
        cfg.get("raw_to_multihead")
        or (MULTIHEAD_ROOT / "configs" / "raw_to_multihead.yaml"),
    )
    mapper = RawToMultiheadMapper(schema, map_path)

    ont = cfg.get("ontology") or {}
    emo_map = resolve_from_cfg(
        cfg_dir,
        ont.get("emotion_mapping")
        or (MULTIHEAD_ROOT / "configs" / "slot_relocate" / "emotion_mapping.yaml"),
    )
    will_ont = resolve_from_cfg(
        cfg_dir,
        ont.get("willingness_ontology")
        or (MULTIHEAD_ROOT / "configs" / "slot_relocate" / "willingness_ontology.yaml"),
    )
    relocator = build_slot_relocator(mapper, emo_map, will_ont)

    emo_vocab = set(
        emotion_labels(
            resolve_from_cfg(
                cfg_dir, cfg.get("emotion_labels_path") or "labels_emotion.yaml"
            )
        )
    )
    will_vocab = set(
        willingness_labels(
            resolve_from_cfg(
                cfg_dir,
                cfg.get("willingness_labels_path") or "labels_willingness.yaml",
            )
        )
    )

    ctx = cfg.get("context") or {}
    max_turns = int(ctx.get("max_turns", 4))
    max_chars = int(ctx.get("max_chars", 200))
    pol = cfg.get("label_policy") or {}
    emotion_policy = str(pol.get("emotion", "anchor_then_window_last"))
    willingness_policy = str(pol.get("willingness", "anchor_then_window_last"))

    if conversations is None:
        ensure_multihead_on_path()
        from conversation_parser import load_conversations

        input_path = resolve_from_cfg(cfg_dir, cfg["input_path"])
        if not input_path.exists():
            raise FileNotFoundError(
                f"input_path not found: {input_path}. "
                "Use --smoke for synthetic data, or set input_path to output_rewarded.py"
            )
        conversations = load_conversations(input_path)

    if limit_conversations > 0:
        conversations = conversations[:limit_conversations]

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
            max_turns=max_turns,
            max_chars=max_chars,
            emotion_policy=emotion_policy,
            willingness_policy=willingness_policy,
            emotion_vocab=emo_vocab,
            willingness_vocab=will_vocab,
        )
        split = split_map.get(conv.conversation_id, "train")
        for r in rows:
            r["split"] = split
            buckets[split].append(r)

    out_dir = resolve_from_cfg(cfg_dir, cfg.get("output_dir", "../data"))
    reports_dir = resolve_from_cfg(cfg_dir, cfg.get("reports_dir", "../data/reports"))
    out_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    written = {}
    all_rows: list[dict] = []
    for split, rows in buckets.items():
        path = out_dir / f"multitask_{split}.jsonl"
        write_jsonl(path, rows)
        written[split] = {"path": str(path), "n": len(rows)}
        all_rows.extend(rows)

    summary = summarize_rows(all_rows)
    summary.update(
        {
            "schema": schema.version,
            "raw_map": str(map_path),
            "emotion_mapping": str(emo_map),
            "willingness_ontology": str(will_ont),
            "max_turns": max_turns,
            "max_chars": max_chars,
            "emotion_policy": emotion_policy,
            "willingness_policy": willingness_policy,
            "n_conversations": len(conversations),
            "splits": written,
        }
    )
    (reports_dir / "build_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_lines = [
        "# Multitask dataset build summary",
        "",
        f"- conversations: {summary['n_conversations']}",
        f"- samples: {summary['n_samples']}",
        f"- emotion coverage: {summary['emotion_coverage']}",
        f"- willingness coverage: {summary['willingness_coverage']}",
        f"- fact mask=1 head-instances: {summary['fact_mask1_head_instances']}",
        f"- window: {max_turns} turns / {max_chars} chars",
        "",
        "## Splits",
    ]
    for split, info in written.items():
        md_lines.append(f"- `{split}`: n={info['n']} → `{info['path']}`")
    (reports_dir / "build_summary.md").write_text(
        "\n".join(md_lines) + "\n", encoding="utf-8"
    )

    quality = cfg.get("quality") or {}
    warnings: list[str] = []
    errors: list[str] = []
    if summary["n_samples"] < int(quality.get("min_samples", 1)):
        errors.append(f"n_samples={summary['n_samples']} < min_samples")
    emo_floor = float(quality.get("warn_emotion_coverage_below", 0.0))
    will_floor = float(quality.get("warn_willingness_coverage_below", 0.0))
    if summary["emotion_coverage"] < emo_floor:
        warnings.append(
            f"emotion_coverage={summary['emotion_coverage']} < {emo_floor}"
        )
    if summary["willingness_coverage"] < will_floor:
        warnings.append(
            f"willingness_coverage={summary['willingness_coverage']} < {will_floor}"
        )

    return {
        "summary": summary,
        "warnings": warnings,
        "errors": errors,
        "out_dir": str(out_dir),
        "reports_dir": str(reports_dir),
    }
