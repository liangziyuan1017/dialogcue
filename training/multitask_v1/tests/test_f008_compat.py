"""F008 / SCBGE extract_state_bert contract tests (no real RoBERTa weights)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import torch

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from f008_compat import (  # noqa: E402
    ROLE_COLLECTOR,
    ROLE_CUSTOMER,
    build_context_window,
    decoded_to_f008_state,
    extract_state_bert,
    map_active_fact,
    normalize_role,
)
from infer_decode import decode_multitask_output  # noqa: E402
from labels import emotion_labels, willingness_labels  # noqa: E402
from model import MultitaskV1Model  # noqa: E402
from paths import load_fact_schema  # noqa: E402


def _required_keys(out: dict) -> None:
    for k in ("facts", "emotions", "actions", "willingness", "confidence", "method"):
        assert k in out
    assert out["method"] == "bert"
    assert isinstance(out["facts"], list)
    assert isinstance(out["emotions"], list)
    assert isinstance(out["actions"], list)
    assert out["willingness"] is None or isinstance(out["willingness"], str)
    assert 0.0 <= float(out["confidence"]) <= 1.0


def test_normalize_role():
    assert normalize_role("客户") == ROLE_CUSTOMER
    assert normalize_role("催收员") == ROLE_COLLECTOR
    assert normalize_role("customer") == ROLE_CUSTOMER
    assert normalize_role("collector") == ROLE_COLLECTOR


def test_map_active_fact_uses_yaml():
    assert map_active_fact("FinancialHardship", "yes") == "financial_hardship"
    assert map_active_fact("RepaymentCapability", "partial") == "partial_capacity"
    assert map_active_fact("RepaymentCapability", "insufficient") == "repayment_inability"


def test_decoded_to_f008_customer_shape():
    schema = load_fact_schema()
    emo = emotion_labels()
    will = willingness_labels()
    fact_logits = {h.name: torch.full((1, h.n_classes), -5.0) for h in schema.heads}
    for h in schema.heads:
        fact_logits[h.name][0, -1] = 5.0
    # fire FinancialHardship yes
    fh = schema.head_by_name()["FinancialHardship"]
    fact_logits["FinancialHardship"] = torch.full((1, fh.n_classes), -5.0)
    fact_logits["FinancialHardship"][0, 0] = 5.0

    out = {
        "fact_logits": fact_logits,
        "emotion_logits": torch.zeros(1, len(emo)),
        "willingness_logits": torch.zeros(1, len(will)),
    }
    out["emotion_logits"][0, emo.index("distress")] = 4.0
    out["willingness_logits"][0, will.index("weak")] = 4.0

    decoded = decode_multitask_output(
        out, schema=schema, emotion_vocab=emo, willingness_vocab=will
    )
    state = decoded_to_f008_state(decoded, role=ROLE_CUSTOMER)
    _required_keys(state)
    assert "financial_hardship" in state["facts"]
    assert state["emotions"] == ["distress"]
    assert state["willingness"] == "weak"
    assert state["actions"] == []


def test_decoded_to_f008_collector_clears_customer_fields():
    decoded = {
        "fact_active": {
            "FinancialHardship": {"value": "yes", "prob": 0.9, "active": True}
        },
        "emotion": {"label": "hostility", "prob": 0.8, "abstain": False},
        "willingness": {"label": "resistant", "prob": 0.7, "abstain": False},
    }
    state = decoded_to_f008_state(decoded, role=ROLE_COLLECTOR)
    _required_keys(state)
    assert state["facts"] == []
    assert state["emotions"] == []
    assert state["willingness"] is None
    assert state["actions"] == []


def test_build_context_window_with_prior_turns():
    text = build_context_window(
        "我现在没钱还",
        role=ROLE_CUSTOMER,
        context_turns=[
            {"role": "催收员", "text": "请问您什么时候能还款？"},
            {"role": "客户", "text": "最近有点困难"},
        ],
    )
    assert "customer" in text.lower() or "[customer]" in text
    assert "没钱" in text or "困难" in text


def test_extract_state_bert_with_mock_ckpt(tmp_path: Path | None = None):
    schema = load_fact_schema()
    emo = emotion_labels()
    will = willingness_labels()
    model = MultitaskV1Model(
        "__mock__", fact_schema=schema, emotion_vocab=emo, willingness_vocab=will
    )
    # Bias FH / emotion / willingness so decode is stable
    with torch.no_grad():
        model.fact_heads["FinancialHardship"].bias[0] = 8.0
        model.fact_heads["FinancialHardship"].bias[1] = -8.0
        model.emotion_head.bias[emo.index("distress")] = 8.0
        model.willingness_head.bias[will.index("weak")] = 8.0

    root = Path(tempfile.mkdtemp()) if tmp_path is None else Path(tmp_path)
    ckpt = root / "multitask_best.pt"
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "metadata": {
                "model": {"encoder": "__mock__"},
                "fact": "v3.1.2-patch1",
                "emotion": "11v1",
                "willingness": "5v1",
            },
            "config": {"model_name": "__mock__"},
        },
        ckpt,
    )

    # reset singleton between tests
    import f008_compat as fc

    fc._runtime = None
    fc._runtime_key = None

    state = extract_state_bert(
        "我现在真的没钱还",
        role=ROLE_CUSTOMER,
        context_turns=[{"role": "催收员", "text": "您好，今天来电提醒还款"}],
        model_dir=root,
        device="cpu",
    )
    _required_keys(state)
    assert "financial_hardship" in state["facts"]
    assert state["emotions"] == ["distress"]
    assert state["willingness"] == "weak"
