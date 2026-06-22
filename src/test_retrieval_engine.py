import json
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from retrieval_engine import (
    BITMASK_FIELDS,
    BG_BACKGROUND_FIELDS,
    aggregate_pools,
    build_node_index,
    compute_bg_boost,
    compute_context_similarity,
    descend_for_sentences,
    filter_by_bitmask,
    lookup_by_key,
    lookup_with_fallback,
    rank_sentences,
    recommend,
    relax_bitmask,
)


SCORED_TREE_PATH = os.path.join(os.path.dirname(__file__), "decision_tree_scored.json")


@pytest.fixture
def tree():
    with open(SCORED_TREE_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def index(tree):
    return build_node_index(tree)


@pytest.fixture
def keyword_freq(index):
    freq = {}
    for (facts, bk), nodes in index.items():
        for kw in facts + bk:
            freq[kw] = freq.get(kw, 0) + 1
    return freq


class TestBuildNodeIndex:
    def test_unique_keys(self, index):
        assert len(index) > 0

    def test_total_nodes(self, index):
        total = sum(len(nodes) for nodes in index.values())
        assert total > 0

    def test_root_key(self, index):
        assert ((), ()) in index
        assert len(index[((), ())]) == 1

    def test_aggregation_case(self, index):
        key = ((), ("closure",))
        assert key in index
        assert len(index[key]) >= 2

    def test_permutation_insensitivity(self, tree):
        idx = build_node_index(tree)
        for (facts, bk), nodes in idx.items():
            if len(facts) >= 2:
                permuted_facts = list(reversed(facts))
                permuted_bk = list(reversed(bk)) if bk else []
                result = lookup_by_key(permuted_facts, permuted_bk, idx)
                assert len(result) == len(nodes)
                break


class TestLookupByKey:
    def test_root_lookup(self, index):
        nodes = lookup_by_key([], [], index)
        assert len(nodes) == 1

    def test_known_key(self, index):
        nodes = lookup_by_key([], ["closure"], index)
        assert len(nodes) >= 2

    def test_permutation_insensitive(self, index):
        r1 = lookup_by_key(["b", "a"], ["d", "c"], index)
        r2 = lookup_by_key(["a", "b"], ["c", "d"], index)
        assert r1 == r2

    def test_unknown_key_returns_empty(self, index):
        nodes = lookup_by_key(["nonexistent_fact_xyz"], [], index)
        assert nodes == []


class TestAggregatePools:
    def test_single_node(self, tree):
        node = tree
        pool = aggregate_pools([node])
        assert len(pool) == len(node.get("sentence_pool", []))

    def test_multiple_nodes(self, tree):
        idx = build_node_index(tree)
        nodes = idx.get(((), ("closure",)), [])
        pool = aggregate_pools(nodes)
        expected = sum(len(n.get("sentence_pool", [])) for n in nodes)
        assert len(pool) == expected

    def test_empty_nodes(self):
        assert aggregate_pools([]) == []


class TestLookupWithFallback:
    def test_exact_match(self, index, keyword_freq):
        nodes, confidence, fallbacks = lookup_with_fallback([], ["closure"], index, keyword_freq)
        assert len(nodes) >= 2
        assert confidence == 1.0
        assert fallbacks == []

    def test_key_drop(self, index, keyword_freq):
        nodes, confidence, fallbacks = lookup_with_fallback(["nonexistent_xyz"], [], index, keyword_freq)
        assert confidence < 1.0
        assert "key_drop" in fallbacks

    def test_drops_least_frequent(self, index, keyword_freq):
        nodes, confidence, fallbacks = lookup_with_fallback(
            ["nonexistent_rare_xyz", "financial_hardship"], [], index, keyword_freq
        )
        assert "key_drop" in fallbacks


class TestDescendForSentences:
    def test_non_empty_pool(self, tree):
        node = tree
        pool, confidence, fallbacks = descend_for_sentences([node])
        assert len(pool) > 0
        assert fallbacks == []

    def test_empty_pool_descends(self, tree):
        def find_empty_node(n):
            if not n.get("sentence_pool") and n.get("children"):
                return n
            for c in n.get("children", []):
                result = find_empty_node(c)
                if result:
                    return result
            return None
        empty_node = find_empty_node(tree)
        assert empty_node is not None
        pool, confidence, fallbacks = descend_for_sentences([empty_node])
        assert len(pool) > 0
        assert "descend" in fallbacks

    def test_includes_all_siblings(self, tree):
        def find_empty_node(n):
            if not n.get("sentence_pool") and n.get("children"):
                return n
            for c in n.get("children", []):
                result = find_empty_node(c)
                if result:
                    return result
            return None
        empty_node = find_empty_node(tree)
        pool, confidence, fallbacks = descend_for_sentences([empty_node])
        assert len(pool) > 0


class TestFilterByBitmask:
    def test_bitmask_0_passes_all(self):
        pool = [
            {"script_id": "s1", "bg_bitmask_int": 0},
            {"script_id": "s2", "bg_bitmask_int": 5},
        ]
        result = filter_by_bitmask(pool, 7)
        assert len(result) == 2

    def test_incompatible_excluded(self):
        pool = [
            {"script_id": "s1", "bg_bitmask_int": 0},
            {"script_id": "s2", "bg_bitmask_int": 8},
        ]
        result = filter_by_bitmask(pool, 3)
        assert len(result) == 1
        assert result[0]["script_id"] == "s1"

    def test_subset_passes(self):
        pool = [
            {"script_id": "s1", "bg_bitmask_int": 1},
        ]
        result = filter_by_bitmask(pool, 3)
        assert len(result) == 1

    def test_relax_bitmask(self):
        pool = [
            {"script_id": "s1", "bg_bitmask_int": 4},
            {"script_id": "s2", "bg_bitmask_int": 0},
        ]
        result, relaxations, fallbacks = relax_bitmask(pool, 1)
        assert len(result) >= 1
        assert "bitmask_relax" in fallbacks


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
