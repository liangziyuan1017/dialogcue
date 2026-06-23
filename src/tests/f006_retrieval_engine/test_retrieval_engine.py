import json
import os

import pytest

from f006_retrieval_engine.retrieval_engine import (
    aggregate_pools,
    build_node_index,
    descend_for_sentences,
    filter_by_bitmask,
    lookup_by_key,
    lookup_with_fallback,
    relax_bitmask,
)


SCORED_TREE_PATH = os.path.join(os.path.dirname(__file__), "../..", "f005_context_scoring", "decision_tree_scored.json")


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
