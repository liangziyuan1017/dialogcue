#!/usr/bin/env python3
"""Build multitask_v1 JSONL (window Fact + Emotion + Willingness).

Does not modify training/multihead/. See docs/BUILD_DATASET.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

MT_ROOT = Path(__file__).resolve().parents[1]
SRC = MT_ROOT / "src"
sys.path.insert(0, str(SRC))

from build_samples import build_from_config, make_smoke_conversations  # noqa: E402
from paths import load_yaml  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Build multitask dataset")
    ap.add_argument(
        "--config",
        type=Path,
        default=MT_ROOT / "configs" / "build_multitask_dataset.yaml",
    )
    ap.add_argument("--limit-conversations", type=int, default=0)
    ap.add_argument(
        "--smoke",
        action="store_true",
        help="Use synthetic conversations; write under data/smoke/",
    )
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Exit 2 if quality errors",
    )
    args = ap.parse_args()

    cfg_path = args.config.resolve()
    cfg = load_yaml(cfg_path)
    cfg_dir = cfg_path.parent

    conversations = None
    if args.smoke:
        conversations = make_smoke_conversations()
        cfg = dict(cfg)
        cfg["output_dir"] = str((MT_ROOT / "data" / "smoke").resolve())
        cfg["reports_dir"] = str((MT_ROOT / "data" / "smoke" / "reports").resolve())
        # Put all synthetic rows in train; smoke_check copies to val if needed
        cfg["split"] = {"seed": 42, "train_ratio": 1.0, "val_ratio": 0.0}
        q = dict(cfg.get("quality") or {})
        q["warn_emotion_coverage_below"] = 0.0
        q["warn_willingness_coverage_below"] = 0.0
        cfg["quality"] = q
        print("smoke: synthetic conversations", flush=True)

    result = build_from_config(
        cfg,
        cfg_dir=cfg_dir,
        conversations=conversations,
        limit_conversations=args.limit_conversations,
    )
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    for w in result["warnings"]:
        print(f"WARN: {w}")
    for e in result["errors"]:
        print(f"ERROR: {e}")
    print(f"out_dir={result['out_dir']}")
    print(f"reports={result['reports_dir']}")
    if args.strict and result["errors"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
