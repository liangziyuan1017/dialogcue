"""Multitask losses — Fact masked multihead CE (+ EN/focal); Emotion/Will CE; no adj in v1."""

from __future__ import annotations

import torch
import torch.nn.functional as F


def effective_number_weights(
    counts: list[int],
    *,
    beta: float = 0.999,
    device: torch.device | None = None,
) -> torch.Tensor:
    ws: list[float] = []
    for n in counts:
        n = max(int(n), 0)
        if n <= 0:
            ws.append(1.0)
            continue
        numer = 1.0 - beta
        denom = 1.0 - (beta**n)
        ws.append(numer / denom if denom > 1e-12 else 1.0)
    t = torch.tensor(ws, dtype=torch.float32, device=device)
    mean = float(t.mean().item()) if t.numel() else 1.0
    if mean > 0:
        t = t / mean
    return t


def build_head_class_weights(
    counts_by_head: dict[str, list[int]],
    *,
    beta: float = 0.999,
    device: torch.device | None = None,
) -> dict[str, torch.Tensor]:
    return {
        name: effective_number_weights(counts, beta=beta, device=device)
        for name, counts in counts_by_head.items()
    }


def _masked_ce(
    logits: torch.Tensor,
    tgt: torch.Tensor,
    mask: torch.Tensor | None = None,
    *,
    weight: torch.Tensor | None = None,
    focal_gamma: float = 0.0,
) -> torch.Tensor:
    if mask is not None:
        m = mask > 0
        if m.sum() == 0:
            return logits.sum() * 0.0
        logits = logits[m]
        tgt = tgt[m]
    if focal_gamma <= 0:
        return F.cross_entropy(logits, tgt.long(), weight=weight)
    log_probs = F.log_softmax(logits, dim=-1)
    gather = log_probs.gather(1, tgt.long().unsqueeze(1)).squeeze(1)
    pt = gather.exp().clamp(min=1e-8)
    focal = (1.0 - pt).pow(focal_gamma)
    per = -focal * gather
    if weight is not None:
        per = per * weight[tgt.long()]
    return per.mean()


def fact_masked_ce_loss(
    logits_by_head: dict[str, torch.Tensor],
    target_idx_by_head: dict[str, torch.Tensor],
    head_mask: dict[str, torch.Tensor],
    class_weights: dict[str, torch.Tensor] | None = None,
    *,
    focal_gamma: float = 0.0,
) -> torch.Tensor:
    """Mean of per-head masked CE. Unknown/missing must have mask=0."""
    losses: list[torch.Tensor] = []
    for name, logits in logits_by_head.items():
        mask = head_mask.get(name)
        tgt = target_idx_by_head.get(name)
        if mask is None or tgt is None:
            continue
        m = mask > 0
        if m.sum() == 0:
            continue
        w = None if class_weights is None else class_weights.get(name)
        losses.append(
            _masked_ce(
                logits[m],
                tgt[m],
                weight=w,
                focal_gamma=focal_gamma,
            )
        )
    if not losses:
        any_logit = next(iter(logits_by_head.values()))
        return any_logit.sum() * 0.0
    return torch.stack(losses).mean()


def multitask_loss(
    *,
    fact_logits: dict[str, torch.Tensor],
    fact_target: dict[str, torch.Tensor],
    fact_mask: dict[str, torch.Tensor],
    emotion_logits: torch.Tensor,
    emotion_target: torch.Tensor,
    emotion_mask: torch.Tensor,
    willingness_logits: torch.Tensor,
    willingness_target: torch.Tensor,
    willingness_mask: torch.Tensor,
    task_weights: dict[str, float] | None = None,
    fact_class_weights: dict[str, torch.Tensor] | None = None,
    emotion_class_weight: torch.Tensor | None = None,
    willingness_class_weight: torch.Tensor | None = None,
    fact_focal_gamma: float = 0.0,
) -> tuple[torch.Tensor, dict[str, float]]:
    """
    L = w_f L_fact + w_e L_emotion + w_w L_willingness.
    adjacency loss intentionally absent in v1.
    """
    tw = task_weights or {"fact": 1.0, "emotion": 1.0, "willingness": 1.0}
    l_fact = fact_masked_ce_loss(
        fact_logits,
        fact_target,
        fact_mask,
        fact_class_weights,
        focal_gamma=fact_focal_gamma,
    )
    l_emo = _masked_ce(
        emotion_logits,
        emotion_target,
        emotion_mask,
        weight=emotion_class_weight,
    )
    l_will = _masked_ce(
        willingness_logits,
        willingness_target,
        willingness_mask,
        weight=willingness_class_weight,
    )
    total = (
        float(tw.get("fact", 1.0)) * l_fact
        + float(tw.get("emotion", 1.0)) * l_emo
        + float(tw.get("willingness", 1.0)) * l_will
    )
    parts = {
        "fact": float(l_fact.detach().item()),
        "emotion": float(l_emo.detach().item()),
        "willingness": float(l_will.detach().item()),
        "total": float(total.detach().item()),
    }
    return total, parts
