#!/usr/bin/env python3
"""Run multitask_v1 inference (usable decode — no fake training masks).

Input (JSON file or stdin): either
  {"context_window": "[collector] ...\\n[customer] ..."}
or
  {"turns": [{"turn_id":0,"speaker":"collector","text":"..."}, ...],
   "anchor_turn_id": 3}

Output: decoded Fact (active vs default) + Emotion + Willingness + probs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch

MT_ROOT = Path(__file__).resolve().parents[1]
SRC = MT_ROOT / "src"
sys.path.insert(0, str(SRC))

from context import encode_window  # noqa: E402
from device_utils import describe_device_env, get_device  # noqa: E402
from infer_decode import decode_multitask_output  # noqa: E402
from labels import emotion_labels, willingness_labels  # noqa: E402
from model import MultitaskV1Model  # noqa: E402
from paths import DEFAULT_FACT_SCHEMA, load_fact_schema, load_yaml  # noqa: E402
from threshold_calib import (  # noqa: E402
    load_thresholds,
    resolve_thresholds_path,
    thresholds_for_decode,
)


def _resolve(cfg_path: Path, maybe: str) -> Path:
    p = Path(maybe)
    if p.is_absolute():
        return p
    for base in (cfg_path.parent, MT_ROOT):
        cand = (base / p).resolve()
        if cand.exists():
            return cand
    return (cfg_path.parent / p).resolve()


def load_input(path: Path | None) -> dict:
    raw = sys.stdin.read() if path is None else path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise SystemExit("input JSON must be an object")
    return data


def build_context_text(payload: dict, *, max_turns: int, max_chars: int) -> dict:
    if payload.get("context_window"):
        return {
            "context_window": str(payload["context_window"]),
            "turn_ids": payload.get("turn_ids"),
            "truncated": bool(payload.get("truncated", False)),
        }
    turns = payload.get("turns") or []
    if not turns:
        raise SystemExit("need context_window or turns[]")
    anchor = payload.get("anchor_turn_id")
    if anchor is None:
        anchor = max(int(t.get("turn_id", i)) for i, t in enumerate(turns))
    # map turn_id -> index
    ids = [int(t.get("turn_id", i)) for i, t in enumerate(turns)]
    if int(anchor) not in ids:
        raise SystemExit(f"anchor_turn_id={anchor} not in turns")
    idx = ids.index(int(anchor))

    class _T:
        def __init__(self, d, i):
            self.turn_id = int(d.get("turn_id", i))
            self.speaker = str(d.get("speaker") or "")
            self.text = str(d.get("text") or "")

    turn_objs = [_T(t, i) for i, t in enumerate(turns)]
    win = encode_window(turn_objs, idx, max_turns=max_turns, max_chars=max_chars)
    return {
        "context_window": win.text,
        "turn_ids": win.turn_ids,
        "char_len": win.char_len,
        "truncated": win.truncated,
        "n_turns_selected": win.n_turns_selected,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Multitask v1 inference")
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument(
        "--config",
        type=Path,
        default=MT_ROOT / "configs" / "train_multitask.yaml",
    )
    ap.add_argument("--input", type=Path, default=None, help="JSON file; default stdin")
    ap.add_argument("--device", type=str, default=None)
    ap.add_argument(
        "--thresholds",
        type=Path,
        default=None,
        help="thresholds.json; default: <ckpt_dir>/thresholds.json if present",
    )
    ap.add_argument(
        "--fact-threshold",
        type=float,
        default=None,
        help="Override Fact binary fire threshold (else from thresholds.json or 0.5)",
    )
    ap.add_argument(
        "--emotion-min-prob",
        type=float,
        default=None,
        help="Override emotion abstain min-prob",
    )
    ap.add_argument(
        "--willingness-min-prob",
        type=float,
        default=None,
        help="Override willingness abstain min-prob",
    )
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    cfg_path = args.config.resolve()
    config = load_yaml(cfg_path)
    if args.device:
        config["device"] = args.device

    contract = load_yaml(_resolve(cfg_path, config.get("contract_path", "configs/contract.yaml")))
    ctx = contract.get("context") or config.get("context") or {}
    max_turns = int(ctx.get("max_turns", 4))
    max_chars = int(ctx.get("max_chars", 200))

    schema_rel = config.get("fact_schema_path") or contract.get("fact_schema_path")
    schema_path = _resolve(cfg_path, schema_rel) if schema_rel else DEFAULT_FACT_SCHEMA
    if not schema_path.exists():
        schema_path = DEFAULT_FACT_SCHEMA
    schema = load_fact_schema(schema_path)
    emo_vocab = emotion_labels(
        _resolve(cfg_path, config.get("emotion_labels_path", "configs/labels_emotion.yaml"))
    )
    will_vocab = willingness_labels(
        _resolve(
            cfg_path,
            config.get("willingness_labels_path", "configs/labels_willingness.yaml"),
        )
    )

    print(f"infer env=({describe_device_env()})", flush=True)
    device = get_device(config)
    print(f"device={device}", flush=True)

    ckpt = torch.load(args.ckpt, map_location="cpu")
    meta = ckpt.get("metadata") or {}
    ckpt_cfg = ckpt.get("config") or {}
    model_name = (
        (meta.get("model") or {}).get("encoder")
        or ckpt_cfg.get("model_name")
        or config.get("model_name", "__mock__")
    )
    if model_name != "__mock__":
        mp = _resolve(cfg_path, str(model_name))
        if mp.exists():
            model_name = str(mp)
    if (meta.get("model") or {}).get("encoder") == "__mock__" or ckpt_cfg.get(
        "model_name"
    ) == "__mock__":
        model_name = "__mock__"

    model = MultitaskV1Model(
        model_name,
        fact_schema=schema,
        emotion_vocab=emo_vocab,
        willingness_vocab=will_vocab,
        max_length=int(config.get("max_length", 256)),
    )
    state = ckpt.get("model_state_dict") or ckpt.get("model")
    if state is None:
        raise SystemExit("checkpoint missing weights")
    model.load_state_dict(state)
    model.to(device)
    model.eval()

    thr_path = resolve_thresholds_path(explicit=args.thresholds, ckpt=args.ckpt)
    thr_payload = load_thresholds(thr_path)
    decode_kw = thresholds_for_decode(thr_payload)
    if args.fact_threshold is not None:
        decode_kw["binary_positive_threshold"] = float(args.fact_threshold)
    if args.emotion_min_prob is not None:
        decode_kw["emotion_min_confidence"] = float(args.emotion_min_prob)
    if args.willingness_min_prob is not None:
        decode_kw["willingness_min_confidence"] = float(args.willingness_min_prob)
    if thr_path:
        print(f"loaded thresholds: {thr_path}", flush=True)
    else:
        print(
            "no thresholds.json found; using defaults "
            f"(fact={decode_kw['binary_positive_threshold']}, "
            f"emo_min={decode_kw['emotion_min_confidence']}, "
            f"will_min={decode_kw['willingness_min_confidence']})",
            flush=True,
        )

    payload = load_input(args.input)
    window = build_context_text(payload, max_turns=max_turns, max_chars=max_chars)
    text = window["context_window"]
    if not text.strip():
        raise SystemExit("empty context_window after encode")

    with torch.no_grad():
        out = model([text], device)
        decoded = decode_multitask_output(
            out,
            schema=schema,
            emotion_vocab=emo_vocab,
            willingness_vocab=will_vocab,
            batch_index=0,
            **decode_kw,
        )

    result = {
        "input": window,
        "prediction": decoded,
        "thresholds_path": str(thr_path) if thr_path else None,
        "thresholds_applied": {
            "fact_binary_threshold": decode_kw["binary_positive_threshold"],
            "emotion_min_prob": decode_kw["emotion_min_confidence"],
            "willingness_min_prob": decode_kw["willingness_min_confidence"],
            "fact_per_head": decode_kw.get("fact_thresholds_per_head"),
        },
        "checkpoint_metadata": {
            "fact": meta.get("fact"),
            "emotion": meta.get("emotion"),
            "willingness": meta.get("willingness"),
            "adjacency": meta.get("adjacency"),
            "encoder": (meta.get("model") or {}).get("encoder"),
        },
    }
    text_out = json.dumps(result, ensure_ascii=False, indent=2)
    print(text_out)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text_out, encoding="utf-8")


if __name__ == "__main__":
    main()
