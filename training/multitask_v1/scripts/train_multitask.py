#!/usr/bin/env python3
"""Train multitask v1 (Fact + Emotion + Willingness) — full-data capable.

Parity goals with training/multihead/scripts/train_state.py:
  NPU/CUDA device, encoder warm-start, EN class weights, warmup, grad clip,
  early stop, progress heartbeats, last/best checkpoints + metadata.
Does not modify training/multihead/.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import torch
import yaml
from torch.utils.data import DataLoader

try:
    from tqdm.auto import tqdm
except ImportError:  # pragma: no cover
    tqdm = None  # type: ignore

MT_ROOT = Path(__file__).resolve().parents[1]
SRC = MT_ROOT / "src"
sys.path.insert(0, str(SRC))

from checkpoint_meta import build_checkpoint_metadata  # noqa: E402
from dataset import (  # noqa: E402
    MultitaskDataset,
    collate_multitask,
    compute_fact_class_counts,
    compute_label_counts,
    iter_mock_samples,
    load_jsonl,
)
from device_utils import describe_device_env, get_device, seed_all  # noqa: E402
from labels import emotion_labels, willingness_labels  # noqa: E402
from losses import (  # noqa: E402
    build_head_class_weights,
    effective_number_weights,
    multitask_loss,
)
from metrics_emotion import evaluate_emotion  # noqa: E402
from metrics_fact import evaluate_fact_evidence_only  # noqa: E402
from metrics_willingness import evaluate_willingness  # noqa: E402
from model import MultitaskV1Model  # noqa: E402
from paths import (  # noqa: E402
    DEFAULT_FACT_SCHEMA,
    load_fact_schema,
    load_yaml,
    resolve_under_mt,
)
from report_format import format_multitask_metrics_md  # noqa: E402


def load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def resolve_path(cfg_path: Path, maybe_rel: str, *, root: Path | None = None) -> Path:
    p = Path(maybe_rel)
    if p.is_absolute():
        return p
    root = root or MT_ROOT
    for base in (cfg_path.parent, root, MT_ROOT):
        cand = (base / p).resolve()
        if cand.exists():
            return cand
    return (cfg_path.parent / p).resolve()


def build_scheduler(optimizer, *, warmup_steps: int, total_steps: int):
    def lr_lambda(step: int) -> float:
        if total_steps <= 0:
            return 1.0
        if step < warmup_steps:
            return float(step + 1) / float(max(warmup_steps, 1))
        progress = (step - warmup_steps) / float(max(total_steps - warmup_steps, 1))
        return max(0.0, 0.5 * (1.0 + math.cos(math.pi * progress)))

    return torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)


def maybe_load_encoder(model: MultitaskV1Model, config: dict, cfg_file: Path, device) -> None:
    if not config.get("init_from_encoder"):
        return
    ckpt_rel = config.get("encoder_ckpt")
    if not ckpt_rel:
        return
    path = resolve_path(cfg_file, str(ckpt_rel), root=MT_ROOT)
    if not path.exists():
        print(f"WARN: encoder_ckpt not found: {path} (training from HF/scratch init)", flush=True)
        return
    ckpt = torch.load(path, map_location="cpu")
    sd = ckpt.get("model_state_dict") or ckpt.get("model") or {}
    enc_sd = {k[len("encoder.") :]: v for k, v in sd.items() if k.startswith("encoder.")}
    if not enc_sd:
        # try nested TextEncoder.encoder.*
        enc_sd = {
            k[len("encoder.encoder.") :]: v
            for k, v in sd.items()
            if k.startswith("encoder.encoder.")
        }
    if not enc_sd:
        print(f"WARN: no encoder.* keys in {path}", flush=True)
        return
    target = model.encoder
    # TextEncoder wraps HF as .encoder; mock has no .encoder
    if getattr(target, "encoder", None) is not None:
        missing, unexpected = target.encoder.load_state_dict(enc_sd, strict=False)
    else:
        missing, unexpected = target.load_state_dict(enc_sd, strict=False)
    print(
        f"Loaded encoder from {path} (missing={len(missing)} unexpected={len(unexpected)})",
        flush=True,
    )


def _make_progress(loader, *, desc: str, disable: bool = False):
    if disable or tqdm is None:
        return loader
    kwargs = dict(
        desc=desc,
        disable=False,
        file=sys.stderr,
        dynamic_ncols=True,
        mininterval=1.0,
        miniters=1,
    )
    if not sys.stderr.isatty():
        kwargs["mininterval"] = 5.0
    return tqdm(loader, **kwargs)


@torch.no_grad()
def run_eval(
    model,
    loader,
    *,
    fact_schema,
    emo_vocab,
    will_vocab,
    adj_eval_set,
    device,
    desc: str = "eval",
    disable_progress: bool = False,
) -> dict:
    model.eval()
    fact_true: dict[str, list[str]] = {h.name: [] for h in fact_schema.heads}
    fact_pred: dict[str, list[str]] = {h.name: [] for h in fact_schema.heads}
    idx2val = {h.name: {i: v for i, v in enumerate(h.values)} for h in fact_schema.heads}
    emo_t, emo_p = [], []
    will_t, will_p = [], []

    for batch in _make_progress(loader, desc=desc, disable=disable_progress):
        out = model(batch["texts"], device)
        labels_rows = batch.get("fact_labels") or []
        for h in fact_schema.heads:
            pred_i = out["fact_logits"][h.name].argmax(dim=-1).tolist()
            masks = batch["fact_mask"][h.name].tolist()
            for i, (pi, m) in enumerate(zip(pred_i, masks)):
                lab = str((labels_rows[i] or {}).get(h.name, "unknown"))
                if h.name == "IdentityProcess":
                    if lab in ("unknown", ""):
                        continue
                elif float(m) < 0.5 or lab in ("unknown", ""):
                    continue
                if lab not in idx2val[h.name].values():
                    continue
                fact_true[h.name].append(lab)
                fact_pred[h.name].append(idx2val[h.name][int(pi)])

        e_pred = out["emotion_logits"].argmax(dim=-1).tolist()
        w_pred = out["willingness_logits"].argmax(dim=-1).tolist()
        for i, m in enumerate(batch["emotion_mask"].tolist()):
            if float(m) < 0.5:
                continue
            lab = batch["emotion_label"][i]
            if lab is None:
                continue
            emo_t.append(lab)
            emo_p.append(emo_vocab[int(e_pred[i])])
        for i, m in enumerate(batch["willingness_mask"].tolist()):
            if float(m) < 0.5:
                continue
            lab = batch["willingness_label"][i]
            if lab is None:
                continue
            will_t.append(lab)
            will_p.append(will_vocab[int(w_pred[i])])

    return {
        "fact": evaluate_fact_evidence_only(fact_schema, fact_true, fact_pred),
        "emotion": evaluate_emotion(emo_t, emo_p, emo_vocab, eval_set=adj_eval_set),
        "willingness": evaluate_willingness(will_t, will_p, will_vocab),
    }


def _monitor_score(metrics: dict, monitor: str) -> float:
    emo = metrics.get("emotion") or {}
    will = metrics.get("willingness") or {}
    fact = metrics.get("fact") or {}
    key = (monitor or "emotion_strict_macro_f1").lower()
    table = {
        "emotion_strict_macro_f1": float(emo.get("strict_macro_f1") or 0.0),
        "emotion_strict_accuracy": float(emo.get("strict_accuracy") or 0.0),
        "willingness_macro_f1": float(will.get("macro_f1") or 0.0),
        "fact_weighted_positive_f1": float(fact.get("weighted_positive_f1") or 0.0),
        "fact_macro_f1": float(fact.get("macro_f1") or 0.0),
    }
    if key in table:
        return table[key]
    # alias from yaml save_best_on
    if "emotion" in key and "f1" in key:
        return table["emotion_strict_macro_f1"]
    return table["emotion_strict_macro_f1"]


def main() -> None:
    ap = argparse.ArgumentParser(description="Train multitask v1")
    ap.add_argument(
        "--config",
        type=Path,
        default=MT_ROOT / "configs" / "train_multitask.yaml",
    )
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--no-progress", action="store_true")
    ap.add_argument(
        "--calibrate",
        action="store_true",
        help="After train, sweep val thresholds → <output_dir>/thresholds.json",
    )
    ap.add_argument(
        "--device",
        type=str,
        default=None,
        help='Override config device, e.g. "npu:0" / "cpu"',
    )
    args = ap.parse_args()

    cfg_path = args.config.resolve()
    config = load_config(cfg_path)
    if args.device:
        config["device"] = args.device
    seed_all(int(config.get("seed", 42)))
    disable_progress = bool(args.no_progress or config.get("no_progress"))

    if args.smoke:
        config["model_name"] = "__mock__"
        config["epochs"] = 1
        config["batch_size"] = min(4, int(config.get("batch_size", 8)))
        config["device"] = "cpu"
        config["init_from_encoder"] = False
        data0 = config.setdefault("data", {})
        train_probe = resolve_under_mt(
            data0.get("train_jsonl", "data/multitask_train.jsonl")
        )
        if not train_probe.exists():
            data0["use_mock_if_missing"] = True

    contract_path = resolve_path(
        cfg_path, config.get("contract_path", "configs/contract.yaml")
    )
    contract = load_yaml(contract_path)
    adj_eval_set = str(
        config.get("emotion_adjacent_eval_set")
        or contract.get("emotion_adjacent_eval_set")
        or "all_rule"
    )

    schema_rel = config.get("fact_schema_path") or contract.get("fact_schema_path")
    schema_path = (
        resolve_path(cfg_path, schema_rel) if schema_rel else DEFAULT_FACT_SCHEMA
    )
    if not schema_path.exists():
        schema_path = DEFAULT_FACT_SCHEMA
    fact_schema = load_fact_schema(schema_path)
    emo_vocab = emotion_labels(
        resolve_path(
            cfg_path, config.get("emotion_labels_path", "configs/labels_emotion.yaml")
        )
    )
    will_vocab = willingness_labels(
        resolve_path(
            cfg_path,
            config.get("willingness_labels_path", "configs/labels_willingness.yaml"),
        )
    )

    print(
        f"train config={cfg_path} env=({describe_device_env()})",
        flush=True,
    )
    device = get_device(config)
    print(f"device={device} fact_heads={fact_schema.n_heads}", flush=True)
    if device.type == "cpu" and not args.smoke:
        print(
            "WARN: running on CPU. If you expected NPU, pass --device npu:0 after "
            "`source …/set_env.sh`.",
            flush=True,
        )

    model_name = config.get("model_name", "__mock__")
    if model_name != "__mock__":
        mp = resolve_path(cfg_path, model_name)
        if mp.exists():
            config["model_name"] = str(mp)
            model_name = config["model_name"]

    data_cfg = config.get("data") or {}
    train_path = resolve_path(
        cfg_path, data_cfg.get("train_jsonl", "data/multitask_train.jsonl")
    )
    val_path = resolve_path(
        cfg_path, data_cfg.get("val_jsonl", "data/multitask_val.jsonl")
    )
    train_rows = load_jsonl(train_path)
    val_rows = load_jsonl(val_path)
    if (not train_rows) and data_cfg.get("use_mock_if_missing", False):
        train_rows = list(
            iter_mock_samples(
                fact_schema,
                emotion_vocab=emo_vocab,
                willingness_vocab=will_vocab,
                n=16,
            )
        )
        val_rows = list(
            iter_mock_samples(
                fact_schema,
                emotion_vocab=emo_vocab,
                willingness_vocab=will_vocab,
                n=8,
            )
        )
        print("using mock multitask samples", flush=True)
    if not train_rows:
        raise SystemExit(
            f"No train samples at {train_path}. "
            "Run build_multitask_dataset.py first (use_mock_if_missing=false)."
        )

    train_ds = MultitaskDataset(
        train_rows,
        fact_schema=fact_schema,
        emotion_vocab=emo_vocab,
        willingness_vocab=will_vocab,
    )
    val_ds = (
        MultitaskDataset(
            val_rows,
            fact_schema=fact_schema,
            emotion_vocab=emo_vocab,
            willingness_vocab=will_vocab,
        )
        if val_rows
        else None
    )
    bs = int(config.get("batch_size", 16))
    train_loader = DataLoader(
        train_ds, batch_size=bs, shuffle=True, collate_fn=collate_multitask
    )
    val_loader = (
        DataLoader(val_ds, batch_size=bs, shuffle=False, collate_fn=collate_multitask)
        if val_ds and len(val_ds)
        else None
    )

    model = MultitaskV1Model(
        model_name,
        fact_schema=fact_schema,
        emotion_vocab=emo_vocab,
        willingness_vocab=will_vocab,
        max_length=int(config.get("max_length", 256)),
    ).to(device)
    maybe_load_encoder(model, config, cfg_path, device)

    loss_cfg = config.get("loss") or {}
    fact_class_weights = None
    emo_w = None
    will_w = None
    if loss_cfg.get("use_class_weight", True):
        beta = float(loss_cfg.get("effective_number_beta", 0.999))
        fact_counts = compute_fact_class_counts(train_rows, fact_schema)
        fact_class_weights = build_head_class_weights(
            fact_counts, beta=beta, device=device
        )
        emo_w = effective_number_weights(
            compute_label_counts(train_rows, emo_vocab, kind="emotion"),
            beta=beta,
            device=device,
        )
        will_w = effective_number_weights(
            compute_label_counts(train_rows, will_vocab, kind="willingness"),
            beta=beta,
            device=device,
        )
        print(
            f"class_weight=effective_number beta={beta} "
            f"fact_heads={len(fact_class_weights)}",
            flush=True,
        )
    fact_focal = (
        float(loss_cfg.get("focal_gamma", 2.0)) if loss_cfg.get("use_focal") else 0.0
    )
    print(f"fact_focal={'on' if fact_focal > 0 else 'off'} gamma={fact_focal}", flush=True)

    opt_cfg = config.get("optimizer") or {}
    enc_params = list(model.encoder.parameters())
    enc_ids = {id(p) for p in enc_params}
    head_params = [p for p in model.parameters() if id(p) not in enc_ids]
    optim = torch.optim.AdamW(
        [
            {"params": enc_params, "lr": float(opt_cfg.get("encoder_lr", 1e-5))},
            {"params": head_params, "lr": float(opt_cfg.get("head_lr", 5e-5))},
        ],
        weight_decay=float(opt_cfg.get("weight_decay", 0.01)),
    )
    epochs = int(config.get("epochs", 8))
    steps_per_epoch = max(len(train_loader), 1)
    total_steps = steps_per_epoch * epochs
    warmup_steps = int(total_steps * float(config.get("warmup_ratio", 0.1)))
    scheduler = build_scheduler(
        optim, warmup_steps=warmup_steps, total_steps=total_steps
    )
    grad_clip = float(config.get("grad_clip", 1.0))
    patience = int(config.get("early_stop_patience", 2))
    tw = config.get("task_weights") or {"fact": 1.0, "emotion": 1.0, "willingness": 1.0}
    monitor = str(
        config.get("monitor", {}).get("metric")
        if isinstance(config.get("monitor"), dict)
        else config.get("save_best_on", "emotion_strict_macro_f1")
    )

    out_dir = resolve_path(
        cfg_path, config.get("output_dir", "checkpoints/multitask_v1")
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    best_path = out_dir / "multitask_best.pt"
    last_path = out_dir / "multitask_last.pt"

    best_score = -1.0
    bad_epochs = 0
    history: list[dict] = []

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0
        n_batches = 0
        n_train_batches = max(len(train_loader), 1)
        print(
            f"[epoch {epoch}/{epochs}] starting train loop "
            f"({n_train_batches} batches, batch_size={bs}) ...",
            flush=True,
        )
        train_bar = _make_progress(
            train_loader,
            desc=f"train {epoch}/{epochs}",
            disable=disable_progress,
        )
        for batch in train_bar:
            optim.zero_grad(set_to_none=True)
            out = model(batch["texts"], device)
            loss, _parts = multitask_loss(
                fact_logits=out["fact_logits"],
                fact_target={k: v.to(device) for k, v in batch["fact_target"].items()},
                fact_mask={k: v.to(device) for k, v in batch["fact_mask"].items()},
                emotion_logits=out["emotion_logits"],
                emotion_target=batch["emotion_target"].to(device),
                emotion_mask=batch["emotion_mask"].to(device),
                willingness_logits=out["willingness_logits"],
                willingness_target=batch["willingness_target"].to(device),
                willingness_mask=batch["willingness_mask"].to(device),
                task_weights=tw,
                fact_class_weights=fact_class_weights,
                emotion_class_weight=emo_w,
                willingness_class_weight=will_w,
                fact_focal_gamma=fact_focal,
            )
            if torch.isnan(loss):
                raise RuntimeError("NaN loss — abort")
            loss.backward()
            if grad_clip > 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
            optim.step()
            scheduler.step()
            total_loss += float(loss.item())
            n_batches += 1
            if hasattr(train_bar, "set_postfix"):
                train_bar.set_postfix(loss=f"{loss.item():.4f}")
            if n_batches == 1 or n_batches % 50 == 0 or n_batches == n_train_batches:
                print(
                    f"[epoch {epoch}/{epochs}] batch {n_batches}/{n_train_batches} "
                    f"loss={loss.item():.4f}",
                    flush=True,
                )

        avg = total_loss / max(n_batches, 1)
        row: dict = {"epoch": epoch, "train_loss": round(avg, 6)}
        if val_loader is not None:
            metrics = run_eval(
                model,
                val_loader,
                fact_schema=fact_schema,
                emo_vocab=emo_vocab,
                will_vocab=will_vocab,
                adj_eval_set=adj_eval_set,
                device=device,
                desc=f"val {epoch}/{epochs}",
                disable_progress=disable_progress,
            )
            score = _monitor_score(metrics, monitor)
            row["monitor"] = monitor
            row["monitor_score"] = score
            row["emo_strict_macro_f1"] = metrics["emotion"].get("strict_macro_f1")
            row["emo_adj_accuracy"] = metrics["emotion"].get("adj_accuracy")
            row["will_macro_f1"] = metrics["willingness"].get("macro_f1")
            row["fact_weighted_positive_f1"] = metrics["fact"].get(
                "weighted_positive_f1"
            )
            print(
                f"epoch={epoch} train_loss={avg:.4f} "
                f"monitor[{monitor}]={score:.4f} "
                f"emo_strict_f1={metrics['emotion'].get('strict_macro_f1')} "
                f"emo_adj_acc={metrics['emotion'].get('adj_accuracy')} "
                f"will_f1={metrics['willingness'].get('macro_f1')} "
                f"fact_wpos_f1={metrics['fact'].get('weighted_positive_f1')}",
                flush=True,
            )
            if score >= best_score:
                best_score = score
                bad_epochs = 0
                meta = build_checkpoint_metadata(
                    contract=contract,
                    model_name=str(config.get("model_name")),
                    hidden_size=model.hidden_size,
                    fact_schema_path=str(schema_path),
                    fact_schema_version=str(getattr(fact_schema, "version", "")),
                    task_weights={k: float(v) for k, v in tw.items()},
                    emotion_adjacent_eval_set=adj_eval_set,
                    dataset_version=str(
                        config.get("dataset_version") or "multitask_v1_window4x200"
                    ),
                    code_version=str(config.get("code_version") or "multitask_v1"),
                    train_jsonl=str(train_path),
                    tokenizer_name=str(config.get("model_name")),
                    extra={
                        "train_config": {
                            "epochs": epochs,
                            "batch_size": bs,
                            "warmup_ratio": config.get("warmup_ratio"),
                            "grad_clip": grad_clip,
                            "loss": loss_cfg,
                            "monitor": monitor,
                        }
                    },
                )
                torch.save(
                    {
                        "model_state_dict": model.state_dict(),
                        "model": model.state_dict(),
                        "metadata": meta,
                        "config": config,
                        "metrics": metrics,
                        "epoch": epoch,
                    },
                    best_path,
                )
                (out_dir / "metadata.json").write_text(
                    json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                (out_dir / "val_metrics_best.json").write_text(
                    json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                (out_dir / "val_metrics_best.md").write_text(
                    format_multitask_metrics_md(
                        metrics, metadata=meta, split="val"
                    ),
                    encoding="utf-8",
                )
                print(f"  saved best → {best_path}", flush=True)
            else:
                bad_epochs += 1
                if patience > 0 and bad_epochs >= patience:
                    print(
                        f"early stop at epoch {epoch} (patience={patience})",
                        flush=True,
                    )
                    history.append(row)
                    break
        else:
            print(f"epoch={epoch} train_loss={avg:.4f} (no val)", flush=True)
        history.append(row)

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "model": model.state_dict(),
            "config": config,
            "schema_version": getattr(fact_schema, "version", ""),
        },
        last_path,
    )
    (out_dir / "train_history.json").write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"saved {last_path}", flush=True)
    print(
        f"done. best_monitor={best_score} ckpt={best_path if best_score >= 0 else 'n/a'}",
        flush=True,
    )

    if args.calibrate and best_path.exists() and val_loader is not None:
        from threshold_calib import (  # local import
            calibrate_from_collected,
            collect_calibration_batches,
            write_thresholds,
        )

        print("calibrating thresholds on val ...", flush=True)
        model.eval()
        # reload best weights for calibration
        best_ckpt = torch.load(best_path, map_location="cpu")
        state = best_ckpt.get("model_state_dict") or best_ckpt.get("model")
        model.load_state_dict(state)
        model.to(device)
        collected = collect_calibration_batches(
            model,
            val_loader,
            schema=fact_schema,
            emo_vocab=emo_vocab,
            will_vocab=will_vocab,
            device=device,
        )
        thr_payload = calibrate_from_collected(
            collected,
            fact_schema,
            checkpoint=str(best_path),
            split="val",
        )
        thr_path = out_dir / "thresholds.json"
        write_thresholds(thr_path, thr_payload)
        print(
            f"wrote {thr_path} "
            f"fact_thr={thr_payload['fact_binary_threshold']} "
            f"emo_min={thr_payload['emotion_min_prob']} "
            f"will_min={thr_payload['willingness_min_prob']}",
            flush=True,
        )

    if args.smoke:
        model.eval()
        batch = next(iter(train_loader))
        out = model(batch["texts"], device)
        assert len(out["fact_logits"]) == fact_schema.n_heads
        assert out["emotion_logits"].shape[-1] == 11
        assert out["willingness_logits"].shape[-1] == 5
        print("smoke OK: heads/logits path", flush=True)


if __name__ == "__main__":
    main()
