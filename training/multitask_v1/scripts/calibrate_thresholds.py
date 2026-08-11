#!/usr/bin/env python3
"""Sweep inference thresholds on val and write thresholds.json next to the ckpt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch
from torch.utils.data import DataLoader

MT_ROOT = Path(__file__).resolve().parents[1]
SRC = MT_ROOT / "src"
sys.path.insert(0, str(SRC))

from dataset import MultitaskDataset, collate_multitask, load_jsonl  # noqa: E402
from device_utils import describe_device_env, get_device  # noqa: E402
from labels import emotion_labels, willingness_labels  # noqa: E402
from model import MultitaskV1Model  # noqa: E402
from paths import DEFAULT_FACT_SCHEMA, load_fact_schema, load_yaml  # noqa: E402
from threshold_calib import (  # noqa: E402
    calibrate_from_collected,
    collect_calibration_batches,
    write_thresholds,
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


def main() -> None:
    ap = argparse.ArgumentParser(description="Calibrate multitask inference thresholds")
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument(
        "--config",
        type=Path,
        default=MT_ROOT / "configs" / "train_multitask.yaml",
    )
    ap.add_argument("--split", choices=["val", "test"], default="val")
    ap.add_argument("--device", type=str, default=None)
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Default: <ckpt_dir>/thresholds.json",
    )
    args = ap.parse_args()

    cfg_path = args.config.resolve()
    config = load_yaml(cfg_path)
    if args.device:
        config["device"] = args.device

    contract = load_yaml(
        _resolve(cfg_path, config.get("contract_path", "configs/contract.yaml"))
    )
    schema_rel = config.get("fact_schema_path") or contract.get("fact_schema_path")
    schema_path = (
        _resolve(cfg_path, schema_rel) if schema_rel else DEFAULT_FACT_SCHEMA
    )
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

    print(f"calibrate env=({describe_device_env()})", flush=True)
    device = get_device(config)
    print(f"device={device} split={args.split}", flush=True)

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

    data_cfg = config.get("data") or {}
    key = "val_jsonl" if args.split == "val" else "test_jsonl"
    path = _resolve(
        cfg_path, data_cfg.get(key, f"data/multitask_{args.split}.jsonl")
    )
    rows = load_jsonl(path)
    if not rows:
        raise SystemExit(f"no data at {path}")

    loader = DataLoader(
        MultitaskDataset(
            rows,
            fact_schema=schema,
            emotion_vocab=emo_vocab,
            willingness_vocab=will_vocab,
        ),
        batch_size=int(config.get("batch_size", 16)),
        shuffle=False,
        collate_fn=collate_multitask,
    )

    collected = collect_calibration_batches(
        model,
        loader,
        schema=schema,
        emo_vocab=emo_vocab,
        will_vocab=will_vocab,
        device=device,
    )
    payload = calibrate_from_collected(
        collected,
        schema,
        checkpoint=str(args.ckpt.resolve()),
        split=args.split,
    )
    out = args.out or (args.ckpt.parent / "thresholds.json")
    write_thresholds(out, payload)
    print(json.dumps({
        "wrote": str(out),
        "fact_binary_threshold": payload["fact_binary_threshold"],
        "emotion_min_prob": payload["emotion_min_prob"],
        "willingness_min_prob": payload["willingness_min_prob"],
        "n_fact_heads_calibrated": len(payload.get("fact_binary_sweep") or {}),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
