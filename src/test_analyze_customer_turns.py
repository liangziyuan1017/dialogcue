from unittest.mock import patch, MagicMock
from src.analyze_customer_turns import analyze_customer_turns, _build_customer_prompt, _group_results


def test_analyze_customer_turns_returns_facts_and_emotions():
    mock_llm_responses = [
        '{"facts": [{"keyword": "失业", "group": "unemployment"}], "emotions": [{"keyword": "焦虑", "group": "anxiety"}], "willingness_signal": "weak"}'
    ]
    with patch("src.analyze_customer_turns.call_deepseek_json", side_effect=mock_llm_responses * 100):
        records = [{"call_id": "test", "response": {"dialog": [{"role": "客户", "text": "我失业了，很焦虑"}]}}]
        result = analyze_customer_turns(records)
        assert "facts" in result
        assert "emotions" in result


def test_fact_entry_has_required_fields():
    mock_resp = '{"facts": [{"keyword": "失业", "group": "unemployment"}], "emotions": [{"keyword": "焦虑", "group": "anxiety"}], "willingness_signal": "weak"}'
    with patch("src.analyze_customer_turns.call_deepseek_json", return_value=__import__("json").loads(mock_resp)):
        records = [{"call_id": "test", "response": {"dialog": [{"role": "客户", "text": "我失业了"}]}}]
        result = analyze_customer_turns(records)
        if result["facts"]:
            f = result["facts"][0]
            assert "group_name" in f
            assert "keywords" in f
            assert "frequency" in f
            assert "example_turn" in f
            assert "source" in f


def test_grouping_merges_same_meaning():
    raw_results = [
        {"facts": [{"keyword": "没钱", "group": "financial_hardship"}], "emotions": [], "willingness_signal": "weak"},
        {"facts": [{"keyword": "经济困难", "group": "financial_hardship"}], "emotions": [], "willingness_signal": "weak"},
    ]
    grouped = _group_results(raw_results, "facts")
    financial = [g for g in grouped if g["group_name"] == "financial_hardship"]
    assert len(financial) == 1
    assert "没钱" in financial[0]["keywords"]
    assert "经济困难" in financial[0]["keywords"]
    assert financial[0]["frequency"] == 2


def test_suggested_keywords_included():
    mock_resp = '{"facts": [{"keyword": "失业", "group": "unemployment"}], "emotions": [{"keyword": "焦虑", "group": "anxiety"}], "willingness_signal": "weak"}'
    with patch("src.analyze_customer_turns.call_deepseek_json", return_value=__import__("json").loads(mock_resp)):
        records = [{"call_id": "test", "response": {"dialog": [{"role": "客户", "text": "我失业了"}]}}]
        result = analyze_customer_turns(records)
        suggested_facts = [f for f in result["facts"] if f["source"] == "suggested"]
        assert len(suggested_facts) > 0
        for sf in suggested_facts:
            assert sf["frequency"] == 0
