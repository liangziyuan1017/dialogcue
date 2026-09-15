"""BERT-backed state extraction via multitask_v1 (Bert_training).

Default pipeline uses DeepSeek (``extraction.provider: llm``). Set
``extraction.provider: bert`` (or env ``EXTRACTION_PROVIDER=bert``) after
pointing ``extraction.bert.model_dir`` at a multitask checkpoint and
``extraction.bert.multitask_root`` at ``training/multitask_v1``.

Torch / transformers are loaded only inside the multitask adapter, so
LLM-only deployments keep working with ``provider: llm``.

See ``docs/features/F008-bert-multitask-bridge.md``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

ROLE_CUSTOMER = "客户"
ROLE_COLLECTOR = "催收员"

_VALID_PROVIDERS = frozenset({"llm", "bert"})


def _cfg(key: str, default: Any = None) -> Any:
    try:
        from f007_infrastructure.config import get as cfg_get

        return cfg_get(key, default)
    except Exception:
        return default


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


def _multitask_root() -> Path:
    env = (os.environ.get("MULTITASK_V1_ROOT") or "").strip()
    if env:
        return Path(env).resolve()
    raw = str(_cfg("extraction.bert.multitask_root", "") or "").strip()
    if raw:
        return Path(raw).resolve()
    here = Path(__file__).resolve()
    for cand in (
        here.parents[2] / "training" / "multitask_v1",
        Path.cwd() / "training" / "multitask_v1",
    ):
        if (cand / "src" / "f008_compat.py").exists():
            return cand.resolve()
    raise RuntimeError(
        "Cannot find multitask_v1. Set extraction.bert.multitask_root or "
        "MULTITASK_V1_ROOT to the Bert_training training/multitask_v1 directory. "
        "See docs/features/F008-bert-multitask-bridge.md."
    )


def _ensure_compat_on_path() -> None:
    root = _multitask_root()
    src = root / "src"
    if not (src / "f008_compat.py").exists():
        raise RuntimeError(f"f008_compat.py missing under {src}")
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def extract_state_bert(
    utterance: str,
    *,
    role: str = ROLE_CUSTOMER,
    context_turns: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Extract conversation state using multitask_v1 BERT checkpoint.

    Output shape matches ``extract_state_llm``::

        {
            "facts": list[str],
            "emotions": list[str],
            "actions": list[str],
            "willingness": str | None,
            "confidence": float,
            "method": "bert",
        }

    Config::

        extraction.bert.model_dir
        extraction.bert.device
        extraction.bert.multitask_root
        extraction.bert.fact_map_path       # optional
        extraction.bert.thresholds_path    # optional
        extraction.bert.train_config       # optional
    """
    _ensure_compat_on_path()
    from f008_compat import extract_state_bert as _predict  # noqa: WPS433

    model_dir = (
        os.environ.get("EXTRACTION_BERT_MODEL_DIR")
        or str(_cfg("extraction.bert.model_dir", "") or "")
    ).strip()
    if not model_dir:
        raise RuntimeError(
            "extraction.bert.model_dir (or EXTRACTION_BERT_MODEL_DIR) is empty. "
            "Point it at multitask_best.pt or its parent directory."
        )
    device = str(_cfg("extraction.bert.device", "auto") or "auto")
    fact_map = str(_cfg("extraction.bert.fact_map_path", "") or "").strip() or None
    thresholds = str(_cfg("extraction.bert.thresholds_path", "") or "").strip() or None
    train_cfg = str(_cfg("extraction.bert.train_config", "") or "").strip() or None

    return _predict(
        utterance,
        role=role,
        context_turns=context_turns,
        model_dir=model_dir,
        device=device,
        train_config=train_cfg,
        fact_map_path=fact_map,
        thresholds_path=thresholds,
    )
