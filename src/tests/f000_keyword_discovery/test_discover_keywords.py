import json
import os
import tempfile
from unittest.mock import patch

from f000_keyword_discovery.discover_keywords import discover_keywords


def _mock_customer_response():
    return [{"facts": [{"keyword": "失业", "group": "unemployment"}], "emotions": [{"keyword": "焦虑", "group": "anxiety"}], "willingness": "weak"}]


def _mock_collector_response():
    return [{"action_group": "greeting"}]


def _mock_cluster_response():
    return {"levels": [{"level": "weak", "definition": "有意愿但无力", "boundary": "说想还但没钱", "example_turns": [{"text": "想还但没钱", "reason": "有意愿"}]}]}


def _mock_records():
    return [{
        "response": {
            "dialog": [
                {"role": "催收员", "text": "您好，请问您是张先生吗？"},
                {"role": "客户", "text": "是，我最近失业了，真的还不上"},
            ]
        }
    }]


def test_discover_keywords_writes_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "state_keywords.json")
        labeled_path = os.path.join(tmpdir, "output_labeled.jsonl")
        with patch("f000_keyword_discovery.discover_keywords.call_deepseek_json", side_effect=[_mock_customer_response(), _mock_collector_response(), _mock_cluster_response()]):
            discover_keywords(_mock_records(), output_path=out_path, labeled_output_path=labeled_path)
            assert os.path.exists(out_path)
            with open(out_path) as f:
                data = json.load(f)
            assert "facts" in data
            assert "emotions" in data
            assert "willingness_levels" in data
            assert "collector_actions" in data


def test_discover_keywords_writes_labeled_output():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "state_keywords.json")
        labeled_path = os.path.join(tmpdir, "output_labeled.jsonl")
        with patch("f000_keyword_discovery.discover_keywords.call_deepseek_json", side_effect=[_mock_customer_response(), _mock_collector_response(), _mock_cluster_response()]):
            discover_keywords(_mock_records(), output_path=out_path, labeled_output_path=labeled_path)
            assert os.path.exists(labeled_path)
            with open(labeled_path) as f:
                lines = [line for line in f if line.strip()]
            data = [json.loads(line) for line in lines]
            assert isinstance(data, list)
            assert len(data) > 0


def test_labeled_turns_have_state_field():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "state_keywords.json")
        labeled_path = os.path.join(tmpdir, "output_labeled.jsonl")
        with patch("f000_keyword_discovery.discover_keywords.call_deepseek_json", side_effect=[_mock_customer_response(), _mock_collector_response(), _mock_cluster_response()]):
            discover_keywords(_mock_records(), output_path=out_path, labeled_output_path=labeled_path)
            with open(labeled_path) as f:
                data = [json.loads(line) for line in f if line.strip()]
            has_state = False
            for record in data:
                for turn in record["response"]["dialog"]:
                    if "state" in turn:
                        has_state = True
                        s = turn["state"]
                        assert isinstance(s, dict)
            assert has_state
