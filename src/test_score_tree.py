import json
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from score_tree import (
    BITMASK_FIELDS,
    BG_BACKGROUND_FIELDS,
    build_context_lookup,
    build_customer_info_lookup,
    build_reward_lookup,
    compute_bg_background,
    compute_bg_constraints,
    compute_hwr,
    compute_sas_for_pool,
    cosine_similarity,
    encode_bitmask,
    encode_bitmask_int,
    score_tree,
    _extract_bg_constraints,
    _extract_bg_background,
    _score_sentence_pool,
)


@pytest.fixture
def context_lookup():
    return build_context_lookup()


@pytest.fixture
def reward_lookup():
    return build_reward_lookup()


@pytest.fixture
def customer_info_lookup():
    return build_customer_info_lookup()


class TestContextLookup:
    def test_returns_31_records(self, context_lookup):
        assert len(context_lookup) == 31

    def test_all_have_context_fields(self, context_lookup):
        for cid, ctx in context_lookup.items():
            assert "has_auto_loan" in ctx
            assert "has_mortgage" in ctx
            assert "credit_rating" in ctx
            assert "days_delinquent" in ctx
            assert "total_debt" in ctx
            assert "external_debt" in ctx
            assert "has_negotiation_history" in ctx
            assert "available_plans" in ctx
            assert "social_insurance_stable" in ctx
            assert "card_restricted" in ctx
            assert "is_cash_out_customer" in ctx
            assert "external_debt_institutions" in ctx
            assert "interest_ratio" in ctx
            assert "installment_ratio" in ctx
            assert "age" in ctx
            assert "gender" in ctx
            assert "education" in ctx
            assert "industry" in ctx
            assert "has_complaint_history" in ctx
            assert "has_legal_tools" in ctx
            assert "is_negotiation_brain_customer" in ctx

    def test_known_call_id_present(self, context_lookup):
        assert "2317941550352385028" in context_lookup


class TestCustomerInfoLookup:
    def test_returns_31_records(self, customer_info_lookup):
        assert len(customer_info_lookup) == 31

    def test_has_chinese_fields(self, customer_info_lookup):
        ci = customer_info_lookup["2317941550352385028"]
        assert "年龄" in ci
        assert "学历" in ci
        assert "行业" in ci


class TestRewardLookup:
    def test_returns_31_records(self, reward_lookup):
        assert len(reward_lookup) == 31

    def test_all_rewards_are_0_or_1(self, reward_lookup):
        for cid, r in reward_lookup.items():
            assert r in (0, 1)

    def test_6_rewards_are_1(self, reward_lookup):
        assert sum(1 for r in reward_lookup.values() if r == 1) == 6


class TestBitmaskEncoding:
    def test_all_false_is_zero_dict(self):
        bg = {f: False for f in BITMASK_FIELDS}
        result = encode_bitmask(bg)
        assert isinstance(result, dict)
        assert all(v == 0 for v in result.values())

    def test_all_true_is_all_ones_dict(self):
        bg = {f: True for f in BITMASK_FIELDS}
        result = encode_bitmask(bg)
        assert all(v == 1 for v in result.values())

    def test_single_bit_0(self):
        bg = {f: False for f in BITMASK_FIELDS}
        bg["has_auto_loan"] = True
        result = encode_bitmask(bg)
        assert result["has_auto_loan"] == 1
        assert result["has_mortgage"] == 0

    def test_bitmask_int_from_dict(self):
        bg_bitmask = {"has_auto_loan": 1, "has_mortgage": 0, "has_negotiation_history": 0, "social_insurance_stable": 0, "credit_rating_good": 0}
        assert encode_bitmask_int(bg_bitmask) == 1

    def test_bitmask_int_all_ones(self):
        bg_bitmask = {f: 1 for f in BITMASK_FIELDS}
        assert encode_bitmask_int(bg_bitmask) == (1 << len(BITMASK_FIELDS)) - 1

    def test_bitmask_int_all_zeros(self):
        bg_bitmask = {f: 0 for f in BITMASK_FIELDS}
        assert encode_bitmask_int(bg_bitmask) == 0

    def test_extract_bg_constraints_from_context(self):
        ctx = {
            "has_auto_loan": True,
            "has_mortgage": False,
            "credit_rating": "good",
            "has_negotiation_history": True,
            "social_insurance_stable": False,
            "card_restricted": True,
            "is_cash_out_customer": False,
            "has_complaint_history": False,
            "has_legal_tools": True,
            "is_negotiation_brain_customer": False,
        }
        bg = _extract_bg_constraints(ctx)
        assert bg["has_auto_loan"] is True
        assert bg["has_mortgage"] is False
        assert bg["credit_rating_good"] is True
        assert bg["has_negotiation_history"] is True
        assert bg["social_insurance_stable"] is False
        assert bg["card_restricted"] is True
        assert bg["is_cash_out_customer"] is False
        assert bg["has_complaint_history"] is False
        assert bg["has_legal_tools"] is True
        assert bg["is_negotiation_brain_customer"] is False

    def test_credit_rating_not_good(self):
        ctx = {"credit_rating": "moderate"}
        bg = _extract_bg_constraints(ctx)
        assert bg["credit_rating_good"] is False

    def test_compute_bg_constraints_single_source(self, context_lookup):
        cid = "2317941550352385028"
        bg = compute_bg_constraints([cid], context_lookup)
        assert all(f in bg for f in BITMASK_FIELDS)

    def test_compute_bg_constraints_empty(self):
        bg = compute_bg_constraints([], {})
        assert all(bg[f] is False for f in BITMASK_FIELDS)

    def test_compute_bg_constraints_intersection(self):
        lookup = {
            "a": {"has_auto_loan": True, "has_mortgage": True, "credit_rating": "good",
                  "has_negotiation_history": False, "social_insurance_stable": False},
            "b": {"has_auto_loan": True, "has_mortgage": False, "credit_rating": "good",
                  "has_negotiation_history": False, "social_insurance_stable": False},
        }
        bg = compute_bg_constraints(["a", "b"], lookup)
        assert bg["has_auto_loan"] is True
        assert bg["has_mortgage"] is False
        assert bg["credit_rating_good"] is True

    def test_bitmask_int_range(self, context_lookup):
        max_mask = (1 << len(BITMASK_FIELDS)) - 1
        for cid, ctx in context_lookup.items():
            bg = _extract_bg_constraints(ctx)
            mask = encode_bitmask(bg)
            assert 0 <= encode_bitmask_int(mask) <= max_mask


class TestBgBackground:
    def test_extract_from_customer_info(self, customer_info_lookup):
        ci = customer_info_lookup["2317941550352385028"]
        bg = _extract_bg_background(ci)
        assert "age" in bg
        assert "gender" in bg
        assert "education" in bg
        assert "industry" in bg

    def test_compute_single_source(self, customer_info_lookup):
        bg = compute_bg_background(["2317941550352385028"], customer_info_lookup)
        assert "age" in bg
        assert isinstance(bg["age"], str)

    def test_compute_empty(self):
        bg = compute_bg_background([], {})
        for eng, _ in BG_BACKGROUND_FIELDS:
            assert eng in bg
            assert bg[eng] == ""

    def test_all_7_fields_present(self, customer_info_lookup):
        bg = compute_bg_background(["2317941550352385028"], customer_info_lookup)
        assert len(bg) == len(BG_BACKGROUND_FIELDS)


class TestHWR:
    def test_single_r1(self):
        assert compute_hwr(["a"], {"a": 1}) == pytest.approx(2 / 3, abs=1e-9)

    def test_single_r0(self):
        assert compute_hwr(["a"], {"a": 0}) == pytest.approx(1 / 3, abs=1e-9)

    def test_empty_is_half(self):
        assert compute_hwr([], {}) == 0.5

    def test_all_r1(self):
        rl = {"a": 1, "b": 1, "c": 1}
        assert compute_hwr(["a", "b", "c"], rl) == pytest.approx(4 / 5, abs=1e-9)

    def test_all_r0(self):
        rl = {"a": 0, "b": 0}
        assert compute_hwr(["a", "b"], rl) == pytest.approx(1 / 4, abs=1e-9)

    def test_mixed(self):
        rl = {"a": 1, "b": 0, "c": 1}
        assert compute_hwr(["a", "b", "c"], rl) == pytest.approx(3 / 5, abs=1e-9)

    def test_unknown_call_id_treated_as_r0(self):
        assert compute_hwr(["unknown"], {}) == pytest.approx(1 / 3, abs=1e-9)


class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0, abs=1e-9)

    def test_orthogonal_vectors(self):
        assert cosine_similarity([1, 0, 0], [0, 1, 0]) == pytest.approx(0.0, abs=1e-9)

    def test_known_value(self):
        a = [1, 1, 0]
        b = [1, 0, 0]
        expected = 1 / (2**0.5)
        assert cosine_similarity(a, b) == pytest.approx(expected, abs=1e-9)

    def test_zero_vector(self):
        assert cosine_similarity([0, 0, 0], [1, 0, 0]) == 0.0


class TestSAS:
    def test_single_sentence_is_one(self):
        sentences = [{"script_text": "hello", "script_id": "t1", "win_rate": 0.5}]
        assert compute_sas_for_pool(sentences) == [1.0]

    def test_identical_texts(self):
        sentences = [
            {"script_text": "你好", "script_id": "t1", "win_rate": 0.7},
            {"script_text": "你好", "script_id": "t2", "win_rate": 0.3},
        ]
        scores = compute_sas_for_pool(sentences)
        assert scores[0] == pytest.approx(1.0, abs=1e-6)
        assert scores[1] == pytest.approx(1.0, abs=1e-6)

    def test_sas_in_range(self):
        sentences = [
            {"script_text": "您可以尽快还款吗", "script_id": "t1", "win_rate": 0.7},
            {"script_text": "我们建议您办理分期", "script_id": "t2", "win_rate": 0.3},
        ]
        scores = compute_sas_for_pool(sentences)
        for s in scores:
            assert 0 <= s <= 1

    def test_reference_is_highest_hwr(self):
        sentences = [
            {"script_text": "低胜率句子", "script_id": "t1", "win_rate": 0.2},
            {"script_text": "高胜率句子不同的文本", "script_id": "t2", "win_rate": 0.8},
        ]
        scores = compute_sas_for_pool(sentences)
        assert scores[1] == pytest.approx(1.0, abs=1e-6)


class TestScoreSentencePool:
    def test_augments_all_fields(self, context_lookup, reward_lookup, customer_info_lookup):
        pool = [
            {"script_text": "hello", "script_id": "t1", "source_call_ids": ["2317941550352385028"]},
        ]
        _score_sentence_pool(pool, context_lookup, reward_lookup, customer_info_lookup)
        s = pool[0]
        for field in ["bg_constraints", "bg_bitmask", "bg_bitmask_int", "bg_background", "win_rate", "sas", "uplift_score", "csi", "deferred"]:
            assert field in s, f"missing {field}"

    def test_bg_bitmask_is_dict(self, context_lookup, reward_lookup, customer_info_lookup):
        pool = [
            {"script_text": "hello", "script_id": "t1", "source_call_ids": ["2317941550352385028"]},
        ]
        _score_sentence_pool(pool, context_lookup, reward_lookup, customer_info_lookup)
        s = pool[0]
        assert isinstance(s["bg_bitmask"], dict)
        assert all(f in s["bg_bitmask"] for f in BITMASK_FIELDS)
        assert all(v in (0, 1) for v in s["bg_bitmask"].values())

    def test_bg_bitmask_int_is_integer(self, context_lookup, reward_lookup, customer_info_lookup):
        pool = [
            {"script_text": "hello", "script_id": "t1", "source_call_ids": ["2317941550352385028"]},
        ]
        _score_sentence_pool(pool, context_lookup, reward_lookup, customer_info_lookup)
        s = pool[0]
        max_mask = (1 << len(BITMASK_FIELDS)) - 1
        assert isinstance(s["bg_bitmask_int"], int)
        assert 0 <= s["bg_bitmask_int"] <= max_mask

    def test_bg_background_has_fields(self, context_lookup, reward_lookup, customer_info_lookup):
        pool = [
            {"script_text": "hello", "script_id": "t1", "source_call_ids": ["2317941550352385028"]},
        ]
        _score_sentence_pool(pool, context_lookup, reward_lookup, customer_info_lookup)
        s = pool[0]
        assert isinstance(s["bg_background"], dict)
        for eng, _ in BG_BACKGROUND_FIELDS:
            assert eng in s["bg_background"]

    def test_deferred_fields(self, context_lookup, reward_lookup, customer_info_lookup):
        pool = [
            {"script_text": "hello", "script_id": "t1", "source_call_ids": ["2317941550352385028"]},
        ]
        _score_sentence_pool(pool, context_lookup, reward_lookup, customer_info_lookup)
        s = pool[0]
        assert s["uplift_score"] == 0
        assert s["csi"] == 0
        assert s["deferred"] is True

    def test_win_rate_in_range(self, context_lookup, reward_lookup, customer_info_lookup):
        pool = [
            {"script_text": "hello", "script_id": "t1", "source_call_ids": ["2317941550352385028"]},
        ]
        _score_sentence_pool(pool, context_lookup, reward_lookup, customer_info_lookup)
        assert 0 <= pool[0]["win_rate"] <= 1

    def test_sas_computed(self, context_lookup, reward_lookup, customer_info_lookup):
        pool = [
            {"script_text": "您可以尽快还款吗", "script_id": "t1", "source_call_ids": ["2317941550352385028"]},
            {"script_text": "我们建议您办理分期", "script_id": "t2", "source_call_ids": ["2317941550352385028"]},
        ]
        _score_sentence_pool(pool, context_lookup, reward_lookup, customer_info_lookup)
        assert 0 <= pool[0]["sas"] <= 1
        assert 0 <= pool[1]["sas"] <= 1


class TestScoreTree:
    def test_preserves_structure(self, context_lookup, reward_lookup, customer_info_lookup):
        with open(os.path.join(os.path.dirname(__file__), "decision_tree.json"), encoding="utf-8") as f:
            tree = json.load(f)
        import copy
        original = copy.deepcopy(tree)
        scored = score_tree(tree, context_lookup, reward_lookup, customer_info_lookup)
        assert scored["state_id"] == original["state_id"]
        assert len(scored.get("children", [])) == len(original.get("children", []))

    def test_all_sentences_scored(self, context_lookup, reward_lookup, customer_info_lookup):
        with open(os.path.join(os.path.dirname(__file__), "decision_tree.json"), encoding="utf-8") as f:
            tree = json.load(f)
        scored = score_tree(tree, context_lookup, reward_lookup, customer_info_lookup)
        missing = []
        def check(node):
            for s in node.get("sentence_pool", []):
                for field in ["bg_constraints", "bg_bitmask", "bg_bitmask_int", "bg_background", "win_rate", "sas", "uplift_score", "csi", "deferred"]:
                    if field not in s:
                        missing.append((s.get("script_id"), field))
            for child in node.get("children", []):
                check(child)
        check(scored)
        assert missing == []
