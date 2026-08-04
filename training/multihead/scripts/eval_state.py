#!/usr/bin/env python3
"""Evaluate state multihead checkpoint (val or test once).

Optional --sweep-threshold: for binary heads, scan positive-class threshold on
this split and report best F1 (colleague: ComplianceRisk/Grievance/Health ≠ 0.5).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch
import torch.nn.functional as F
import yaml
from torch.utils.data import DataLoader

MH_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MH_ROOT / "src"))

from datasets.state_dataset import StateDataset, collate_state, load_state_jsonl  # noqa: E402
from device_utils import get_device  # noqa: E402
from metrics.state_metrics import evaluate_predictions, format_metrics_md  # noqa: E402
from models.state_model import StateMultiheadModel  # noqa: E402
from schema_loader import load_schema  # noqa: E402


def resolve_path(cfg_path: Path, maybe_rel: str) -> Path:
    p = Path(maybe_rel)
    if p.is_absolute():
        return p
    for base in (cfg_path.parent, MH_ROOT):
        cand = (base / p).resolve()
        if cand.exists():
            return cand
    return (cfg_path.parent / p).resolve()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=MH_ROOT / "configs" / "train_state.yaml")
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--split", choices=["val", "test"], default="test")
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument(
        "--sweep-threshold",
        action="store_true",
        help="Sweep positive-class threshold for binary heads; write thresholds JSON",
    )
    args = ap.parse_args()

    config = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
    schema_path = resolve_path(args.config, config.get("schema_path", "configs/schema_v3.1.yaml"))
    schema = load_schema(str(schema_path))
    config["schema_path"] = str(schema_path)

    data_cfg = config.get("data") or {}
    key = "test" if args.split == "test" else "val"
    data_path = resolve_path(args.config, data_cfg.get(key, f"data/state/state_{key}.jsonl"))
    samples = load_state_jsonl(data_path)
    if not samples:
        raise SystemExit(f"No samples at {data_path}")

    device = get_device(config)
    print(f"device={device}", flush=True)
    model_name = config.get("model_name", "__mock__")
    if model_name != "__mock__":
        mp = resolve_path(args.config, model_name)
        if mp.exists():
            config["model_name"] = str(mp)

    ckpt = torch.load(args.ckpt, map_location=device)
    if ckpt.get("config", {}).get("model_name") == "__mock__":
        config["model_name"] = "__mock__"

    model = StateMultiheadModel.from_config(config).to(device)
    model.load_state_dict(ckpt["model"])
    model.eval()

    loader = DataLoader(
        StateDataset(samples, schema),
        batch_size=int(config.get("batch_size", 16)),
        shuffle=False,
        collate_fn=collate_state,
    )

    y_true = {h.name: [] for h in schema.heads}
    y_pred = {h.name: [] for h in schema.heads}
    # threshold calibration: positives (mask=1) + unknown rows as operational negatives
    calib_true = {h.name: [] for h in schema.heads if len(h.values) == 2}
    calib_prob = {h.name: [] for h in schema.heads if len(h.values) == 2}
    idx2val = {h.name: {i: v for i, v in enumerate(h.values)} for h in schema.heads}

    with torch.no_grad():
        for batch in loader:
            out = model(batch["texts"], device)
            labels_rows = batch.get("labels") or []
            for h in schema.heads:
                logits = out["logits"][h.name]
                pred_i = logits.argmax(-1).tolist()
                masks = batch["head_mask"][h.name].tolist()
                probs = F.softmax(logits, dim=-1)
                for i, (pi, m) in enumerate(zip(pred_i, masks)):
                    lab = (
                        str((labels_rows[i] or {}).get(h.name, "unknown"))
                        if i < len(labels_rows)
                        else "unknown"
                    )
                    if h.name in calib_prob:
                        # operational: fire positive only when confident; unknown ≈ should not fire
                        p_pos = float(probs[i, 0].item())
                        if float(m) >= 0.5 and lab == h.values[0]:
                            calib_true[h.name].append(1)
                            calib_prob[h.name].append(p_pos)
                        elif lab in ("unknown", "") or float(m) < 0.5:
                            calib_true[h.name].append(0)
                            calib_prob[h.name].append(p_pos)

                    if h.name == "IdentityProcess":
                        if lab in ("unknown", ""):
                            continue
                    elif float(m) < 0.5 or lab in ("unknown", ""):
                        continue
                    if lab not in idx2val[h.name].values():
                        continue
                    y_true[h.name].append(lab)
                    y_pred[h.name].append(idx2val[h.name][int(pi)])

    metrics = evaluate_predictions(schema, y_true, y_pred)
    out_dir = args.out_dir or args.ckpt.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"eval_{args.split}"
    (out_dir / f"{stem}.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / f"{stem}.md").write_text(format_metrics_md(metrics, schema), encoding="utf-8")

    summary = {
        k: metrics[k]
        for k in ("macro_f1", "weighted_macro_f1", "macro_f1_by_kind", "n_heads_scored")
    }
    if args.sweep_threshold:
        thr = {}
        for h in schema.heads:
            if h.name not in calib_prob or not calib_prob[h.name]:
                continue
            if len(h.values) != 2:
                continue
            pos_lab, default = h.values[0], h.values[-1]
            y = calib_true[h.name]
            p = calib_prob[h.name]
            best = {"threshold": 0.5, "f1": -1.0, "precision": 0.0, "recall": 0.0}
            for step in range(5, 100, 5):
                t = step / 100.0
                tp = fp = fn = 0
                for yi, pi in zip(y, p):
                    pred = 1 if pi >= t else 0
                    if pred == 1 and yi == 1:
                        tp += 1
                    elif pred == 1 and yi == 0:
                        fp += 1
                    elif pred == 0 and yi == 1:
                        fn += 1
                prec = tp / (tp + fp) if (tp + fp) else 0.0
                rec = tp / (tp + fn) if (tp + fn) else 0.0
                f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
                if f1 > best["f1"]:
                    best = {
                        "threshold": t,
                        "f1": round(f1, 4),
                        "precision": round(prec, 4),
                        "recall": round(rec, 4),
                        "n_pos": int(sum(y)),
                        "n_calib_neg": int(len(y) - sum(y)),
                        "positive_label": pos_lab,
                        "default_label": default,
                        "note": "negatives=unknown/mask0 for operational fire threshold only",
                    }
            thr[h.name] = best
        thr_path = out_dir / f"{stem}_thresholds.json"
        thr_path.write_text(json.dumps(thr, ensure_ascii=False, indent=2), encoding="utf-8")
        summary["binary_thresholds"] = thr
        print(f"wrote {thr_path}")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"wrote {out_dir / (stem + '.md')}")


if __name__ == "__main__":
    main()
