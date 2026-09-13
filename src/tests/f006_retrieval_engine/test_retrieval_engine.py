import inspect
import json
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

from f006_retrieval_engine.retrieval_engine import (
    _build_label_set_index,
    _find_matching_nodes_subset,
    build_node_index,
    recommend,
)
from f007_infrastructure.embeddings import EMBEDDING_DIM

SCORED_TREE_PATH = os.path.join(os.path.dirname(__file__), "../..", "f005_context_scoring", "data", "decision_tree_scored.json")


@pytest.fixture
def tree():
    with open(SCORED_TREE_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def index(tree):
    return build_node_index(tree)


@pytest.fixture
def label_set_index(index):
    return _build_label_set_index(index)


class TestRecommendOutputSchema:
    def test_is_async(self):
        assert inspect.iscoroutinefunction(recommend)

    async def test_has_vec_score_and_final_score(self, tree, index, label_set_index):
        result = await recommend(
            query_bitmask=511, conversation_context="客户说没有钱",
            query_bg={}, tree=tree, index=index, label_set_index=label_set_index,
        )
        assert result is not None
        assert "vec_score" in result
        assert "final_score" in result
        assert "conversation_state" in result

    async def test_has_ranking_weights(self, tree, index, label_set_index):
        result = await recommend(
            query_bitmask=511, conversation_context="客户说没有钱",
            query_bg={}, tree=tree, index=index, label_set_index=label_set_index,
        )
        assert result is not None
        assert "ranking_weights" in result


class TestRecommendWithDB:
    async def test_uses_db_for_candidates(self, tree, index, label_set_index):
        mock_db = MagicMock()
        mock_db.get_node_by_signature = AsyncMock(return_value={"id": 1})
        mock_db.get_sentences_by_node = AsyncMock(return_value=[
            {"script_id": "s1", "script_text": "hello", "win_rate": 0.8, "sas": 0.5, "bg_bitmask_int": 0, "bg_background": {}},
        ])
        mock_db.get_vectors = AsyncMock(return_value={"s1": [0.1] * EMBEDDING_DIM})
        result = await recommend(
            query_bitmask=511, conversation_context="客户说没有钱",
            query_bg={}, tree=tree, index=index, label_set_index=label_set_index,
            db=mock_db, query_vec=[0.1] * EMBEDDING_DIM,
        )
        assert result is not None


class TestPathStructuredState:
    async def test_accepts_path_state(self, tree, index, label_set_index):
        result = await recommend(
            query_bitmask=511, conversation_context="客户说没有钱",
            query_bg={}, tree=tree, index=index, label_set_index=label_set_index,
            conversation_state={"branch_key": {"facts": ["situational_hardship"]}, "inherited_facts": [], "inherited_emotions": [], "willingness": None},
        )
        assert result is not None
        assert "conversation_state" in result
        assert "branch_key" in result["conversation_state"]

    async def test_default_conversation_state(self, tree, index, label_set_index):
        result = await recommend(
            query_bitmask=511, conversation_context="客户说没有钱",
            query_bg={}, tree=tree, index=index, label_set_index=label_set_index,
        )
        assert result is not None
        assert result["conversation_state"] == {"branch_key": {}, "inherited_facts": [], "inherited_emotions": [], "willingness": None}

    async def test_backward_compat_flat_state(self, tree, index, label_set_index):
        result = await recommend(
            query_bitmask=511, conversation_context="客户说没有钱",
            query_bg={}, tree=tree, index=index, label_set_index=label_set_index,
            conversation_state={"facts": ["situational_hardship"], "emotions": [], "actions": [], "willingness": None},
        )
        assert result is not None


class TestSubsetMatchFallback:
    def test_exact_match_confidence_1(self, tree, index, label_set_index):
        nodes, conf, fb = _find_matching_nodes_subset(
            ["situational_hardship"], [], [], index, label_set_index
        )
        if nodes:
            assert conf == 1.0
            assert fb == []

    def test_nonexistent_label_falls_back(self, tree, index, label_set_index):
        nodes, conf, fb = _find_matching_nodes_subset(
            ["nonexistent_xyz"], [], [], index, label_set_index
        )
        assert conf < 1.0
        assert len(fb) > 0

    def test_drop_emotions_before_facts(self, tree, index, label_set_index):
        nodes, conf, fb = _find_matching_nodes_subset(
            ["situational_hardship"], ["nonexistent_emo"], [], index, label_set_index
        )
        if nodes:
            assert any("emotion" in f for f in fb) or conf == 1.0

    def test_pools_multiple_nodes(self, tree, index, label_set_index):
        nodes, conf, fb = _find_matching_nodes_subset(
            ["situational_hardship", "payment_commitment"], [], [], index, label_set_index
        )
        if nodes:
            assert isinstance(nodes, list)


class TestDescendIntoChildrenForPool:
    def test_anxiety_node_returned_not_root(self, tree, index, label_set_index):
        nodes, conf, fb = _find_matching_nodes_subset(
            ["situational_hardship"], [], [], index, label_set_index
        )
        assert len(nodes) > 0
        for n in nodes:
            assert n.get("state_id", "") != "initial_contact"
        assert "root_fallback" not in fb

    def test_personal_info_node_returned_not_root(self, tree, index, label_set_index):
        nodes, conf, fb = _find_matching_nodes_subset(
            ["installment_request"], [], [], index, label_set_index
        )
        assert len(nodes) > 0
        for n in nodes:
            assert n.get("state_id", "") != "initial_contact"
        assert "root_fallback" not in fb

    def test_income_loss_node_returned_not_root(self, tree, index, label_set_index):
        nodes, conf, fb = _find_matching_nodes_subset(
            ["account_info"], [], [], index, label_set_index
        )
        assert len(nodes) > 0
        for n in nodes:
            assert n.get("state_id", "") != "initial_contact"
        assert "root_fallback" not in fb


class TestFallbacksStillWork:
    async def test_empty_key_fallback(self, tree, index, label_set_index):
        result = await recommend(
            query_bitmask=511, conversation_context="客户说没有钱",
            query_bg={}, tree=tree, index=index, label_set_index=label_set_index,
            conversation_state={"branch_key": {"facts": ["nonexistent_xyz"]}, "inherited_facts": [], "inherited_emotions": [], "willingness": None},
        )
        assert result is not None
