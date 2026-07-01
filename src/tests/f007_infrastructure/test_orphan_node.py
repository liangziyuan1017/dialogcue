from unittest.mock import MagicMock, patch

import pytest


def _make_scored_tree():
    return {
        "state_id": "root",
        "path_signature": "root_sig",
        "sentence_pool": [
            {"script_id": "s1", "script_text": "t1", "_node_path_sig": "root_sig"},
            {"script_id": "s2", "script_text": "t2", "_node_path_sig": "orphan_sig"},
        ],
        "children": [],
    }


def _make_all_nodes():
    return [
        {"state_id": "root", "path_signature": "root_sig", "branch_key": {}, "depth": 0},
    ]


def test_orphan_signature_raises_loud():
    from build_tree_and_db import run_build_db

    scored = _make_scored_tree()
    aligned = []
    rewarded = []

    mock_db = MagicMock()
    mock_db.get_node_by_signature.return_value = {"id": 1, "path_signature": "root_sig"}

    with patch("f005_context_scoring.score_tree._collect_tree_nodes", return_value=_make_all_nodes()), \
         patch("f005_context_scoring.score_tree._collect_tree_sentences", return_value=scored["sentence_pool"]), \
         patch("f007_infrastructure.db.SentenceDB", return_value=mock_db), \
         patch("f007_infrastructure.embeddings.embed_texts", return_value=[[0.0] * 4, [0.0] * 4]):
        with pytest.raises(ValueError, match="orphan"):
            run_build_db(scored, aligned, rewarded, "dsn")


def test_no_orphan_succeeds():
    from build_tree_and_db import run_build_db

    scored = {
        "state_id": "root",
        "path_signature": "root_sig",
        "sentence_pool": [
            {"script_id": "s1", "script_text": "t1", "_node_path_sig": "root_sig"},
        ],
        "children": [],
    }

    mock_db = MagicMock()

    def _get_node(sig):
        if sig == "root_sig":
            return {"id": 1, "path_signature": "root_sig"}
        return None

    mock_db.get_node_by_signature.side_effect = _get_node

    with patch("f005_context_scoring.score_tree._collect_tree_nodes", return_value=_make_all_nodes()), \
         patch("f005_context_scoring.score_tree._collect_tree_sentences", return_value=scored["sentence_pool"]), \
         patch("f007_infrastructure.db.SentenceDB", return_value=mock_db), \
         patch("f007_infrastructure.embeddings.embed_texts", return_value=[[0.0] * 4]):
        run_build_db(scored, [], [], "dsn")
