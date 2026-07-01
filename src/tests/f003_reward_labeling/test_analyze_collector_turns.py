import json
from unittest.mock import patch

from f003_reward_labeling.analyze_collector_turns import _group_collector_results, analyze_collector_turns


def test_analyze_collector_turns_returns_actions():
    mock_resp = '{"action_type": "proposal", "action_group": "plan_proposal", "keyword": "建议分期"}'
    with patch("f003_reward_labeling.analyze_collector_turns.call_deepseek_json", return_value=json.loads(mock_resp)):
        records = [{"call_id": "test", "response": {"dialog": [{"role": "催收员", "text": "建议您分期还款"}]}}]
        result = analyze_collector_turns(records)
        assert "collector_actions" in result


def test_collector_action_has_required_fields():
    mock_resp = '{"action_type": "proposal", "action_group": "plan_proposal", "keyword": "建议分期"}'
    with patch("f003_reward_labeling.analyze_collector_turns.call_deepseek_json", return_value=json.loads(mock_resp)):
        records = [{"call_id": "test", "response": {"dialog": [{"role": "催收员", "text": "建议您分期还款"}]}}]
        result = analyze_collector_turns(records)
        if result["collector_actions"]:
            a = result["collector_actions"][0]
            assert "group_name" in a
            assert "keywords" in a
            assert "frequency" in a
            assert "example_turn" in a
            assert "source" in a


def test_grouping_merges_same_action():
    raw = [
        {"action_type": "proposal", "action_group": "plan_proposal", "keyword": "建议分期", "_turn_text": "建议分期"},
        {"action_type": "proposal", "action_group": "plan_proposal", "keyword": "可以调减", "_turn_text": "可以调减"},
    ]
    grouped = _group_collector_results(raw)
    proposal = [g for g in grouped if g["group_name"] == "plan_proposal"]
    assert len(proposal) == 1
    assert "建议分期" in proposal[0]["keywords"]
    assert "可以调减" in proposal[0]["keywords"]


def test_suggested_collector_actions_included():
    mock_resp = '{"action_type": "proposal", "action_group": "plan_proposal", "keyword": "建议分期"}'
    with patch("f003_reward_labeling.analyze_collector_turns.call_deepseek_json", return_value=json.loads(mock_resp)):
        records = [{"call_id": "test", "response": {"dialog": [{"role": "催收员", "text": "建议您分期还款"}]}}]
        result = analyze_collector_turns(records)
        suggested = [a for a in result["collector_actions"] if a["source"] == "suggested"]
        assert len(suggested) > 0
