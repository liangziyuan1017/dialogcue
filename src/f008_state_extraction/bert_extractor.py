"""BERT-backed state extraction adapter (optional).

Default pipeline uses DeepSeek (`extraction.provider: llm`). Set
`extraction.provider: bert` (or env ``EXTRACTION_PROVIDER=bert``) only after
replacing :func:`extract_state_bert` with a real model call.

This module must not import torch/transformers at import time so LLM-only
deployments keep working with no BERT dependencies installed.
"""

from __future__ import annotations

import os
from typing import Any

from f007_infrastructure.config import get as _cfg

# Roles used by offline labeling (F000) and online extraction (F008).
ROLE_CUSTOMER = "客户"
ROLE_COLLECTOR = "催收员"

_VALID_PROVIDERS = frozenset({"llm", "bert"})


def get_extraction_provider() -> str:
    """Return ``llm`` (default) or ``bert``.

    Resolution order:
    1. ``EXTRACTION_PROVIDER`` env (``llm`` | ``bert``)
    2. ``extraction.provider`` in config.md
    """
    env = (os.environ.get("EXTRACTION_PROVIDER") or "").strip().lower()
    if env in _VALID_PROVIDERS:
        return env
    raw = str(_cfg("extraction.provider", "llm") or "llm").strip().lower()
    return raw if raw in _VALID_PROVIDERS else "llm"


def extract_state_bert(
    utterance: str,
    *,
    role: str = ROLE_CUSTOMER,
    context_turns: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Extract conversation state from one utterance using a local BERT model.

    ---------------------------------------------------------------------------
    INPUT
    ---------------------------------------------------------------------------
    utterance : str
        Raw turn text (customer or collector), e.g. ``"我现在真的没钱还"``.
    role : str
        ``"客户"`` (customer) or ``"催收员"`` (collector).
        Customer turns typically fill facts / emotions / willingness.
        Collector turns typically fill actions (and leave facts/emotions empty).
    context_turns : list[dict] | None
        Optional prior turns for context-aware models. Each dict matches F000
        dialog turns, e.g. ``{"role": "催收员", "text": "..."}``.
        Online F008 currently passes ``None`` (utterance-only); offline F000
        passes the same window as the LLM path
        (``context_window.analysis_turns_before``).

    ---------------------------------------------------------------------------
    OUTPUT (required keys — same shape as ``extract_state_llm``)
    ---------------------------------------------------------------------------
    {
        "facts": list[str],          # canonical fact group names, e.g. ["financial_hardship"]
        "emotions": list[str],       # canonical emotion group names, e.g. ["distress"]
        "actions": list[str],        # collector action group names, e.g. ["plan_proposal"]
                                     # use [] for customer turns; for collector, usually one label
        "willingness": str | None,   # one of: resistant | weak | conditional |
                                     #          negotiating | strong  (customer); else None
        "confidence": float,         # 0.0–1.0 model confidence
        "method": "bert",            # must be the literal string "bert"
    }

    Prefer **canonical** taxonomy names (post-relabel). If your model emits
    free-form / Chinese tags, map them to canonical names inside this function
    before returning so tree node keys stay stable.

    ---------------------------------------------------------------------------
    INTEGRATION
    ---------------------------------------------------------------------------
    Replace the body below with your inference call, for example::

        model = _load_model()  # lazy singleton from extraction.bert.model_dir
        return model.predict(utterance, role=role, context=context_turns)

    Config keys reserved for you (optional)::

        extraction.bert.model_dir
        extraction.bert.device          # auto | cpu | cuda | mps

    Do not hard-require torch at module import; load inside this function or a
    private ``_load_model()`` so ``provider: llm`` never needs BERT installed.
    """
    _ = (utterance, role, context_turns, _cfg("extraction.bert.model_dir", ""))
    raise NotImplementedError(
        "extract_state_bert is a placeholder. Wire your trained BERT here, then "
        "set extraction.provider: bert (or EXTRACTION_PROVIDER=bert)."
    )
