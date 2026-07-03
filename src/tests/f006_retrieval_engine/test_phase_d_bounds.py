from unittest.mock import patch

from f006_retrieval_engine.retrieval_engine import (
    _find_matching_nodes_subset,
    descend_for_sentences,
)


def _node(state_id, pool=None, children=None):
    return {"state_id": state_id, "sentence_pool": pool or [], "children": children or []}


class TestCombinatorialCap:
    def test_subset_search_truncated_flagged_on_explosion(self):
        facts = [f"f{i}" for i in range(20)]
        emotions = [f"e{i}" for i in range(20)]
        with patch("f006_retrieval_engine.retrieval_engine._cfg", side_effect=lambda k, d=None: 4096 if k == "decision_tree.max_subset_combinations" else d):
            nodes, conf, fb = _find_matching_nodes_subset(facts, emotions, [], {}, {}, pool_cap=50)
        assert "subset_search_truncated" in fb

    def test_subset_search_unbounded_when_under_cap(self):
        facts = ["f0", "f1"]
        emotions = ["e0"]
        nodes, conf, fb = _find_matching_nodes_subset(facts, emotions, [], {}, {}, pool_cap=50)
        assert "subset_search_truncated" not in fb


class TestBoundedDescend:
    def test_descend_stops_at_max_levels(self):
        depth = 50
        leaf = _node("n50", pool=[{"script_text": "deep", "script_id": "s1"}])
        cur = leaf
        for i in range(depth - 1, 0, -1):
            cur = _node(f"n{i}", children=[cur])
        root = _node("n0", children=[cur])

        with patch("f006_retrieval_engine.retrieval_engine._cfg", side_effect=lambda k, d=None: 4 if k == "decision_tree.find_node_max_levels" else 0.05 if k == "confidence.descend_penalty" else d):
            pool, conf, fb = descend_for_sentences([root])
        assert conf >= 0.0
        assert len(fb) <= 4

    def test_descend_confidence_never_negative(self):
        depth = 100
        leaf = _node("n100", pool=[{"script_text": "deep", "script_id": "s1"}])
        cur = leaf
        for i in range(depth - 1, 0, -1):
            cur = _node(f"n{i}", children=[cur])
        root = _node("n0", children=[cur])

        with patch("f006_retrieval_engine.retrieval_engine._cfg", side_effect=lambda k, d=None: 4 if k == "decision_tree.find_node_max_levels" else 0.05 if k == "confidence.descend_penalty" else d):
            pool, conf, fb = descend_for_sentences([root])
        assert conf >= 0.0
