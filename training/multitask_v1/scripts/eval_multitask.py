#!/usr/bin/env python3
"""Evaluate multitask v1 checkpoint (val/test) — full-data capable."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import torch
from torch.utils.data import DataLoader

MT_ROOT = Path(__file__).resolve().parents[1]
SRC = MT_ROOT / "src"
sys.path.insert(0, str(SRC))

_train_path = Path(__file__).resolve().parent / "train_multitask.py"
_spec = importlib.util.spec_from_file_location("train_multitask_mod", _train_path)
_train = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_train)

from dataset import MultitaskDataset, collate_multitask, iter_mock_samples, load_jsonl  # noqa: E402
from device_utils import describe_device_env, get_device  # noqa: E402
from labels import emotion_labels, willingness_labels  # noqa: E402
from model import MultitaskV1Model  # noqa: E402
from paths import DEFAULT_FACT_SCHEMA, load_fact_schema, load_yaml  # noqa: E402
from report_format import format_multitask_metrics_md  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument(
        "--config",
        type=Path,
        default=MT_ROOT / "configs" / "train_multitask.yaml",
    )
    ap.add_argument("--split", choices=["val", "test", "mock"], default="test")
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument(
        "--device",
        type=str,
        default=None,
        help='Override config device, e.g. "npu:0" / "cpu"',
    )
    args = ap.parse_args()

    cfg_path = args.config.resolve()
    config = _train.load_config(cfg_path)
    if args.device:
        config["device"] = args.device

    contract = load_yaml(
        _train.resolve_path(cfg_path, config.get("contract_path", "configs/contract.yaml"))
    )
    adj_eval_set = str(
        config.get("emotion_adjacent_eval_set")
        or contract.get("emotion_adjacent_eval_set")
        or "all_rule"
    )
    schema_rel = config.get("fact_schema_path") or contract.get("fact_schema_path")
    schema_path = (
        _train.resolve_path(cfg_path, schema_rel) if schema_rel else DEFAULT_FACT_SCHEMA
    )
    if not schema_path.exists():
        schema_path = DEFAULT_FACT_SCHEMA
    fact_schema = load_fact_schema(schema_path)
    emo_vocab = emotion_labels(
        _train.resolve_path(
            cfg_path, config.get("emotion_labels_path", "configs/labels_emotion.yaml")
        )
    )
    will_vocab = willingness_labels(
        _train.resolve_path(
            cfg_path,
            config.get("willingness_labels_path", "configs/labels_willingness.yaml"),
        )
    )

    print(
        f"eval config={cfg_path} device_cfg={config.get('device')!r} "
        f"cli_device={args.device!r} env=({describe_device_env()})",
        flush=True,
    )
    device = get_device(config)
    print(f"device={device}", flush=True)
    if device.type == "cpu":
        print(
            "WARN: running on CPU. If you expected NPU, pass --device npu:0 after "
            "`source …/set_env.sh`.",
            flush=True,
        )

    # Load weights on CPU first — Ascend map_location can be flaky across builds.
    ckpt = torch.load(args.ckpt, map_location="cpu")
    meta = ckpt.get("metadata") or {}
    ckpt_cfg = ckpt.get("config") or {}
    model_name = (
        (meta.get("model") or {}).get("encoder")
        or ckpt_cfg.get("model_name")
        or config.get("model_name", "__mock__")
    )
    if model_name != "__mock__":
        mp = _train.resolve_path(cfg_path, str(model_name))
        if mp.exists():
            model_name = str(mp)
    if ckpt_cfg.get("model_name") == "__mock__" or (
        isinstance(meta.get("model"), dict) and meta["model"].get("encoder") == "__mock__"
    ):
        model_name = "__mock__"

    model = MultitaskV1Model(
        model_name,
        fact_schema=fact_schema,
        emotion_vocab=emo_vocab,
        willingness_vocab=will_vocab,
        max_length=int(config.get("max_length", 256)),
    )
    state = ckpt.get("model_state_dict") or ckpt.get("model")
    if state is None:
        raise SystemExit("checkpoint missing model_state_dict/model")
    model.load_state_dict(state)
    model.to(device)

    data_cfg = config.get("data") or {}
    if args.split == "mock":
        rows = list(
            iter_mock_samples(
                fact_schema,
                emotion_vocab=emo_vocab,
                willingness_vocab=will_vocab,
                n=8,
            )
        )
    else:
        key = "val_jsonl" if args.split == "val" else "test_jsonl"
        default = f"data/multitask_{args.split}.jsonl"
        path = _train.resolve_path(cfg_path, data_cfg.get(key, default))
        rows = load_jsonl(path)
        if not rows:
            raise SystemExit(f"no data at {path}")

    loader = DataLoader(
        MultitaskDataset(
            rows,
            fact_schema=fact_schema,
            emotion_vocab=emo_vocab,
            willingness_vocab=will_vocab,
        ),
        batch_size=int(config.get("batch_size", 16)),
        shuffle=False,
        collate_fn=collate_multitask,
    )
    metrics = _train.run_eval(
        model,
        loader,
        fact_schema=fact_schema,
        emo_vocab=emo_vocab,
        will_vocab=will_vocab,
        adj_eval_set=adj_eval_set,
        device=device,
        desc=f"eval-{args.split}",
    )
    payload = {"metadata": meta, "metrics": metrics, "split": args.split}
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print(text)

    out_dir = args.out_dir
    if out_dir is None:
        out_dir = args.ckpt.parent
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"eval_{args.split}"
    (out_dir / f"{stem}.json").write_text(text, encoding="utf-8")
    (out_dir / f"{stem}.md").write_text(
        format_multitask_metrics_md(metrics, metadata=meta, split=args.split),
        encoding="utf-8",
    )
    print(f"wrote {out_dir / (stem + '.json')} and .md", flush=True)


if __name__ == "__main__":
    main()
