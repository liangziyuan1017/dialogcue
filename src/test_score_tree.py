import json
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from score_tree import (
    BITMASK_FIELDS,
    build_context_lookup,
    build_reward_lookup,
    compute_bg_constraints,
    compute_hwr,
    compute_sas_for_pool,
    cosine_similarity,
    encode_bitmask,
    score_tree,
    _extract_bg_constraints,
    _score_sentence_pool,
)


@pytest.fixture
def context_lookup():
    return build_context_lookup()


@pytest.fixture
def reward_lookup():
    return build_reward_lookup()


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

    def test_known_call_id_present(self, context_lookup):
        assert "2317941550352385028" in context_lookup


class TestRewardLookup:
    def test_returns_31_records(self, reward_lookup):
        assert len(reward_lookup) == 31

    def test_all_rewards_are_0_or_1(self, reward_lookup):
        for cid, r in reward_lookup.items():
            assert r in (0, 1)

    def test_6_rewards_are_1(self, reward_lookup):
        assert sum(1 for r in reward_lookup.values() if r == 1) == 6


class TestBitmaskEncoding:
    def test_all_false_is_zero(self):
        assert encode_bitmask({f: False for f in BITMASK_FIELDS}) == 0

    def test_all_true_is_31(self):
        assert encode_bitmask({f: True for f in BITMASK_FIELDS}) == 31

    def test_single_bit_0(self):
        bg = {f: False for f in BITMASK_FIELDS}
        bg["has_auto_loan"] = True
        assert encode_bitmask(bg) == 1

    def test_single_bit_1(self):
        bg = {f: False for f in BITMASK_FIELDS}
        bg["has_mortgage"] = True
        assert encode_bitmask(bg) == 2

    def test_single_bit_4(self):
        bg = {f: False for f in BITMASK_FIELDS}
        bg["credit_rating_good"] = True
        assert encode_bitmask(bg) == 16

    def test_extract_bg_constraints_from_context(self):
        ctx = {
            "has_auto_loan": True,
            "has_mortgage": False,
            "credit_rating": "good",
            "has_negotiation_history": True,
            "social_insurance_stable": False,
        }
        bg = _extract_bg_constraints(ctx)
        assert bg["has_auto_loan"] is True
        assert bg["has_mortgage"] is False
        assert bg["credit_rating_good"] is True
        assert bg["has_negotiation_history"] is True
        assert bg["social_insurance_stable"] is False

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

    def test_bitmask_range(self, context_lookup):
        for cid, ctx in context_lookup.items():
            bg = _extract_bg_constraints(ctx)
            mask = encode_bitmask(bg)
            assert 0 <= mask <= 31


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
    def test_augments_all_fields(self, context_lookup, reward_lookup):
        pool = [
            {"script_text": "hello", "script_id": "t1", "source_call_ids": ["2317941550352385028"]},
        ]
        _score_sentence_pool(pool, context_lookup, reward_lookup)
        s = pool[0]
        assert "bg_constraints" in s
        assert "bg_bitmask" in s
        assert "win_rate" in s
        assert "sas" in s
        assert "uplift_score" in s
        assert "csi" in s
        assert "deferred" in s

    def test_deferred_fields(self, context_lookup, reward_lookup):
        pool = [
            {"script_text": "hello", "script_id": "t1", "source_call_ids": ["2317941550352385028"]},
        ]
        _score_sentence_pool(pool, context_lookup, reward_lookup)
        s = pool[0]
        assert s["uplift_score"] == 0
        assert s["csi"] == 0
        assert s["deferred"] is True

    def test_win_rate_in_range(self, context_lookup, reward_lookup):
        pool = [
            {"script_text": "hello", "script_id": "t1", "source_call_ids": ["2317941550352385028"]},
        ]
        _score_sentence_pool(pool, context_lookup, reward_lookup)
        assert 0 <= pool[0]["win_rate"] <= 1

    def test_sas_computed(self, context_lookup, reward_lookup):
        pool = [
            {"script_text": "您可以尽快还款吗", "script_id": "t1", "source_call_ids": ["2317941550352385028"]},
            {"script_text": "我们建议您办理分期", "script_id": "t2", "source_call_ids": ["2317941550352385028"]},
        ]
        _score_sentence_pool(pool, context_lookup, reward_lookup)
        assert 0 <= pool[0]["sas"] <= 1
        assert 0 <= pool[1]["sas"] <= 1


class TestScoreTree:
    def test_preserves_structure(self, context_lookup, reward_lookup):
        with open(os.path.join(os.path.dirname(__file__), "decision_tree.json"), encoding="utf-8") as f:
            tree = json.load(f)
        import copy
        original = copy.deepcopy(tree)
        scored = score_tree(tree, context_lookup, reward_lookup)
        assert scored["state_id"] == original["state_id"]
        assert len(scored.get("children", [])) == len(original.get("children", []))

    def test_all_sentences_scored(self, context_lookup, reward_lookup):
        with open(os.path.join(os.path.dirname(__file__), "decision_tree.json"), encoding="utf-8") as f:
            tree = json.load(f)
        scored = score_tree(tree, context_lookup, reward_lookup)
        missing = []
        def check(node):
            for s in node.get("sentence_pool", []):
                for field in ["bg_constraints", "bg_bitmask", "win_rate", "sas", "uplift_score", "csi", "deferred"]:
                    if field not in s:
                        missing.append((s.get("script_id"), field))
            for child in node.get("children", []):
                check(child)
        check(scored)
        assert missing == []
