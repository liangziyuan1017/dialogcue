import json
import os
from collections import defaultdict
from unittest.mock import MagicMock

import pytest

from f006_retrieval_engine.retrieval_engine import (
    build_node_index,
    recommend,
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


class TestRecommendOutputSchema:
    def test_has_vec_score_and_final_score(self, tree, index, keyword_freq):
        result = recommend(
            inherited_facts=[], branch_key_values=["closure"],
            query_bitmask=1023, conversation_context="客户说没有钱",
            query_bg={}, tree=tree, index=index, keyword_freq=keyword_freq,
        )
        assert result is not None
        assert "vec_score" in result
        assert "final_score" in result
        assert "conversation_state" in result

    def test_no_old_fields(self, tree, index, keyword_freq):
        result = recommend(
            inherited_facts=[], branch_key_values=["closure"],
            query_bitmask=1023, conversation_context="客户说没有钱",
            query_bg={}, tree=tree, index=index, keyword_freq=keyword_freq,
        )
        assert result is not None
        assert "conversation_context_similarity" not in result
        assert "strategy" not in result

    def test_has_ranking_weights(self, tree, index, keyword_freq):
        result = recommend(
            inherited_facts=[], branch_key_values=["closure"],
            query_bitmask=1023, conversation_context="客户说没有钱",
            query_bg={}, tree=tree, index=index, keyword_freq=keyword_freq,
        )
        assert result is not None
        assert "ranking_weights" in result


class TestRecommendWithDB:
    def test_uses_db_for_candidates(self, tree, index, keyword_freq):
        mock_db = MagicMock()
        mock_db.get_sentences_by_node.return_value = [
            {"script_id": "s1", "script_text": "hello", "win_rate": 0.8, "sas": 0.5, "bg_bitmask_int": 0, "bg_background": {}},
        ]
        mock_db.get_vectors.return_value = {"s1": [0.1] * 768}
        result = recommend(
            inherited_facts=[], branch_key_values=["closure"],
            query_bitmask=1023, conversation_context="客户说没有钱",
            query_bg={}, tree=tree, index=index, keyword_freq=keyword_freq,
            db=mock_db, query_vec=[0.1] * 768,
        )
        assert result is not None


class TestConversationState:
    def test_accepts_conversation_state(self, tree, index, keyword_freq):
        result = recommend(
            inherited_facts=[], branch_key_values=["closure"],
            query_bitmask=1023, conversation_context="客户说没有钱",
            query_bg={}, tree=tree, index=index, keyword_freq=keyword_freq,
            conversation_state={"facts": ["financial_hardship"], "emotions": [], "actions": []},
        )
        assert result is not None
        assert "conversation_state" in result

    def test_default_conversation_state(self, tree, index, keyword_freq):
        result = recommend(
            inherited_facts=[], branch_key_values=["closure"],
            query_bitmask=1023, conversation_context="客户说没有钱",
            query_bg={}, tree=tree, index=index, keyword_freq=keyword_freq,
        )
        assert result is not None
        assert result["conversation_state"] == {"facts": [], "emotions": [], "actions": []}


class TestFallbacksStillWork:
    def test_key_drop_fallback(self, tree, index, keyword_freq):
        result = recommend(
            inherited_facts=["nonexistent_xyz"], branch_key_values=[],
            query_bitmask=1023, conversation_context="客户说没有钱",
            query_bg={}, tree=tree, index=index, keyword_freq=keyword_freq,
        )
        assert result is not None
        assert "key_drop" in result["fallbacks"]
