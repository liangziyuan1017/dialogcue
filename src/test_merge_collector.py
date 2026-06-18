import importlib.util
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from build_decision_tree import _find_merge_candidates, _word_count, _build_merge_prompt, _llm_should_merge, _merge_turns, _apply_merges


def _load_record(index):
    data_path = os.path.join(os.path.dirname(__file__), "output_rewarded.py")
    spec = importlib.util.spec_from_file_location("mod", data_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.results[index]


class TestWordCount:
    def test_chinese(self):
        assert _word_count("嗯对你好") == 4

    def test_mixed(self):
        assert _word_count("好的，我尽量") == 5

    def test_short(self):
        assert _word_count("嗯") == 1

    def test_empty(self):
        assert _word_count("") == 0

    def test_punctuation_only(self):
        assert _word_count("，，。") == 0


class TestFindMergeCandidates:
    def test_consecutive_collector(self):
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "方案A", "state": {"action": "plan_proposal"}},
            {"turn_index": 1, "role": "催收员", "text": "方案A续", "state": {"action": "plan_proposal"}},
            {"turn_index": 2, "role": "客户", "text": "好的", "state": {}},
        ]
        groups = _find_merge_candidates(turns)
        assert len(groups) >= 1
        assert any(0 in g["collector_indices"] and 1 in g["collector_indices"] for g in groups)

    def test_ack_interruption_under_6_words(self):
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "我给您介绍一下", "state": {"action": "plan_proposal"}},
            {"turn_index": 1, "role": "客户", "text": "嗯", "state": {}},
            {"turn_index": 2, "role": "催收员", "text": "这个方案很好", "state": {"action": "plan_proposal"}},
        ]
        groups = _find_merge_candidates(turns)
        assert len(groups) >= 1
        assert any(0 in g["collector_indices"] and 2 in g["collector_indices"] for g in groups)

    def test_long_customer_reply_not_candidate(self):
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "方案A", "state": {"action": "plan_proposal"}},
            {"turn_index": 1, "role": "客户", "text": "我不要这个方案因为我实在还不上每个月六千多", "state": {"emotions": ["stress"]}},
            {"turn_index": 2, "role": "催收员", "text": "方案B", "state": {"action": "plan_proposal"}},
        ]
        groups = _find_merge_candidates(turns)
        merged_indices = set()
        for g in groups:
            merged_indices.update(g["collector_indices"])
        assert 0 not in merged_indices or 2 not in merged_indices

    def test_dialog2_t14_t15(self):
        r = _load_record(2)
        groups = _find_merge_candidates(r["turns_annotated"])
        has_14_15 = any(14 in g["collector_indices"] and 15 in g["collector_indices"] for g in groups)
        assert has_14_15

    def test_dialog2_t23_t25(self):
        r = _load_record(2)
        groups = _find_merge_candidates(r["turns_annotated"])
        has_23_25 = any(23 in g["collector_indices"] and 25 in g["collector_indices"] for g in groups)
        assert has_23_25

    def test_dialog2_t26_t27(self):
        r = _load_record(2)
        groups = _find_merge_candidates(r["turns_annotated"])
        has_26_27 = any(26 in g["collector_indices"] and 27 in g["collector_indices"] for g in groups)
        assert has_26_27


class TestBuildMergePrompt:
    def test_produces_prompt(self):
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "方案A", "state": {}},
            {"turn_index": 1, "role": "客户", "text": "嗯", "state": {}},
            {"turn_index": 2, "role": "催收员", "text": "方案A续", "state": {}},
        ]
        group = {"collector_indices": [0, 2], "interruption_indices": [1]}
        prompt = _build_merge_prompt(turns, group)
        assert "方案A" in prompt
        assert "MERGE" in prompt
        assert "KEEP" in prompt


class TestLLMShouldMerge:
    def test_merge_response(self, monkeypatch):
        import llm_client
        monkeypatch.setattr(llm_client, "call_deepseek_json", lambda p: {"decision": "MERGE", "reason": "same plan"})
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "方案A", "state": {}},
            {"turn_index": 1, "role": "客户", "text": "嗯", "state": {}},
            {"turn_index": 2, "role": "催收员", "text": "方案A续", "state": {}},
        ]
        group = {"collector_indices": [0, 2], "interruption_indices": [1]}
        should_merge, reason = _llm_should_merge(turns, group)
        assert should_merge is True
        assert "same plan" in reason

    def test_keep_response(self, monkeypatch):
        import llm_client
        monkeypatch.setattr(llm_client, "call_deepseek_json", lambda p: {"decision": "KEEP", "reason": "different topic"})
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "方案A", "state": {}},
            {"turn_index": 1, "role": "客户", "text": "嗯", "state": {}},
            {"turn_index": 2, "role": "催收员", "text": "方案B", "state": {}},
        ]
        group = {"collector_indices": [0, 2], "interruption_indices": [1]}
        should_merge, reason = _llm_should_merge(turns, group)
        assert should_merge is False


class TestMergeTurns:
    def test_merge_two_consecutive(self):
        turns = [
            {"turn_index": 14, "role": "催收员", "text": "方案A", "state": {"action": "plan_proposal"}},
            {"turn_index": 15, "role": "催收员", "text": "方案A续", "state": {"action": "plan_proposal"}},
        ]
        group = {"collector_indices": [0, 1], "interruption_indices": []}
        entry = _merge_turns(turns, group, "call1")
        assert entry["script_text"] == "方案A 方案A续"
        assert "_merged" in entry["script_id"]
        assert entry["merged_from"] == ["call1_t14", "call1_t15"]
        assert entry["collector_action"] == "plan_proposal"

    def test_merge_with_interruption(self):
        turns = [
            {"turn_index": 10, "role": "催收员", "text": "方案A", "state": {"action": "plan_proposal"}},
            {"turn_index": 11, "role": "客户", "text": "嗯", "state": {}},
            {"turn_index": 12, "role": "催收员", "text": "方案A续", "state": {"action": "plan_proposal"}},
        ]
        group = {"collector_indices": [0, 2], "interruption_indices": [1]}
        entry = _merge_turns(turns, group, "call1")
        assert entry["script_text"] == "方案A 方案A续"
        assert entry["merged_from"] == ["call1_t10", "call1_t12"]


class TestApplyMerges:
    def test_merges_applied(self, monkeypatch):
        import llm_client
        monkeypatch.setattr(llm_client, "call_deepseek_json", lambda p: {"decision": "MERGE", "reason": "same"})
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "方案A", "state": {"action": "plan_proposal"}},
            {"turn_index": 1, "role": "催收员", "text": "方案A续", "state": {"action": "plan_proposal"}},
            {"turn_index": 2, "role": "客户", "text": "好的", "state": {}},
        ]
        merge_decisions = {}
        result = _apply_merges(turns, "call1", merge_decisions)
        collector_turns = [t for t in result if t["role"] == "催收员"]
        assert len(collector_turns) == 1
        assert "_merged_entry" in collector_turns[0]

    def test_keep_preserved(self, monkeypatch):
        import llm_client
        monkeypatch.setattr(llm_client, "call_deepseek_json", lambda p: {"decision": "KEEP", "reason": "different"})
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "方案A", "state": {"action": "plan_proposal"}},
            {"turn_index": 1, "role": "客户", "text": "嗯", "state": {}},
            {"turn_index": 2, "role": "催收员", "text": "方案B", "state": {"action": "plan_proposal"}},
        ]
        merge_decisions = {}
        result = _apply_merges(turns, "call1", merge_decisions)
        collector_turns = [t for t in result if t["role"] == "催收员"]
        assert len(collector_turns) == 2

    def test_cache_used(self):
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "方案A", "state": {"action": "plan_proposal"}},
            {"turn_index": 1, "role": "催收员", "text": "方案A续", "state": {"action": "plan_proposal"}},
            {"turn_index": 2, "role": "客户", "text": "好的", "state": {}},
        ]
        merge_decisions = {("call1", (0, 1)): True}
        result = _apply_merges(turns, "call1", merge_decisions)
        collector_turns = [t for t in result if t["role"] == "催收员"]
        assert len(collector_turns) == 1
