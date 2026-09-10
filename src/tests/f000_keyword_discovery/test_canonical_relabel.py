import json
import os
import tempfile
from unittest.mock import patch

from f000_keyword_discovery.canonical_relabel import relabel_label_list, relabel_records
from f000_keyword_discovery.discover_keywords import discover_keywords


def test_relabel_label_list_maps_via_csv():
    # unemployment → income_loss in facts_relabeled.csv; anxiety is already canonical
    assert relabel_label_list(["unemployment"], "facts") == ["income_loss"]
    assert relabel_label_list(["anxiety"], "emotions") == ["anxiety"]


def test_relabel_records_rewrites_state_in_place():
    records = [{
        "call_id": "x",
        "response": {
            "dialog": [
                {
                    "role": "客户",
                    "text": "失业了",
                    "state": {"facts": ["unemployment"], "emotions": ["anxiety"], "willingness": "weak"},
                }
            ]
        },
    }]
    stats = relabel_records(records)
    state = records[0]["response"]["dialog"][0]["state"]
    assert state["facts"] == ["income_loss"]
    assert state["emotions"] == ["anxiety"]
    assert state["willingness"] == "weak"
    assert stats["facts_out"] == 1
    assert stats["emotions_out"] == 1


def _mock_customer_response():
    return [{"facts": [{"keyword": "失业", "group": "unemployment"}], "emotions": [{"keyword": "焦虑", "group": "anxiety"}], "willingness": "weak"}]


def _mock_collector_response():
    return [{"action_group": "greeting"}]


def _mock_cluster_response():
    return {"levels": [{"level": "weak", "definition": "有意愿但无力", "boundary": "说想还但没钱", "example_turns": [{"text": "想还但没钱", "reason": "有意愿"}]}]}


def _mock_records():
    return [{
        "call_id": "test1",
        "response": {
            "dialog": [
                {"role": "催收员", "text": "您好，请问您是张先生吗？"},
                {"role": "客户", "text": "是，我最近失业了，真的还不上"},
            ]
        }
    }]


def test_discover_keywords_writes_canonical_fact_labels():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "state_keywords.json")
        labeled_path = os.path.join(tmpdir, "output_labeled.jsonl")
        with patch(
            "f000_keyword_discovery.discover_keywords.call_deepseek_json",
            side_effect=[_mock_customer_response(), _mock_collector_response(), _mock_cluster_response()],
        ):
            discover_keywords(_mock_records(), output_path=out_path, labeled_output_path=labeled_path)
        with open(labeled_path) as f:
            data = [json.loads(line) for line in f if line.strip()]
        customer = next(t for t in data[0]["response"]["dialog"] if t["role"] == "客户")
        assert customer["state"]["facts"] == ["income_loss"]
        assert customer["state"]["emotions"] == ["anxiety"]
