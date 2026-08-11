"""Val threshold calibration for multitask inference (no training masks)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F


def _f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return prec, rec, f1


def sweep_binary_threshold(
    y_true: list[int],
    p_pos: list[float],
    *,
    steps: range | None = None,
) -> dict[str, Any]:
    """y_true: 1=should fire positive, 0=should not. p_pos: P(positive)."""
    steps = steps or range(5, 100, 5)
    best = {
        "threshold": 0.5,
        "f1": -1.0,
        "precision": 0.0,
        "recall": 0.0,
        "n_pos": int(sum(y_true)),
        "n_neg": int(len(y_true) - sum(y_true)),
    }
    if not y_true:
        best["f1"] = 0.0
        best["note"] = "empty calibration set"
        return best
    for step in steps:
        t = step / 100.0
        tp = fp = fn = 0
        for yi, pi in zip(y_true, p_pos):
            pred = 1 if pi >= t else 0
            if pred == 1 and yi == 1:
                tp += 1
            elif pred == 1 and yi == 0:
                fp += 1
            elif pred == 0 and yi == 1:
                fn += 1
        prec, rec, f1 = _f1(tp, fp, fn)
        if f1 > best["f1"]:
            best = {
                "threshold": t,
                "f1": round(f1, 4),
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "n_pos": int(sum(y_true)),
                "n_neg": int(len(y_true) - sum(y_true)),
            }
    return best


def sweep_abstain_min_prob(
    y_true_idx: list[int],
    probs: list[list[float]],
    *,
    steps: range | None = None,
    min_coverage: float = 0.3,
) -> dict[str, Any]:
    """
    Sweep min confidence: if max_p < t → abstain (counts as wrong).
    Prefer thresholds with coverage >= min_coverage; else best accuracy.
    """
    steps = steps or range(0, 95, 5)
    n = len(y_true_idx)
    if n == 0:
        return {
            "min_prob": 0.0,
            "accuracy": 0.0,
            "coverage": 0.0,
            "n": 0,
            "note": "empty calibration set",
        }
    candidates: list[dict[str, Any]] = []
    for step in steps:
        t = step / 100.0
        correct = 0
        kept = 0
        for yi, pr in zip(y_true_idx, probs):
            conf = max(pr) if pr else 0.0
            if conf < t:
                continue
            kept += 1
            pred = int(max(range(len(pr)), key=lambda i: pr[i]))
            if pred == yi:
                correct += 1
        cov = kept / n
        acc = correct / kept if kept else 0.0
        # score: among sufficient coverage, maximize acc; else soft-penalize
        score = acc if cov >= min_coverage else acc * cov
        candidates.append(
            {
                "min_prob": t,
                "accuracy": round(acc, 4),
                "coverage": round(cov, 4),
                "n_kept": kept,
                "n": n,
                "score": score,
            }
        )
    viable = [c for c in candidates if c["coverage"] >= min_coverage]
    pool = viable or candidates
    best = max(pool, key=lambda c: (c["score"], c["coverage"], -c["min_prob"]))
    return {
        "min_prob": best["min_prob"],
        "accuracy": best["accuracy"],
        "coverage": best["coverage"],
        "n_kept": best["n_kept"],
        "n": best["n"],
        "min_coverage_constraint": min_coverage,
    }


@torch.no_grad()
def collect_calibration_batches(
    model,
    loader,
    *,
    schema,
    emo_vocab: list[str],
    will_vocab: list[str],
    device,
) -> dict[str, Any]:
    """Gather scores for Fact binary fire + Emotion/Will abstain calibration."""
    fact_y: dict[str, list[int]] = {}
    fact_p: dict[str, list[float]] = {}
    for h in schema.heads:
        if h.type == "binary" or (
            len(h.values) == 2 and h.values[-1] in ("none", "no")
        ):
            fact_y[h.name] = []
            fact_p[h.name] = []

    emo_y: list[int] = []
    emo_probs: list[list[float]] = []
    will_y: list[int] = []
    will_probs: list[list[float]] = []
    emo_v2i = {lab: i for i, lab in enumerate(emo_vocab)}
    will_v2i = {lab: i for i, lab in enumerate(will_vocab)}

    for batch in loader:
        out = model(batch["texts"], device)
        labels_rows = batch.get("fact_labels") or []
        for h_name in list(fact_y.keys()):
            h = schema.head_by_name()[h_name]
            probs = F.softmax(out["fact_logits"][h_name].float(), dim=-1)
            masks = batch["fact_mask"][h_name].tolist()
            for i, m in enumerate(masks):
                lab = str((labels_rows[i] or {}).get(h_name, "unknown"))
                p_pos = float(probs[i, 0].item())
                # operational: gold positive vs unknown/mask0 as negative
                if float(m) >= 0.5 and lab == h.values[0]:
                    fact_y[h_name].append(1)
                    fact_p[h_name].append(p_pos)
                elif lab in ("unknown", "") or float(m) < 0.5:
                    fact_y[h_name].append(0)
                    fact_p[h_name].append(p_pos)

        e_probs = F.softmax(out["emotion_logits"].float(), dim=-1)
        w_probs = F.softmax(out["willingness_logits"].float(), dim=-1)
        for i, m in enumerate(batch["emotion_mask"].tolist()):
            if float(m) < 0.5:
                continue
            lab = batch["emotion_label"][i]
            if lab is None or lab not in emo_v2i:
                continue
            emo_y.append(emo_v2i[lab])
            emo_probs.append(e_probs[i].detach().cpu().tolist())
        for i, m in enumerate(batch["willingness_mask"].tolist()):
            if float(m) < 0.5:
                continue
            lab = batch["willingness_label"][i]
            if lab is None or lab not in will_v2i:
                continue
            will_y.append(will_v2i[lab])
            will_probs.append(w_probs[i].detach().cpu().tolist())

    return {
        "fact_y": fact_y,
        "fact_p": fact_p,
        "emo_y": emo_y,
        "emo_probs": emo_probs,
        "will_y": will_y,
        "will_probs": will_probs,
    }


def calibrate_from_collected(
    collected: dict[str, Any],
    schema,
    *,
    checkpoint: str,
    split: str,
) -> dict[str, Any]:
    per_head: dict[str, Any] = {}
    thr_list: list[float] = []
    for h in schema.heads:
        if h.name not in collected["fact_y"]:
            continue
        best = sweep_binary_threshold(
            collected["fact_y"][h.name], collected["fact_p"][h.name]
        )
        best["positive_label"] = h.values[0]
        best["default_label"] = h.values[-1]
        best["note"] = "negatives=unknown/mask0 for operational fire only"
        per_head[h.name] = best
        thr_list.append(float(best["threshold"]))

    global_fact = (
        round(sorted(thr_list)[len(thr_list) // 2], 2) if thr_list else 0.5
    )
    emo = sweep_abstain_min_prob(collected["emo_y"], collected["emo_probs"])
    will = sweep_abstain_min_prob(collected["will_y"], collected["will_probs"])

    return {
        "version": "multitask_v1_thresholds",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "checkpoint": checkpoint,
        "split": split,
        "fact_binary_threshold": global_fact,
        "fact_binary_thresholds_per_head": {
            k: v["threshold"] for k, v in per_head.items()
        },
        "fact_binary_sweep": per_head,
        "emotion_min_prob": float(emo.get("min_prob", 0.0)),
        "willingness_min_prob": float(will.get("min_prob", 0.0)),
        "emotion_sweep": emo,
        "willingness_sweep": will,
    }


def load_thresholds(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_thresholds_path(
    *,
    explicit: Path | None,
    ckpt: Path,
) -> Path | None:
    if explicit is not None:
        return explicit
    cand = ckpt.parent / "thresholds.json"
    return cand if cand.exists() else None


def thresholds_for_decode(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize thresholds.json → kwargs for decode_multitask_output."""
    if not payload:
        return {
            "binary_positive_threshold": 0.5,
            "fact_thresholds_per_head": None,
            "emotion_min_confidence": 0.0,
            "willingness_min_confidence": 0.0,
        }
    return {
        "binary_positive_threshold": float(
            payload.get("fact_binary_threshold", 0.5)
        ),
        "fact_thresholds_per_head": payload.get("fact_binary_thresholds_per_head"),
        "emotion_min_confidence": float(payload.get("emotion_min_prob", 0.0)),
        "willingness_min_confidence": float(
            payload.get("willingness_min_prob", 0.0)
        ),
    }


def write_thresholds(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
