#!/usr/bin/env python3
"""Local smoke: build synthetic JSONL → 1-epoch mock train → eval."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

MT_ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> int:
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=str(MT_ROOT)).returncode


def main() -> int:
    build = MT_ROOT / "scripts" / "build_multitask_dataset.py"
    rc = _run([sys.executable, str(build), "--smoke"])
    if rc != 0:
        return rc

    smoke_train = MT_ROOT / "data" / "smoke" / "multitask_train.jsonl"
    smoke_val = MT_ROOT / "data" / "smoke" / "multitask_val.jsonl"
    if not smoke_train.exists():
        # with 2 conversations, one may land in test only — accept any split file
        splits = list((MT_ROOT / "data" / "smoke").glob("multitask_*.jsonl"))
        if not splits:
            print("FAIL: no smoke jsonl written")
            return 1
        # If train empty due to split luck, copy largest to train/val for smoke
        rows_by = {}
        for p in splits:
            rows_by[p] = p.read_text(encoding="utf-8").strip().splitlines()
        largest = max(rows_by, key=lambda p: len(rows_by[p]))
        smoke_train.write_text("\n".join(rows_by[largest]) + "\n", encoding="utf-8")
        smoke_val.write_text("\n".join(rows_by[largest][: max(1, len(rows_by[largest]) // 2)]) + "\n", encoding="utf-8")
        print("smoke: normalized train/val from", largest.name, flush=True)

    if not smoke_val.exists() or smoke_val.stat().st_size == 0:
        smoke_val.write_text(smoke_train.read_text(encoding="utf-8"), encoding="utf-8")

    base = yaml.safe_load(
        (MT_ROOT / "configs" / "train_multitask.yaml").read_text(encoding="utf-8")
    )
    base["model_name"] = "__mock__"
    base["epochs"] = 1
    base["batch_size"] = 2
    base["device"] = "cpu"
    base["init_from_encoder"] = False
    base["early_stop_patience"] = 0
    base["data"] = {
        "train_jsonl": str(smoke_train),
        "val_jsonl": str(smoke_val),
        "test_jsonl": str(smoke_val),
        "use_mock_if_missing": False,
    }
    base["output_dir"] = str(MT_ROOT / "checkpoints" / "multitask_v1_smoke")
    override = MT_ROOT / "configs" / "_smoke_train_override.yaml"
    override.write_text(yaml.safe_dump(base, allow_unicode=True), encoding="utf-8")

    train = MT_ROOT / "scripts" / "train_multitask.py"
    rc = _run([sys.executable, str(train), "--config", str(override)])
    if rc != 0:
        return rc

    ckpt = MT_ROOT / "checkpoints" / "multitask_v1_smoke" / "multitask_best.pt"
    if not ckpt.exists():
        print("FAIL: checkpoint missing", ckpt)
        return 1
    eval_py = MT_ROOT / "scripts" / "eval_multitask.py"
    return _run(
        [
            sys.executable,
            str(eval_py),
            "--ckpt",
            str(ckpt),
            "--config",
            str(override),
            "--split",
            "val",
            "--device",
            "cpu",
            "--out-dir",
            str(MT_ROOT / "checkpoints" / "multitask_v1_smoke"),
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
