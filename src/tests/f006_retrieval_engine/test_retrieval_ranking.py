import json
import os
from unittest.mock import MagicMock

import pytest

from f007_infrastructure.embeddings import EMBEDDING_DIM
from f006_retrieval_engine.retrieval_ranking import (
    RANKING_WEIGHTS,
    compute_bg_boost,
    compute_vec_similarity,
    rank_sentences,
)


SCORED_TREE_PATH = os.path.join(os.path.dirname(__file__), "../..", "f005_context_scoring", "data", "decision_tree_scored.json")


@pytest.fixture
def tree():
    with open(SCORED_TREE_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def index(tree):
    from f006_retrieval_engine.retrieval_engine import build_node_index
    return build_node_index(tree)


class TestRankingWeights:
    def test_has_correct_keys(self):
        assert set(RANKING_WEIGHTS.keys()) == {"win_rate", "vec_score", "sas", "bg_boost"}

    def test_sums_to_one(self):
        assert sum(RANKING_WEIGHTS.values()) == pytest.approx(1.0, abs=1e-9)

    def test_values(self):
        assert RANKING_WEIGHTS["win_rate"] == 0.40
        assert RANKING_WEIGHTS["vec_score"] == 0.30
        assert RANKING_WEIGHTS["sas"] == 0.15
        assert RANKING_WEIGHTS["bg_boost"] == 0.15


class TestVecSimilarity:
    def test_returns_dict_of_scores(self):
        mock_db = MagicMock()
        mock_db.get_vectors.return_value = {
            "s1": [1.0, 0.0] + [0.0] * (EMBEDDING_DIM - 2),
            "s2": [0.0, 1.0] + [0.0] * (EMBEDDING_DIM - 2),
        }
        query_vec = [1.0, 0.0] + [0.0] * (EMBEDDING_DIM - 2)
        scores = compute_vec_similarity(query_vec, ["s1", "s2"], mock_db)
        assert isinstance(scores, dict)
        assert "s1" in scores
        assert "s2" in scores
        assert scores["s1"] == pytest.approx(1.0, abs=1e-6)
        assert scores["s2"] == pytest.approx(0.0, abs=1e-6)

    def test_orthogonal_vectors_zero_similarity(self):
        mock_db = MagicMock()
        mock_db.get_vectors.return_value = {
            "s1": [0.0, 1.0] + [0.0] * (EMBEDDING_DIM - 2),
        }
        query_vec = [1.0, 0.0] + [0.0] * (EMBEDDING_DIM - 2)
        scores = compute_vec_similarity(query_vec, ["s1"], mock_db)
        assert scores["s1"] == pytest.approx(0.0, abs=1e-6)


class TestBgBoost:
    def test_industry_match(self):
        boost = compute_bg_boost({"industry": "专业性事务所"}, {"industry": "专业性事务所"})
        assert boost >= 0.05

    def test_no_match(self):
        boost = compute_bg_boost({"industry": "A"}, {"industry": "B"})
        assert boost == 0.0

    def test_all_matches(self):
        boost = compute_bg_boost(
            {"industry": "A", "education": "college", "total_debt": 100, "age": 40, "interest_ratio": 5},
            {"industry": "A", "education": "college", "total_debt": 120, "age": 45},
        )
        assert boost >= 0.05 + 0.02 + 0.03 + 0.02


class TestRankSentences:
    def test_unified_fusion_ranking(self):
        mock_db = MagicMock()
        mock_db.get_vectors.return_value = {
            "s1": [1.0] + [0.0] * (EMBEDDING_DIM - 1),
            "s2": [0.5] + [0.0] * (EMBEDDING_DIM - 1),
        }
        pool = [
            {"script_id": "s1", "win_rate": 0.5, "sas": 0.5, "bg_background": {}, "bg_bitmask_int": 0},
            {"script_id": "s2", "win_rate": 0.9, "sas": 0.5, "bg_background": {}, "bg_bitmask_int": 0},
        ]
        ranked = rank_sentences(pool, query_vec=[1.0] + [0.0] * (EMBEDDING_DIM - 1), db=mock_db, query_bg={})
        assert len(ranked) == 2
        assert "final_score" in ranked[0]
        assert "vec_score" in ranked[0]
        assert ranked[0]["final_score"] >= ranked[1]["final_score"]

    def test_empty_pool(self):
        assert rank_sentences([]) == []

    def test_single_sentence(self):
        mock_db = MagicMock()
        mock_db.get_vectors.return_value = {"s1": [0.1] * EMBEDDING_DIM}
        pool = [
            {"script_id": "s1", "win_rate": 0.5, "sas": 0.5, "bg_background": {}, "bg_bitmask_int": 0},
        ]
        ranked = rank_sentences(pool, query_vec=[0.1] * EMBEDDING_DIM, db=mock_db, query_bg={})
        assert len(ranked) == 1
        assert "final_score" in ranked[0]

    def test_final_score_formula(self):
        mock_db = MagicMock()
        mock_db.get_vectors.return_value = {"s1": [1.0] + [0.0] * (EMBEDDING_DIM - 1)}
        pool = [
            {"script_id": "s1", "win_rate": 0.8, "sas": 0.6, "bg_background": {"industry": "A"}, "bg_bitmask_int": 0},
        ]
        ranked = rank_sentences(pool, query_vec=[1.0] + [0.0] * (EMBEDDING_DIM - 1), db=mock_db, query_bg={"industry": "A"})
        s = ranked[0]
        bg_boost = compute_bg_boost({"industry": "A"}, {"industry": "A"})
        expected = 0.40 * 0.8 + 0.30 * s["vec_score"] + 0.15 * 0.6 + 0.15 * bg_boost
        assert s["final_score"] == pytest.approx(expected, abs=1e-6)


class TestNoOldFunctions:
    def test_compute_context_similarity_removed(self):
        import f006_retrieval_engine.retrieval_ranking as mod
        assert not hasattr(mod, "compute_context_similarity")

    def test_rank_limited_removed(self):
        import f006_retrieval_engine.retrieval_ranking as mod
        assert not hasattr(mod, "_rank_limited")

    def test_rank_full_removed(self):
        import f006_retrieval_engine.retrieval_ranking as mod
        assert not hasattr(mod, "_rank_full")

    def test_ranking_strategy_removed(self):
        import f006_retrieval_engine.retrieval_ranking as mod
        assert not hasattr(mod, "RANKING_STRATEGY")
