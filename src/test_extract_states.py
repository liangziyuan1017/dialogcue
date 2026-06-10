import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from extract_states import build_taxonomy_index, build_customer_prompt, build_collector_prompt, extract_turn_state, extract_all_states, write_output_states, main


def _load_taxonomy():
    path = os.path.join(os.path.dirname(__file__), "..", "src", "state_keywords.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_build_taxonomy_index_returns_all_dimensions():
    taxonomy = _load_taxonomy()
    index = build_taxonomy_index(taxonomy)
    assert "fact_groups" in index
    assert "emotion_groups" in index
    assert "willingness_levels" in index
    assert "collector_action_groups" in index


def test_fact_groups_have_name_and_keywords():
    taxonomy = _load_taxonomy()
    index = build_taxonomy_index(taxonomy)
    for g in index["fact_groups"]:
        assert "group_name" in g
        assert "keywords" in g
        assert isinstance(g["keywords"], list)


def test_emotion_groups_have_name_and_keywords():
    taxonomy = _load_taxonomy()
    index = build_taxonomy_index(taxonomy)
    for g in index["emotion_groups"]:
        assert "group_name" in g
        assert "keywords" in g


def test_willingness_levels_have_level_and_definition():
    taxonomy = _load_taxonomy()
    index = build_taxonomy_index(taxonomy)
    for w in index["willingness_levels"]:
        assert "level" in w
        assert "definition" in w


def test_collector_action_groups_have_name_and_keywords():
    taxonomy = _load_taxonomy()
    index = build_taxonomy_index(taxonomy)
    for g in index["collector_action_groups"]:
        assert "group_name" in g
        assert "keywords" in g


def test_counts_match_source():
    taxonomy = _load_taxonomy()
    index = build_taxonomy_index(taxonomy)
    assert len(index["fact_groups"]) == len(taxonomy["facts"])
    assert len(index["emotion_groups"]) == len(taxonomy["emotions"])
    assert len(index["willingness_levels"]) == len(taxonomy["willingness_levels"])
    assert len(index["collector_action_groups"]) == len(
        [g for g in taxonomy["collector_actions"] if g.get("group_name") is not None]
    )


def test_customer_prompt_contains_turn_text():
    taxonomy = _load_taxonomy()
    index = build_taxonomy_index(taxonomy)
    prompt = build_customer_prompt("我现在没钱还", index)
    assert "我现在没钱还" in prompt


def test_customer_prompt_contains_fact_groups():
    taxonomy = _load_taxonomy()
    index = build_taxonomy_index(taxonomy)
    prompt = build_customer_prompt("test", index)
    for g in index["fact_groups"]:
        assert g["group_name"] in prompt


def test_customer_prompt_contains_emotion_groups():
    taxonomy = _load_taxonomy()
    index = build_taxonomy_index(taxonomy)
    prompt = build_customer_prompt("test", index)
    for g in index["emotion_groups"]:
        assert g["group_name"] in prompt


def test_customer_prompt_contains_willingness_levels():
    taxonomy = _load_taxonomy()
    index = build_taxonomy_index(taxonomy)
    prompt = build_customer_prompt("test", index)
    for w in index["willingness_levels"]:
        assert w["level"] in prompt


def test_collector_prompt_contains_turn_text():
    taxonomy = _load_taxonomy()
    index = build_taxonomy_index(taxonomy)
    prompt = build_collector_prompt("您好，请问是张先生吗", index)
    assert "您好，请问是张先生吗" in prompt


def test_collector_prompt_contains_action_groups():
    taxonomy = _load_taxonomy()
    index = build_taxonomy_index(taxonomy)
    prompt = build_collector_prompt("test", index)
    for g in index["collector_action_groups"]:
        assert g["group_name"] in prompt


def test_extract_customer_turn_returns_state_keywords():
    from unittest.mock import patch
    taxonomy = _load_taxonomy()
    index = build_taxonomy_index(taxonomy)
    turn = {"role": "客户", "text": "我现在没钱还"}
    with patch("extract_states.call_deepseek_json", return_value={"facts": ["financial_hardship"], "emotions": ["distress"], "willingness": "Ambivalent"}):
        result = extract_turn_state(turn, index)
    assert "facts" in result
    assert "emotions" in result
    assert "willingness" in result


def test_extract_collector_turn_returns_action_type():
    from unittest.mock import patch
    taxonomy = _load_taxonomy()
    index = build_taxonomy_index(taxonomy)
    turn = {"role": "催收员", "text": "您好，请问是张先生吗"}
    with patch("extract_states.call_deepseek_json", return_value={"action_type": "greeting"}):
        result = extract_turn_state(turn, index)
    assert "action_type" in result


def test_extract_all_skips_annotated_turns():
    from unittest.mock import patch
    taxonomy = _load_taxonomy()
    index = build_taxonomy_index(taxonomy)
    records = [
        {
            "call_id": "test1",
            "turns_annotated": [
                {"turn_index": 0, "role": "客户", "text": "我没钱", "state": {"facts": ["financial_hardship"], "willingness": "Resistant"}},
                {"turn_index": 1, "role": "催收员", "text": "您好"},
            ],
        }
    ]
    with patch("extract_states.call_deepseek_json", return_value={"action_type": "greeting"}):
        result = extract_all_states(records, index, delay=0)
    assert result[0]["turns_annotated"][0]["state"]["facts"] == ["financial_hardship"]
    assert result[0]["turns_annotated"][0].get("labeled") is True


def test_extract_all_processes_unannotated_turns():
    from unittest.mock import patch
    taxonomy = _load_taxonomy()
    index = build_taxonomy_index(taxonomy)
    records = [
        {
            "call_id": "test2",
            "turns_annotated": [
                {"turn_index": 0, "role": "客户", "text": "我没钱"},
                {"turn_index": 1, "role": "催收员", "text": "您好"},
            ],
        }
    ]
    call_count = 0

    def mock_llm(prompt):
        nonlocal call_count
        call_count += 1
        if "客户" in prompt:
            return {"facts": ["financial_hardship"], "emotions": ["distress"], "willingness": "Resistant"}
        return {"action_type": "greeting"}

    with patch("extract_states.call_deepseek_json", side_effect=mock_llm):
        result = extract_all_states(records, index, delay=0)
    assert call_count == 2
    assert "state" in result[0]["turns_annotated"][0]
    assert "state" in result[0]["turns_annotated"][1]


def test_extract_all_customer_state_has_state_keywords():
    from unittest.mock import patch
    taxonomy = _load_taxonomy()
    index = build_taxonomy_index(taxonomy)
    records = [
        {
            "call_id": "test3",
            "turns_annotated": [
                {"turn_index": 0, "role": "客户", "text": "我没钱"},
            ],
        }
    ]
    with patch("extract_states.call_deepseek_json", return_value={"facts": ["financial_hardship"], "emotions": ["distress"], "willingness": "Resistant"}):
        result = extract_all_states(records, index, delay=0)
    state = result[0]["turns_annotated"][0]["state"]
    assert "facts" in state
    assert "emotions" in state
    assert "willingness" in state


def test_extract_all_collector_state_has_action_type_and_text():
    from unittest.mock import patch
    taxonomy = _load_taxonomy()
    index = build_taxonomy_index(taxonomy)
    records = [
        {
            "call_id": "test4",
            "turns_annotated": [
                {"turn_index": 0, "role": "催收员", "text": "您好请问是张先生吗"},
            ],
        }
    ]
    with patch("extract_states.call_deepseek_json", return_value={"action_type": "greeting"}):
        result = extract_all_states(records, index, delay=0)
    state = result[0]["turns_annotated"][0]["state"]
    assert state["action_type"] == "greeting"
    assert state["action_text"] == "您好请问是张先生吗"


def test_write_output_states_creates_importable_file():
    import tempfile
    import importlib.util as ilu
    records = [{"call_id": "test", "turns_annotated": []}]
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
        path = f.name
    try:
        write_output_states(records, path)
        spec = ilu.spec_from_file_location("test_output", path)
        mod = ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "results")
        assert len(mod.results) == 1
        assert mod.results[0]["call_id"] == "test"
    finally:
        os.unlink(path)


def test_main_loads_and_processes():
    from unittest.mock import patch, MagicMock
    import tempfile
    import importlib.util as ilu2
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as f:
        out_path = f.name
    try:
        mock_records = [{"call_id": "test_main", "turns_annotated": [
            {"turn_index": 0, "role": "客户", "text": "我没钱"},
            {"turn_index": 1, "role": "催收员", "text": "您好"},
        ]}]
        with patch("extract_states._load_aligned", return_value=mock_records), \
             patch("extract_states._load_taxonomy", return_value=_load_taxonomy()), \
             patch("extract_states.call_deepseek_json", side_effect=[
                 {"facts": ["financial_hardship"], "emotions": ["distress"], "willingness": "Resistant"},
                 {"action_type": "greeting"},
             ]):
            main(output_path=out_path)
        spec = ilu2.spec_from_file_location("test_out", out_path)
        mod = ilu2.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert len(mod.results) == 1
        turns = mod.results[0]["turns_annotated"]
        assert "state" in turns[0]
        assert "state" in turns[1]
    finally:
        os.unlink(out_path)
