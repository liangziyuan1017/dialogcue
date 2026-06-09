from unittest.mock import patch
import json
import os
import tempfile
from src.discover_keywords import discover_keywords


def test_discover_keywords_writes_json():
    mock_customer = {"facts": [{"group_name": "unemployment", "keywords": ["失业"], "frequency": 1, "example_turn": "我失业了", "source": "observed"}], "emotions": [{"group_name": "anxiety", "keywords": ["焦虑"], "frequency": 1, "example_turn": "很焦虑", "source": "observed"}]}
    mock_collector = {"collector_actions": [{"group_name": "greeting", "keywords": ["您好"], "frequency": 1, "example_turn": "您好", "source": "observed"}]}
    mock_willingness = [{"level": "weak", "definition": "有意愿但无力", "boundary": "说想还但没钱", "example_turns": [{"text": "想还但没钱", "reason": "有意愿"}]}]

    with patch("src.discover_keywords.analyze_customer_turns", return_value=mock_customer), \
         patch("src.discover_keywords.analyze_collector_turns", return_value=mock_collector), \
         patch("src.discover_keywords.define_willingness_levels", return_value=mock_willingness):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "state_keywords.json")
            result = discover_keywords(output_path=out_path)
            assert os.path.exists(out_path)
            with open(out_path) as f:
                data = json.load(f)
            assert "facts" in data
            assert "emotions" in data
            assert "willingness_levels" in data
            assert "collector_actions" in data


def test_discover_keywords_returns_dict():
    mock_customer = {"facts": [], "emotions": []}
    mock_collector = {"collector_actions": []}
    mock_willingness = []

    with patch("src.discover_keywords.analyze_customer_turns", return_value=mock_customer), \
         patch("src.discover_keywords.analyze_collector_turns", return_value=mock_collector), \
         patch("src.discover_keywords.define_willingness_levels", return_value=mock_willingness):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "state_keywords.json")
            result = discover_keywords(output_path=out_path)
            assert "facts" in result
            assert "emotions" in result
            assert "willingness_levels" in result
            assert "collector_actions" in result
