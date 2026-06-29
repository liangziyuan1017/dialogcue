import pytest
from unittest.mock import patch, MagicMock
from f006_retrieval_engine.state_extraction import (
    extract_state_llm,
    extract_state_keyword,
    extract_state,
    merge_state,
)


TAXONOMY = {
    "facts": [{"group_name": "financial_hardship", "keywords": ["没钱", "没有钱", "经济困难"]}],
    "emotions": [{"group_name": "pleading", "keywords": ["求求你", "拜托"]}],
    "collector_actions": [{"group_name": "empathy", "keywords": ["理解", "体谅"]}],
}


class TestExtractStateLLM:
    def test_returns_correct_structure(self):
        mock_response = {"facts": ["financial_hardship"], "emotions": [], "actions": [], "confidence": 0.9}
        with patch("f006_retrieval_engine.state_extraction.call_deepseek_json", return_value=mock_response):
            result = extract_state_llm("我现在没钱还", TAXONOMY)
        assert "facts" in result
        assert "emotions" in result
        assert "actions" in result
        assert "confidence" in result
        assert result["method"] == "llm"

    def test_returns_lists(self):
        mock_response = {"facts": ["financial_hardship"], "emotions": ["pleading"], "actions": []}
        with patch("f006_retrieval_engine.state_extraction.call_deepseek_json", return_value=mock_response):
            result = extract_state_llm("我现在没钱还", TAXONOMY)
        assert isinstance(result["facts"], list)
        assert isinstance(result["emotions"], list)
        assert isinstance(result["actions"], list)


class TestExtractStateKeyword:
    def test_returns_correct_structure(self):
        mock_db = MagicMock()
        mock_db.keyword_search.return_value = [
            {"group_name": "financial_hardship", "category": "facts"},
        ]
        result = extract_state_keyword("我现在没钱还", TAXONOMY, db=mock_db)
        assert "facts" in result
        assert "emotions" in result
        assert "actions" in result
        assert result["method"] == "keyword"

    def test_no_db_returns_empty(self):
        result = extract_state_keyword("我现在没钱还", TAXONOMY, db=None)
        assert result["facts"] == []
        assert result["emotions"] == []
        assert result["actions"] == []
        assert result["confidence"] == 0.0


class TestExtractState:
    def test_llm_first(self):
        mock_response = {"facts": ["financial_hardship"], "emotions": [], "actions": []}
        with patch("f006_retrieval_engine.state_extraction.call_deepseek_json", return_value=mock_response):
            result = extract_state("我现在没钱还", TAXONOMY)
        assert result["method"] == "llm"

    def test_keyword_fallback_on_llm_failure(self):
        mock_db = MagicMock()
        mock_db.keyword_search.return_value = [
            {"group_name": "financial_hardship", "category": "facts"},
        ]
        with patch("f006_retrieval_engine.state_extraction.call_deepseek_json", side_effect=Exception("API error")):
            result = extract_state("我现在没钱还", TAXONOMY, db=mock_db)
        assert result["method"] == "keyword"


class TestMergeState:
    def test_merges_new_items(self):
        existing = {"facts": ["a"], "emotions": [], "actions": []}
        new = {"facts": ["b"], "emotions": ["e1"], "actions": []}
        result = merge_state(existing, new)
        assert result["facts"] == ["a", "b"]
        assert result["emotions"] == ["e1"]

    def test_deduplicates(self):
        existing = {"facts": ["a"], "emotions": [], "actions": []}
        new = {"facts": ["a"], "emotions": [], "actions": []}
        result = merge_state(existing, new)
        assert result["facts"] == ["a"]

    def test_preserves_insertion_order(self):
        existing = {"facts": ["b"], "emotions": [], "actions": []}
        new = {"facts": ["a"], "emotions": [], "actions": []}
        result = merge_state(existing, new)
        assert result["facts"] == ["b", "a"]

    def test_empty_existing(self):
        existing = {"facts": [], "emotions": [], "actions": []}
        new = {"facts": ["a"], "emotions": ["e1"], "actions": ["act1"]}
        result = merge_state(existing, new)
        assert result["facts"] == ["a"]
        assert result["emotions"] == ["e1"]
        assert result["actions"] == ["act1"]

    def test_empty_new(self):
        existing = {"facts": ["a"], "emotions": ["e1"], "actions": []}
        new = {"facts": [], "emotions": [], "actions": []}
        result = merge_state(existing, new)
        assert result["facts"] == ["a"]

    def test_all_three_categories(self):
        existing = {"facts": ["a"], "emotions": ["e1"], "actions": ["act1"]}
        new = {"facts": ["b"], "emotions": ["e2"], "actions": ["act2"]}
        result = merge_state(existing, new)
        assert result["facts"] == ["a", "b"]
        assert result["emotions"] == ["e1", "e2"]
        assert result["actions"] == ["act1", "act2"]
