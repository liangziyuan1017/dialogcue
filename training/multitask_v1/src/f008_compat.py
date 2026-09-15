"""SCBGE main F008-compatible state extraction from multitask_v1.

Matches ``origin/main`` contract in ``src/f008_state_extraction/bert_extractor.py``:

    extract_state_bert(utterance, *, role=ROLE_CUSTOMER, context_turns=None)
        -> {facts, emotions, actions, willingness, confidence, method: \"bert\"}

This module must stay importable without loading torch until
``MultitaskBertRuntime`` / ``extract_state_bert`` actually runs inference.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

ROLE_CUSTOMER = "客户"
ROLE_COLLECTOR = "催收员"

_VALID_ROLES = frozenset({ROLE_CUSTOMER, ROLE_COLLECTOR, "customer", "collector"})

_MT_SRC = Path(__file__).resolve().parent
_MT_ROOT = _MT_SRC.parent
_DEFAULT_FACT_MAP = _MT_ROOT / "configs" / "f008_fact_group_map.yaml"
_DEFAULT_TRAIN_CFG = _MT_ROOT / "configs" / "train_multitask.yaml"

_runtime = None  # MultitaskBertRuntime | None
_runtime_key: tuple[str, str, str] | None = None


def _pascal_to_snake(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def normalize_role(role: str | None) -> str:
    r = (role or ROLE_CUSTOMER).strip()
    low = r.lower()
    if r == ROLE_COLLECTOR or low in ("collector", "agent", "催收"):
        return ROLE_COLLECTOR
    if r == ROLE_CUSTOMER or low in ("customer", "client", "债务人"):
        return ROLE_CUSTOMER
    if r in _VALID_ROLES:
        return ROLE_COLLECTOR if "collect" in low or r == ROLE_COLLECTOR else ROLE_CUSTOMER
    return ROLE_CUSTOMER


def _speaker_tag(role: str) -> str:
    return "collector" if normalize_role(role) == ROLE_COLLECTOR else "customer"


def load_fact_group_map(path: str | Path | None = None) -> dict[str, str]:
    """Load Head / Head.value → canonical SCBGE fact group name."""
    p = Path(path) if path else _DEFAULT_FACT_MAP
    if not p.exists():
        return {}
    # local yaml load without importing paths (keeps torch-free import)
    import yaml

    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    m = raw.get("map") or {}
    return {str(k): str(v) for k, v in m.items()}


def map_active_fact(
    head: str,
    value: str,
    fact_map: dict[str, str] | None = None,
) -> str:
    """Map one active Fact head prediction to a canonical group name."""
    fmap = fact_map if fact_map is not None else load_fact_group_map()
    key_hv = f"{head}.{value}"
    if key_hv in fmap:
        return fmap[key_hv]
    if head in fmap:
        return fmap[head]
    snake = _pascal_to_snake(head)
    # binary-ish positives: just the head snake name
    if value in ("yes", "disrupted", "unavailable", "denying"):
        return snake
    return f"{snake}_{value}"


def decoded_to_f008_state(
    decoded: dict[str, Any],
    *,
    role: str = ROLE_CUSTOMER,
    fact_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Convert ``decode_multitask_output`` result → F008 extract_state_bert dict."""
    role_n = normalize_role(role)
    fmap = fact_map if fact_map is not None else load_fact_group_map()

    facts: list[str] = []
    fact_confs: list[float] = []
    for head, info in (decoded.get("fact_active") or {}).items():
        if info.get("excluded_from_train"):
            continue
        value = str(info.get("value") or "")
        tag = map_active_fact(head, value, fmap)
        if tag and tag not in facts:
            facts.append(tag)
        try:
            fact_confs.append(float(info.get("prob") or 0.0))
        except (TypeError, ValueError):
            pass

    emotions: list[str] = []
    emo = decoded.get("emotion") or {}
    emo_label = emo.get("label")
    emo_prob = float(emo.get("prob") or 0.0)
    if emo_label and not emo.get("abstain"):
        emotions.append(str(emo_label))

    willingness = None
    will = decoded.get("willingness") or {}
    will_label = will.get("label")
    will_prob = float(will.get("prob") or 0.0)
    if will_label and not will.get("abstain"):
        willingness = str(will_label)

    # Multitask v1 has no collector-action head; keep empty for collector turns.
    actions: list[str] = []

    if role_n == ROLE_COLLECTOR:
        # Collector turns: do not invent customer state; only actions (none yet).
        facts = []
        emotions = []
        willingness = None
        conf_parts = [0.0]
    else:
        conf_parts = list(fact_confs)
        if emotions:
            conf_parts.append(emo_prob)
        if willingness is not None:
            conf_parts.append(will_prob)
        if not conf_parts:
            conf_parts = [emo_prob, will_prob]

    confidence = round(sum(conf_parts) / max(len(conf_parts), 1), 4)
    confidence = max(0.0, min(1.0, confidence))

    return {
        "facts": facts,
        "emotions": emotions,
        "actions": actions,
        "willingness": willingness,
        "confidence": confidence,
        "method": "bert",
    }


def build_context_window(
    utterance: str,
    *,
    role: str = ROLE_CUSTOMER,
    context_turns: list[dict[str, Any]] | None = None,
    max_turns: int = 4,
    max_chars: int = 200,
) -> str:
    """Build multitask context_window text from F008-style turns + current utterance."""
    role_n = normalize_role(role)
    turns: list[dict[str, Any]] = []
    if context_turns:
        for i, t in enumerate(context_turns):
            if not isinstance(t, dict):
                continue
            text = str(t.get("text") or t.get("utterance") or "").strip()
            if not text:
                continue
            r = t.get("role") or t.get("speaker") or ROLE_CUSTOMER
            turns.append(
                {
                    "turn_id": int(t.get("turn_id", i)),
                    "speaker": _speaker_tag(str(r)),
                    "text": text,
                }
            )

    anchor_id = len(turns)
    turns.append(
        {
            "turn_id": anchor_id,
            "speaker": _speaker_tag(role_n),
            "text": str(utterance or "").strip(),
        }
    )

    # Lazy import encode only when building (torch not required here)
    import sys

    if str(_MT_SRC) not in sys.path:
        sys.path.insert(0, str(_MT_SRC))
    from context import encode_window  # noqa: WPS433

    class _T:
        def __init__(self, d: dict[str, Any]):
            self.turn_id = int(d["turn_id"])
            self.speaker = str(d["speaker"])
            self.text = str(d["text"])

    objs = [_T(t) for t in turns]
    win = encode_window(objs, len(objs) - 1, max_turns=max_turns, max_chars=max_chars)
    return win.text


class MultitaskBertRuntime:
    """Lazy-loaded multitask_v1 checkpoint used by extract_state_bert."""

    def __init__(
        self,
        *,
        model_dir: str | Path,
        device: str = "auto",
        train_config: str | Path | None = None,
        fact_map_path: str | Path | None = None,
        thresholds_path: str | Path | None = None,
    ):
        self.model_dir = Path(model_dir)
        self.device_spec = device
        self.train_config = Path(train_config) if train_config else _DEFAULT_TRAIN_CFG
        self.fact_map_path = Path(fact_map_path) if fact_map_path else _DEFAULT_FACT_MAP
        self.thresholds_path = Path(thresholds_path) if thresholds_path else None
        self._loaded = False
        self._model = None
        self._device = None
        self._schema = None
        self._emo_vocab: list[str] = []
        self._will_vocab: list[str] = []
        self._decode_kw: dict[str, Any] = {}
        self._max_turns = 4
        self._max_chars = 200
        self._fact_map: dict[str, str] = {}

    def _resolve_ckpt(self) -> Path:
        d = self.model_dir
        if d.is_file() and d.suffix in {".pt", ".pth", ".bin"}:
            return d
        for name in (
            "multitask_best.pt",
            "best.pt",
            "model.pt",
            "pytorch_model.bin",
        ):
            cand = d / name
            if cand.exists():
                return cand
        pts = sorted(d.glob("*.pt"))
        if pts:
            return pts[0]
        raise FileNotFoundError(
            f"no multitask checkpoint under {d} "
            "(expected multitask_best.pt or a .pt file)"
        )

    def load(self) -> None:
        if self._loaded:
            return
        import sys

        if str(_MT_SRC) not in sys.path:
            sys.path.insert(0, str(_MT_SRC))

        import torch
        from device_utils import get_device
        from labels import emotion_labels, willingness_labels
        from model import MultitaskV1Model
        from paths import DEFAULT_FACT_SCHEMA, load_fact_schema, load_yaml, resolve_from_cfg
        from threshold_calib import (
            load_thresholds,
            resolve_thresholds_path,
            thresholds_for_decode,
        )

        cfg_path = self.train_config.resolve()
        config = load_yaml(cfg_path) if cfg_path.exists() else {}
        contract_rel = config.get("contract_path", "configs/contract.yaml")
        contract_path = resolve_from_cfg(cfg_path.parent, contract_rel)
        contract = load_yaml(contract_path) if contract_path.exists() else {}
        ctx = contract.get("context") or config.get("context") or {}
        self._max_turns = int(ctx.get("max_turns", 4))
        self._max_chars = int(ctx.get("max_chars", 200))

        schema_rel = config.get("fact_schema_path") or contract.get("fact_schema_path")
        schema_path = (
            resolve_from_cfg(cfg_path.parent, schema_rel)
            if schema_rel
            else DEFAULT_FACT_SCHEMA
        )
        if not schema_path.exists():
            schema_path = DEFAULT_FACT_SCHEMA
        self._schema = load_fact_schema(schema_path)
        self._emo_vocab = emotion_labels(
            resolve_from_cfg(
                cfg_path.parent,
                config.get("emotion_labels_path", "configs/labels_emotion.yaml"),
            )
        )
        self._will_vocab = willingness_labels(
            resolve_from_cfg(
                cfg_path.parent,
                config.get("willingness_labels_path", "configs/labels_willingness.yaml"),
            )
        )
        self._fact_map = load_fact_group_map(self.fact_map_path)

        ckpt_path = self._resolve_ckpt()
        ckpt = torch.load(ckpt_path, map_location="cpu")
        meta = ckpt.get("metadata") or {}
        ckpt_cfg = ckpt.get("config") or {}
        model_name = (
            (meta.get("model") or {}).get("encoder")
            or ckpt_cfg.get("model_name")
            or config.get("model_name", "__mock__")
        )
        if model_name != "__mock__":
            mp = resolve_from_cfg(cfg_path.parent, str(model_name))
            if mp.exists():
                model_name = str(mp)
        if (meta.get("model") or {}).get("encoder") == "__mock__" or ckpt_cfg.get(
            "model_name"
        ) == "__mock__":
            model_name = "__mock__"

        # Serve-time "auto" must probe local HW — do NOT inherit train.yaml's npu:0
        # (that would hard-fail on machines without torch_npu).
        if self.device_spec and str(self.device_spec).strip().lower() not in ("", "auto"):
            self._device = get_device({"device": self.device_spec})
        else:
            self._device = get_device(None)

        model = MultitaskV1Model(
            model_name,
            fact_schema=self._schema,
            emotion_vocab=self._emo_vocab,
            willingness_vocab=self._will_vocab,
            max_length=int(config.get("max_length", 256)),
        )
        state = ckpt.get("model_state_dict") or ckpt.get("model")
        if state is None:
            raise RuntimeError(f"checkpoint missing weights: {ckpt_path}")
        model.load_state_dict(state)
        model.to(self._device)
        model.eval()
        self._model = model

        thr_path = resolve_thresholds_path(
            explicit=self.thresholds_path, ckpt=ckpt_path
        )
        self._decode_kw = thresholds_for_decode(load_thresholds(thr_path))
        self._loaded = True

    def predict(
        self,
        utterance: str,
        *,
        role: str = ROLE_CUSTOMER,
        context_turns: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self.load()
        import torch
        from infer_decode import decode_multitask_output

        text = build_context_window(
            utterance,
            role=role,
            context_turns=context_turns,
            max_turns=self._max_turns,
            max_chars=self._max_chars,
        )
        if not text.strip():
            return {
                "facts": [],
                "emotions": [],
                "actions": [],
                "willingness": None,
                "confidence": 0.0,
                "method": "bert",
            }

        with torch.no_grad():
            out = self._model([text], self._device)
            decoded = decode_multitask_output(
                out,
                schema=self._schema,
                emotion_vocab=self._emo_vocab,
                willingness_vocab=self._will_vocab,
                batch_index=0,
                **self._decode_kw,
            )
        return decoded_to_f008_state(
            decoded, role=role, fact_map=self._fact_map
        )


def get_runtime(
    *,
    model_dir: str | Path | None = None,
    device: str = "auto",
    train_config: str | Path | None = None,
    fact_map_path: str | Path | None = None,
    thresholds_path: str | Path | None = None,
    force_reload: bool = False,
) -> MultitaskBertRuntime:
    """Process-wide singleton keyed by (model_dir, device, thresholds)."""
    global _runtime, _runtime_key
    md = str(
        model_dir
        or os.environ.get("EXTRACTION_BERT_MODEL_DIR")
        or os.environ.get("MULTITASK_CKPT_DIR")
        or ""
    ).strip()
    if not md:
        raise RuntimeError(
            "model_dir required: pass model_dir= or set EXTRACTION_BERT_MODEL_DIR "
            "/ MULTITASK_CKPT_DIR to the multitask checkpoint directory or .pt file"
        )
    key = (md, str(device), str(thresholds_path or ""))
    if force_reload or _runtime is None or _runtime_key != key:
        _runtime = MultitaskBertRuntime(
            model_dir=md,
            device=device,
            train_config=train_config,
            fact_map_path=fact_map_path,
            thresholds_path=thresholds_path,
        )
        _runtime_key = key
    return _runtime


def extract_state_bert(
    utterance: str,
    *,
    role: str = ROLE_CUSTOMER,
    context_turns: list[dict[str, Any]] | None = None,
    model_dir: str | Path | None = None,
    device: str = "auto",
    train_config: str | Path | None = None,
    fact_map_path: str | Path | None = None,
    thresholds_path: str | Path | None = None,
) -> dict[str, Any]:
    """F008-compatible entrypoint (same signature as main's placeholder)."""
    rt = get_runtime(
        model_dir=model_dir,
        device=device,
        train_config=train_config,
        fact_map_path=fact_map_path,
        thresholds_path=thresholds_path,
    )
    return rt.predict(utterance, role=role, context_turns=context_turns)
