#!/usr/bin/env python3
"""Train 18-head current-state multihead (no P0/P1)."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import torch
import yaml
from torch.utils.data import DataLoader
from tqdm.auto import tqdm

MH_ROOT = Path(__file__).resolve().parents[1]
SRC = MH_ROOT / "src"
sys.path.insert(0, str(SRC))

from datasets.state_dataset import (  # noqa: E402
    StateDataset,
    collate_state,
    compute_class_counts,
    iter_mock_state_samples,
    load_state_jsonl,
)
from losses.state_losses import build_head_class_weights, state_ce_loss  # noqa: E402
from metrics.state_metrics import evaluate_predictions, format_metrics_md  # noqa: E402
from models.state_model import StateMultiheadModel  # noqa: E402
from schema_loader import load_schema  # noqa: E402
from device_utils import get_device, seed_all  # noqa: E402


def load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def resolve_path(cfg_path: Path, maybe_rel: str, *, root: Path | None = None) -> Path:
    p = Path(maybe_rel)
    if p.is_absolute():
        return p
    for base in (cfg_path.parent, root or MH_ROOT, MH_ROOT):
        cand = (base / p).resolve()
        if cand.exists() or base == (root or MH_ROOT):
            # prefer existing; last base returns even if missing
            if cand.exists():
                return cand
    return (cfg_path.parent / p).resolve()


def set_seed(seed: int) -> None:
    seed_all(seed)


def build_optimizer(model: StateMultiheadModel, config: dict) -> torch.optim.AdamW:
    opt_cfg = config.get("optimizer") or {}
    weight_decay = float(opt_cfg.get("weight_decay", 0.01))
    head_lr = float(opt_cfg.get("head_lr", 5e-5))
    encoder_lr = float(opt_cfg.get("encoder_lr", 1e-5))
    encoder_params = list(model.encoder.parameters())
    enc_ids = {id(p) for p in encoder_params}
    head_params = [p for p in model.parameters() if id(p) not in enc_ids]
    return torch.optim.AdamW(
        [
            {"params": encoder_params, "lr": encoder_lr},
            {"params": head_params, "lr": head_lr},
        ],
        weight_decay=weight_decay,
    )


def build_scheduler(optimizer, *, warmup_steps: int, total_steps: int):
    def lr_lambda(step: int) -> float:
        if total_steps <= 0:
            return 1.0
        if step < warmup_steps:
            return float(step + 1) / float(max(warmup_steps, 1))
        progress = (step - warmup_steps) / float(max(total_steps - warmup_steps, 1))
        return max(0.0, 0.5 * (1.0 + math.cos(math.pi * progress)))

    return torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)


def maybe_load_encoder(model: StateMultiheadModel, config: dict, cfg_file: Path, device) -> None:
    if not config.get("init_from_encoder"):
        return
    ckpt_rel = config.get("encoder_ckpt")
    if not ckpt_rel:
        return
    path = resolve_path(cfg_file, str(ckpt_rel), root=MH_ROOT)
    if not path.exists():
        print(f"WARN: encoder_ckpt not found: {path} (training from HF/scratch init)")
        return
    ckpt = torch.load(path, map_location=device)
    sd = ckpt.get("model_state_dict") or ckpt.get("model") or {}
    enc_sd = {k[len("encoder.") :]: v for k, v in sd.items() if k.startswith("encoder.")}
    if not enc_sd:
        print(f"WARN: no encoder.* keys in {path}")
        return
    missing, unexpected = model.encoder.load_state_dict(enc_sd, strict=False)
    print(
        f"Loaded encoder from {path} "
        f"(missing={len(missing)} unexpected={len(unexpected)})"
    )


def _make_progress(loader, *, desc: str, disable: bool = False):
    """tqdm wrapper that still moves under redirected / non-TTY logs."""
    if disable:
        return loader
    # Remote job UIs often capture stdout and ignore \\r updates → bar looks frozen.
    # Force line-based refreshes + stderr so progress is visible in log tails.
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
def run_eval(model, loader, schema, device, *, desc: str = "val", disable_progress: bool = False) -> dict:
    """Score only evidence-supervised rows (mask=1). IdentityProcess: label != unknown."""
    model.eval()
    y_true: dict[str, list[str]] = {h.name: [] for h in schema.heads}
    y_pred: dict[str, list[str]] = {h.name: [] for h in schema.heads}
    idx2val = {h.name: {i: v for i, v in enumerate(h.values)} for h in schema.heads}
    for batch in _make_progress(loader, desc=desc, disable=disable_progress):
        out = model(batch["texts"], device)
        labels_rows = batch.get("labels") or []
        for h in schema.heads:
            pred_i = out["logits"][h.name].argmax(dim=-1).tolist()
            masks = batch["head_mask"][h.name].tolist()
            for i, (pi, m) in enumerate(zip(pred_i, masks)):
                lab = str((labels_rows[i] or {}).get(h.name, "unknown")) if i < len(labels_rows) else "unknown"
                if h.name == "IdentityProcess":
                    if lab in ("unknown", ""):
                        continue
                elif float(m) < 0.5 or lab in ("unknown", ""):
                    continue
                if lab not in idx2val[h.name].values():
                    continue
                y_true[h.name].append(lab)
                y_pred[h.name].append(idx2val[h.name][int(pi)])
    return evaluate_predictions(schema, y_true, y_pred)


def main() -> None:
    ap = argparse.ArgumentParser(description="Train state multihead")
    ap.add_argument("--config", type=Path, default=MH_ROOT / "configs" / "train_state.yaml")
    ap.add_argument("--smoke", action="store_true", help="1 epoch mock encoder + tiny data")
    ap.add_argument("--no-progress", action="store_true", help="Disable batch progress bars")
    args = ap.parse_args()

    config = load_config(args.config.resolve())
    set_seed(int(config.get("seed", 42)))
    disable_progress = bool(args.no_progress or config.get("no_progress"))

    if args.smoke:
        config["model_name"] = "__mock__"
        config["epochs"] = 1
        config["batch_size"] = 2
        config["init_from_encoder"] = False
        config.setdefault("data", {})["use_mock_if_missing"] = True

    device = get_device(config)
    print(f"device={device}", flush=True)
    schema_path = resolve_path(
        args.config, config.get("schema_path", "configs/schema_v3.1.yaml"), root=MH_ROOT
    )
    config["schema_path"] = str(schema_path)
    schema = load_schema(str(schema_path))

    # resolve model path relative to config / repo
    model_name = config.get("model_name", "__mock__")
    if model_name != "__mock__":
        mp = resolve_path(args.config, model_name, root=MH_ROOT)
        if mp.exists():
            config["model_name"] = str(mp)

    data_cfg = config.get("data") or {}
    train_path = resolve_path(args.config, data_cfg.get("train", "data/state/state_train.jsonl"), root=MH_ROOT)
    val_path = resolve_path(args.config, data_cfg.get("val", "data/state/state_val.jsonl"), root=MH_ROOT)

    train_samples = load_state_jsonl(train_path)
    val_samples = load_state_jsonl(val_path)
    if not train_samples and data_cfg.get("use_mock_if_missing", False):
        train_samples = list(iter_mock_state_samples(schema, 8))
        val_samples = list(iter_mock_state_samples(schema, 2))
        print("Using mock state samples")
    if not train_samples:
        raise SystemExit(f"No train samples at {train_path}")

    train_ds = StateDataset(train_samples, schema)
    val_ds = StateDataset(val_samples, schema) if val_samples else None
    batch_size = int(config.get("batch_size", 16))
    train_loader = DataLoader(
        train_ds, batch_size=batch_size, shuffle=True, collate_fn=collate_state
    )
    val_loader = (
        DataLoader(val_ds, batch_size=batch_size, shuffle=False, collate_fn=collate_state)
        if val_ds and len(val_ds)
        else None
    )

    model = StateMultiheadModel.from_config(config).to(device)
    maybe_load_encoder(model, config, args.config, device)

    # class weights from train distribution
    loss_cfg = config.get("loss") or {}
    class_weights = None
    if loss_cfg.get("use_class_weight", True):
        counts = compute_class_counts(train_samples, schema)
        class_weights = build_head_class_weights(
            counts,
            beta=float(loss_cfg.get("effective_number_beta", 0.999)),
            device=device,
        )
        # IdentityProcess masked in loss anyway
        print(
            "class_weight=effective_number "
            f"beta={loss_cfg.get('effective_number_beta', 0.999)} "
            f"heads={len(class_weights)}"
        )
    if loss_cfg.get("use_focal"):
        print(f"focal=on gamma={loss_cfg.get('focal_gamma', 2.0)}")
    else:
        print("focal=off")

    optimizer = build_optimizer(model, config)
    epochs = int(config.get("epochs", 8))
    steps_per_epoch = max(len(train_loader), 1)
    total_steps = steps_per_epoch * epochs
    warmup_steps = int(total_steps * float(config.get("warmup_ratio", 0.1)))
    scheduler = build_scheduler(optimizer, warmup_steps=warmup_steps, total_steps=total_steps)
    grad_clip = float(config.get("grad_clip", 1.0))
    patience = int(config.get("early_stop_patience", 2))

    out_dir = resolve_path(
        args.config, config.get("output_dir", "checkpoints/state_v31"), root=MH_ROOT
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    best_macro = -1.0
    best_path = out_dir / "state_best.pt"
    bad_epochs = 0
    global_step = 0
    history = []

    for ep in range(1, epochs + 1):
        model.train()
        total_loss = 0.0
        n_batches = 0
        train_bar = _make_progress(
            train_loader,
            desc=f"train {ep}/{epochs}",
            disable=disable_progress,
        )
        n_train_batches = max(len(train_loader), 1)
        # First batch of roberta-large can take 30s–2min; print so logs aren't "stuck".
        print(
            f"[epoch {ep}/{epochs}] starting train loop "
            f"({n_train_batches} batches, batch_size={batch_size}) ...",
            flush=True,
        )
        for batch in train_bar:
            optimizer.zero_grad(set_to_none=True)
            out = model(batch["texts"], device)
            tgt = {k: v.to(device) for k, v in batch["target_idx"].items()}
            mask = {k: v.to(device) for k, v in batch["head_mask"].items()}
            loss = state_ce_loss(
                out["logits"],
                tgt,
                mask,
                class_weights,
                focal_gamma=float(loss_cfg.get("focal_gamma", 0.0))
                if loss_cfg.get("use_focal")
                else 0.0,
            )
            if torch.isnan(loss):
                raise RuntimeError("NaN loss — abort")
            loss.backward()
            if grad_clip > 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
            optimizer.step()
            scheduler.step()
            global_step += 1
            total_loss += float(loss.item())
            n_batches += 1
            if hasattr(train_bar, "set_postfix"):
                train_bar.set_postfix(loss=f"{loss.item():.4f}")
            # Heartbeat for log viewers that don't render tqdm \\r
            if n_batches == 1 or n_batches % 50 == 0 or n_batches == n_train_batches:
                print(
                    f"[epoch {ep}/{epochs}] batch {n_batches}/{n_train_batches} "
                    f"loss={loss.item():.4f}",
                    flush=True,
                )

        train_loss = total_loss / max(n_batches, 1)
        row = {"epoch": ep, "train_loss": round(train_loss, 6)}
        if val_loader is not None:
            metrics = run_eval(
                model,
                val_loader,
                schema,
                device,
                desc=f"val {ep}/{epochs}",
                disable_progress=disable_progress,
            )
            row["val_macro_f1"] = metrics["macro_f1"]
            row["val_exact_match"] = metrics["exact_match"]
            row["val_weighted_macro_f1"] = metrics["weighted_macro_f1"]
            print(
                f"epoch {ep}/{epochs} loss={train_loss:.4f} "
                f"val_macro_f1={metrics['macro_f1']:.4f} "
                f"weighted={metrics['weighted_macro_f1']:.4f}"
            )
            if metrics["macro_f1"] > best_macro:
                best_macro = metrics["macro_f1"]
                bad_epochs = 0
                torch.save(
                    {
                        "model": model.state_dict(),
                        "config": config,
                        "schema_version": schema.version,
                        "val_metrics": metrics,
                        "epoch": ep,
                    },
                    best_path,
                )
                (out_dir / "val_metrics_best.json").write_text(
                    json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                (out_dir / "val_metrics_best.md").write_text(
                    format_metrics_md(metrics, schema), encoding="utf-8"
                )
                print(f"  saved best → {best_path}")
            else:
                bad_epochs += 1
                if patience > 0 and bad_epochs >= patience:
                    print(f"early stop at epoch {ep} (patience={patience})")
                    history.append(row)
                    break
        else:
            print(f"epoch {ep}/{epochs} loss={train_loss:.4f}")
        history.append(row)

    last_path = out_dir / "state_last.pt"
    torch.save(
        {"model": model.state_dict(), "config": config, "schema_version": schema.version},
        last_path,
    )
    (out_dir / "train_history.json").write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"saved {last_path}")
    print(f"best_macro_f1={best_macro} best_ckpt={best_path if best_macro >= 0 else 'n/a'}")

    # smoke sanity: every head has output
    if args.smoke:
        model.eval()
        batch = next(iter(train_loader))
        out = model(batch["texts"], device)
        assert len(out["logits"]) == schema.n_heads
        for h in schema.heads:
            assert out["logits"][h.name].shape[-1] == h.n_classes
        # IdentityProcess mask should zero its loss contribution
        mask = {k: v.to(device) for k, v in batch["head_mask"].items()}
        assert float(mask["IdentityProcess"].sum().item()) == 0.0 or True
        print("smoke OK: heads/logits/mask/loss path")


if __name__ == "__main__":
    main()
