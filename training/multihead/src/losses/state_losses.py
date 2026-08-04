"""State multihead losses: CE + head_mask + EN weights + optional focal."""

from __future__ import annotations

import torch
import torch.nn.functional as F


def effective_number_weights(
    counts: list[int],
    *,
    beta: float = 0.999,
    device: torch.device | None = None,
) -> torch.Tensor:
    """
    Cui et al. Class-Balanced Loss: w_c = (1-β) / (1-β^{n_c}).
    Renormalize so mean weight == 1.
    """
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
    *,
    weight: torch.Tensor | None,
    focal_gamma: float,
) -> torch.Tensor:
    """Per-row CE or focal; returns mean over rows."""
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


def state_ce_loss(
    logits_by_head: dict[str, torch.Tensor],
    target_idx_by_head: dict[str, torch.Tensor],
    head_mask: dict[str, torch.Tensor],
    class_weights: dict[str, torch.Tensor] | None = None,
    *,
    focal_gamma: float = 0.0,
) -> torch.Tensor:
    """
    Mean of per-head masked CE (optional focal).
    Heads with mask sum==0 are skipped.
    """
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
            _masked_ce(logits[m], tgt[m], weight=w, focal_gamma=focal_gamma)
        )
    if not losses:
        any_logit = next(iter(logits_by_head.values()))
        return any_logit.sum() * 0.0
    return torch.stack(losses).mean()
