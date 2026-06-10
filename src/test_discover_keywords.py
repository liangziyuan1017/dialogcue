from unittest.mock import patch
import json
import os
import tempfile
from src.discover_keywords import discover_keywords


def _mock_customer_response():
    return [{"facts": [{"keyword": "失业", "group": "unemployment"}], "emotions": [{"keyword": "焦虑", "group": "anxiety"}], "willingness": "weak"}]


def _mock_collector_response():
    return [{"action_group": "greeting"}]


def _mock_cluster_response():
    return {"levels": [{"level": "weak", "definition": "有意愿但无力", "boundary": "说想还但没钱", "example_turns": [{"text": "想还但没钱", "reason": "有意愿"}]}]}


def test_discover_keywords_writes_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "state_keywords.json")
        labeled_path = os.path.join(tmpdir, "output_labeled.py")
        with patch("src.discover_keywords.call_deepseek_json", side_effect=[_mock_customer_response(), _mock_collector_response(), _mock_cluster_response()]):
            result = discover_keywords(output_path=out_path, labeled_output_path=labeled_path)
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
        labeled_path = os.path.join(tmpdir, "output_labeled.py")
        with patch("src.discover_keywords.call_deepseek_json", side_effect=[_mock_customer_response(), _mock_collector_response(), _mock_cluster_response()]):
            discover_keywords(output_path=out_path, labeled_output_path=labeled_path)
            assert os.path.exists(labeled_path)
            with open(labeled_path) as f:
                content = f.read()
            assert content.startswith("results = ")
            data = json.loads(content[len("results = "):])
            assert isinstance(data, list)
            assert len(data) > 0


def test_labeled_turns_have_state_field():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "state_keywords.json")
        labeled_path = os.path.join(tmpdir, "output_labeled.py")
        with patch("src.discover_keywords.call_deepseek_json", side_effect=[_mock_customer_response(), _mock_collector_response(), _mock_cluster_response()]):
            discover_keywords(output_path=out_path, labeled_output_path=labeled_path)
            with open(labeled_path) as f:
                data = json.loads(f.read()[len("results = "):])
            has_state = False
            for record in data:
                for turn in record["response"]["dialog"]:
                    if "state" in turn:
                        has_state = True
                        s = turn["state"]
                        assert isinstance(s, dict)
            assert has_state
