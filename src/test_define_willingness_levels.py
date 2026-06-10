from unittest.mock import patch
import json
from src.define_willingness_levels import define_willingness_levels


def _make_cluster_result(levels):
    return json.dumps({"levels": levels})


CLUSTER_RESULT = _make_cluster_result([
    {"level": "resistant", "definition": "明确拒绝还款", "boundary": "说'不还'或挂断", "example_turns": [{"text": "我不还", "reason": "明确拒绝"}]},
    {"level": "weak", "definition": "有意愿但无力", "boundary": "说想还但没钱", "example_turns": [{"text": "想还但没钱", "reason": "有意愿表达"}]},
    {"level": "conditional", "definition": "有条件同意", "boundary": "提出前提条件", "example_turns": [{"text": "如果分期我可以", "reason": "设前提条件"}]},
    {"level": "strong", "definition": "明确承诺还款", "boundary": "给出具体时间或金额", "example_turns": [{"text": "我明天还", "reason": "给出具体时间"}]},
])


def test_returns_ordered_levels():
    classify_resp = [{"willingness_signal": "weak"}]
    cluster_resp = json.loads(CLUSTER_RESULT)
    with patch("src.define_willingness_levels.call_deepseek_json", side_effect=[classify_resp, cluster_resp]):
        records = [{"call_id": "test", "response": {"dialog": [{"role": "客户", "text": "想还但没钱"}]}}]
        result = define_willingness_levels(records)
        assert isinstance(result, list)
        assert len(result) >= 2


def test_level_has_required_fields():
    classify_resp = [{"willingness_signal": "weak"}]
    cluster_resp = json.loads(_make_cluster_result([
        {"level": "resistant", "definition": "拒绝", "boundary": "说no", "example_turns": [{"text": "不还", "reason": "拒绝"}]},
        {"level": "strong", "definition": "同意", "boundary": "说ok", "example_turns": [{"text": "好我还", "reason": "同意"}]},
    ]))
    with patch("src.define_willingness_levels.call_deepseek_json", side_effect=[classify_resp, cluster_resp]):
        records = [{"call_id": "test", "response": {"dialog": [{"role": "客户", "text": "好我还"}]}}]
        result = define_willingness_levels(records)
        for lvl in result:
            assert "level" in lvl
            assert "definition" in lvl
            assert "boundary" in lvl
            assert "example_turns" in lvl
            assert len(lvl["example_turns"]) >= 1
            for ex in lvl["example_turns"]:
                assert "text" in ex
                assert "reason" in ex


def test_levels_ordered_resistant_to_cooperative():
    classify_resp = [{"willingness_signal": "weak"}]
    cluster_resp = json.loads(_make_cluster_result([
        {"level": "resistant", "definition": "拒绝", "boundary": "说no", "example_turns": [{"text": "不还", "reason": "拒绝"}]},
        {"level": "weak", "definition": "想还但没钱", "boundary": "有意愿但无力", "example_turns": [{"text": "想还", "reason": "有意愿"}]},
        {"level": "strong", "definition": "同意", "boundary": "说ok", "example_turns": [{"text": "好我还", "reason": "同意"}]},
    ]))
    with patch("src.define_willingness_levels.call_deepseek_json", side_effect=[classify_resp, cluster_resp]):
        records = [{"call_id": "test", "response": {"dialog": [{"role": "客户", "text": "想还"}]}}]
        result = define_willingness_levels(records)
        assert result[0]["level"] == "resistant"
        assert result[-1]["level"] == "strong"
