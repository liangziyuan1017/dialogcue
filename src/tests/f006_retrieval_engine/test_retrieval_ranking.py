import json
import os

import pytest

from f006_retrieval_engine.retrieval_engine import (
    compute_bg_boost,
    compute_context_similarity,
    rank_sentences,
    recommend,
)


SCORED_TREE_PATH = os.path.join(os.path.dirname(__file__), "../..", "f005_context_scoring", "decision_tree_scored.json")


@pytest.fixture
def tree():
    with open(SCORED_TREE_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def index(tree):
    from f006_retrieval_engine.retrieval_engine import build_node_index
    return build_node_index(tree)


@pytest.fixture
def keyword_freq(index):
    freq = {}
    for (facts, bk), nodes in index.items():
        for kw in facts + bk:
            freq[kw] = freq.get(kw, 0) + 1
    return freq


class TestContextSimilarity:
    def test_identical_context(self):
        sim = compute_context_similarity("客户说没有钱无法还款", "客户说没有钱无法还款")
        assert sim == pytest.approx(1.0, abs=1e-6)

    def test_different_context(self):
        sim = compute_context_similarity("客户说没有钱无法还款", "催收员建议办理分期付款")
        assert 0.0 <= sim < 1.0

    def test_range(self):
        sim = compute_context_similarity("你好", "再见")
        assert 0.0 <= sim <= 1.0


class TestBgBoost:
    def test_industry_match(self):
        boost = compute_bg_boost({"industry": "专业性事务所"}, {"industry": "专业性事务所"})
        assert boost >= 0.05

    def test_no_match(self):
        boost = compute_bg_boost({"industry": "A"}, {"industry": "B"})
        assert boost == 0.0

    def test_all_matches(self):
        boost = compute_bg_boost(
            {"industry": "A", "education": "college", "total_debt": 100, "age": 40},
            {"industry": "A", "education": "college", "total_debt": 120, "age": 45},
        )
        assert boost >= 0.05 + 0.02 + 0.03 + 0.02


class TestRankSentences:
    def test_limited_context_first(self):
        pool = [
            {"script_id": "s1", "win_rate": 0.8, "sas": 0.5, "conversation_context_similarity": 0.3, "bg_bitmask_int": 0},
            {"script_id": "s2", "win_rate": 0.3, "sas": 0.5, "conversation_context_similarity": 0.9, "bg_bitmask_int": 0},
        ]
        ranked = rank_sentences(pool, strategy="limited", conversation_context="some context")
        assert ranked[0]["script_id"] == "s2"

    def test_full_winrate_first(self):
        pool = [
            {"script_id": "s1", "win_rate": 0.8, "sas": 0.5, "conversation_context_similarity": 0.3, "bg_bitmask_int": 0},
            {"script_id": "s2", "win_rate": 0.3, "sas": 0.5, "conversation_context_similarity": 0.9, "bg_bitmask_int": 0},
        ]
        ranked = rank_sentences(pool, strategy="full", conversation_context="some context")
        assert ranked[0]["script_id"] == "s1"

    def test_empty_pool(self):
        assert rank_sentences([], strategy="limited") == []

    def test_single_sentence(self):
        pool = [
            {"script_id": "s1", "win_rate": 0.5, "sas": 0.5, "conversation_context_similarity": 0.5, "bg_bitmask_int": 0},
        ]
        ranked = rank_sentences(pool, strategy="limited")
        assert len(ranked) == 1


class TestRecommend:
    def test_exact_match(self, tree, index, keyword_freq):
        result = recommend(
            inherited_facts=[], branch_key_values=["closure"],
            query_bitmask=1023, conversation_context="客户说没有钱",
            query_bg={}, strategy="limited",
            tree=tree, index=index, keyword_freq=keyword_freq,
        )
        assert result is not None
        assert "script_text" in result
        assert result["confidence"] == 1.0
        assert result["fallbacks"] == []

    def test_key_drop_fallback(self, tree, index, keyword_freq):
        result = recommend(
            inherited_facts=["nonexistent_xyz"], branch_key_values=[],
            query_bitmask=1023, conversation_context="客户说没有钱",
            query_bg={}, strategy="limited",
            tree=tree, index=index, keyword_freq=keyword_freq,
        )
        assert result is not None
        assert "key_drop" in result["fallbacks"]

    def test_bitmask_filter(self, tree, index, keyword_freq):
        result = recommend(
            inherited_facts=[], branch_key_values=["greeting"],
            query_bitmask=1023, conversation_context="客户说你好",
            query_bg={}, strategy="limited",
            tree=tree, index=index, keyword_freq=keyword_freq,
        )
        assert result is not None

    def test_output_schema(self, tree, index, keyword_freq):
        result = recommend(
            inherited_facts=[], branch_key_values=["closure"],
            query_bitmask=1023, conversation_context="客户说没有钱",
            query_bg={}, strategy="full",
            tree=tree, index=index, keyword_freq=keyword_freq,
        )
        assert result is not None
        for field in ["script_text", "script_id", "state_id", "win_rate", "sas",
                      "conversation_context_similarity", "confidence", "strategy", "fallbacks"]:
            assert field in result, f"missing {field}"
        assert result["strategy"] == "full"
