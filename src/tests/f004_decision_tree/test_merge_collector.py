import importlib.util
import json
import os

import pytest

from f004_decision_tree.build_decision_tree import _find_merge_candidates, _word_count, _build_merge_prompt, _llm_should_merge, _merge_turns, _apply_merges, MAX_MERGED_WORDS, ACK_MAX_WORDS, _is_ack_interruption, _ensure_same_action_merged


def _load_record(index):
    data_path = os.path.join(os.path.dirname(__file__), "../..", "f003_reward_labeling", "output_rewarded.py")
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

    def test_ack_interruption_under_15_words(self):
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "我给您介绍一下", "state": {"action": "plan_proposal"}},
            {"turn_index": 1, "role": "客户", "text": "但是个性化分期", "state": {}},
            {"turn_index": 2, "role": "催收员", "text": "这个方案更好", "state": {"action": "plan_proposal"}},
        ]
        groups = _find_merge_candidates(turns)
        assert len(groups) >= 1
        assert any(0 in g["collector_indices"] and 2 in g["collector_indices"] for g in groups)

    def test_ack_with_emotions_not_candidate(self):
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "方案A", "state": {"action": "plan_proposal"}},
            {"turn_index": 1, "role": "客户", "text": "嗯", "state": {"emotions": ["stress"]}},
            {"turn_index": 2, "role": "催收员", "text": "方案B", "state": {"action": "plan_proposal"}},
        ]
        groups = _find_merge_candidates(turns)
        merged_indices = set()
        for g in groups:
            merged_indices.update(g["collector_indices"])
        assert 0 not in merged_indices or 2 not in merged_indices

    def test_long_customer_reply_not_candidate(self):
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "方案A", "state": {"action": "plan_proposal"}},
            {"turn_index": 1, "role": "客户", "text": "我不要这个方案因为我实在还不上每个月六千多块钱真的太多了", "state": {}},
            {"turn_index": 2, "role": "催收员", "text": "方案B", "state": {"action": "plan_proposal"}},
        ]
        groups = _find_merge_candidates(turns)
        merged_indices = set()
        for g in groups:
            merged_indices.update(g["collector_indices"])
        assert 0 not in merged_indices or 2 not in merged_indices

    def test_label1_turn_treated_as_absent(self):
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "方案A", "state": {"action": "plan_proposal"}},
            {"turn_index": 1, "role": "客户", "text": "一些话", "label": 1, "state": {}},
            {"turn_index": 2, "role": "催收员", "text": "方案A续", "state": {"action": "plan_proposal"}},
        ]
        groups = _find_merge_candidates(turns)
        assert len(groups) >= 1
        g = groups[0]
        assert 0 in g["collector_indices"] and 2 in g["collector_indices"]
        assert 1 in g.get("skipped_label1_indices", [])

    def test_label1_turn_removed_on_merge(self, monkeypatch):
        import infra.llm_client as llm_client
        monkeypatch.setattr(llm_client, "call_deepseek_json", lambda p: {"groups": [[0, 1]], "reason": "same"})
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "方案A", "state": {"action": "plan_proposal"}},
            {"turn_index": 1, "role": "客户", "text": "一些话", "label": 1, "state": {}},
            {"turn_index": 2, "role": "催收员", "text": "方案A续", "state": {"action": "plan_proposal"}},
        ]
        merge_decisions = {}
        result = _apply_merges(turns, "call1", merge_decisions)
        assert all(t.get("label") != 1 for t in result)
        collector_turns = [t for t in result if t["role"] == "催收员"]
        assert len(collector_turns) == 1

class TestIsAckInterruption:
    def test_short_no_facts(self):
        assert _is_ack_interruption({"role": "客户", "text": "嗯", "state": {}})

    def test_medium_no_facts(self):
        assert _is_ack_interruption({"role": "客户", "text": "但是个性化分期", "state": {}})

    def test_with_emotions(self):
        assert not _is_ack_interruption({"role": "客户", "text": "嗯", "state": {"emotions": ["stress"]}})

    def test_with_facts(self):
        assert not _is_ack_interruption({"role": "客户", "text": "嗯", "state": {"facts": ["financial_hardship"]}})

    def test_label1(self):
        assert not _is_ack_interruption({"role": "客户", "text": "嗯", "label": 1, "state": {}})

    def test_too_long(self):
        assert not _is_ack_interruption({"role": "客户", "text": "字" * 16, "state": {}})

    def test_collector_never(self):
        assert not _is_ack_interruption({"role": "催收员", "text": "嗯", "state": {}})


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

    def test_dialog2_t35_t37_t39(self):
        r = _load_record(2)
        groups = _find_merge_candidates(r["turns_annotated"])
        has_35_37 = any(35 in g["collector_indices"] and 37 in g["collector_indices"] for g in groups)
        has_37_39 = any(37 in g["collector_indices"] and 39 in g["collector_indices"] for g in groups)
        assert has_35_37 or has_37_39


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
        assert str(MAX_MERGED_WORDS) in prompt


class TestLLMShouldMerge:
    def test_merge_response(self, monkeypatch):
        import infra.llm_client as llm_client
        monkeypatch.setattr(llm_client, "call_deepseek_json", lambda p: {"groups": [[0, 1]], "reason": "same plan"})
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "方案A", "state": {}},
            {"turn_index": 1, "role": "客户", "text": "嗯", "state": {}},
            {"turn_index": 2, "role": "催收员", "text": "方案A续", "state": {}},
        ]
        group = {"collector_indices": [0, 2], "interruption_indices": [1]}
        result = _llm_should_merge(turns, group)
        assert result == [[0, 1]]

    def test_keep_response(self, monkeypatch):
        import infra.llm_client as llm_client
        monkeypatch.setattr(llm_client, "call_deepseek_json", lambda p: {"groups": [[0], [1]], "reason": "different topic"})
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "方案A", "state": {}},
            {"turn_index": 1, "role": "客户", "text": "嗯", "state": {}},
            {"turn_index": 2, "role": "催收员", "text": "方案B", "state": {}},
        ]
        group = {"collector_indices": [0, 2], "interruption_indices": [1]}
        result = _llm_should_merge(turns, group)
        assert result == [[0], [1]]

    def test_same_action_auto_merge(self):
        turns = [
            {"turn_index": 35, "role": "催收员", "text": "方案A", "state": {"action": "pressure"}},
            {"turn_index": 37, "role": "催收员", "text": "方案A续", "state": {"action": "pressure"}},
            {"turn_index": 39, "role": "催收员", "text": "方案A再续", "state": {"action": "pressure"}},
        ]
        group = {"collector_indices": [0, 1, 2], "interruption_indices": []}
        result = _llm_should_merge(turns, group)
        assert result == [[0, 1, 2]]

    def test_same_action_auto_merge_with_word_limit(self):
        long_a = "字" * 100
        long_b = "字" * 60
        turns = [
            {"turn_index": 0, "role": "催收员", "text": long_a, "state": {"action": "pressure"}},
            {"turn_index": 1, "role": "催收员", "text": long_b, "state": {"action": "pressure"}},
        ]
        group = {"collector_indices": [0, 1], "interruption_indices": []}
        result = _llm_should_merge(turns, group)
        assert result == [[0], [1]]

    def test_partial_merge_response(self, monkeypatch):
        import infra.llm_client as llm_client
        monkeypatch.setattr(llm_client, "call_deepseek_json", lambda p: {"groups": [[0, 1], [2]], "reason": "first two same topic"})
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "方案A", "state": {}},
            {"turn_index": 1, "role": "催收员", "text": "方案A续", "state": {}},
            {"turn_index": 2, "role": "催收员", "text": "方案B", "state": {}},
        ]
        group = {"collector_indices": [0, 1, 2], "interruption_indices": []}
        result = _llm_should_merge(turns, group)
        assert result == [[0, 1], [2]]

    def test_word_count_enforcement_splits_group(self, monkeypatch):
        import infra.llm_client as llm_client
        long_a = "字" * 80
        long_b = "字" * 80
        long_c = "字" * 90
        long_d = "字" * 30
        monkeypatch.setattr(llm_client, "call_deepseek_json", lambda p: {"groups": [[0, 1, 2, 3]], "reason": "all same"})
        turns = [
            {"turn_index": 0, "role": "催收员", "text": long_a, "state": {}},
            {"turn_index": 1, "role": "催收员", "text": long_b, "state": {}},
            {"turn_index": 2, "role": "催收员", "text": long_c, "state": {}},
            {"turn_index": 3, "role": "催收员", "text": long_d, "state": {}},
        ]
        group = {"collector_indices": [0, 1, 2, 3], "interruption_indices": []}
        result = _llm_should_merge(turns, group)
        assert result == [[0], [1], [2, 3]]

    def test_word_count_single_exceeds_limit_kept_alone(self, monkeypatch):
        import infra.llm_client as llm_client
        very_long = "字" * 160
        short = "字" * 30
        monkeypatch.setattr(llm_client, "call_deepseek_json", lambda p: {"groups": [[0, 1]], "reason": "same"})
        turns = [
            {"turn_index": 0, "role": "催收员", "text": very_long, "state": {}},
            {"turn_index": 1, "role": "催收员", "text": short, "state": {}},
        ]
        group = {"collector_indices": [0, 1], "interruption_indices": []}
        result = _llm_should_merge(turns, group)
        assert result == [[0], [1]]


class TestMergeTurns:
    def test_merge_two_consecutive(self):
        turns = [
            {"turn_index": 14, "role": "催收员", "text": "方案A", "state": {"action": "plan_proposal"}},
            {"turn_index": 15, "role": "催收员", "text": "方案A续", "state": {"action": "plan_proposal"}},
        ]
        entry = _merge_turns(turns, [0, 1], "call1")
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
        entry = _merge_turns(turns, [0, 2], "call1")
        assert entry["script_text"] == "方案A 方案A续"
        assert entry["merged_from"] == ["call1_t10", "call1_t12"]


class TestEnsureSameActionMerged:
    def test_merges_consecutive_same_action(self):
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "a", "state": {"action": "pressure"}},
            {"turn_index": 1, "role": "催收员", "text": "b", "state": {"action": "pressure"}},
            {"turn_index": 2, "role": "催收员", "text": "c", "state": {"action": "pressure"}},
        ]
        indices = [0, 1, 2]
        partition = [[0], [1], [2]]
        result = _ensure_same_action_merged(turns, indices, partition)
        assert result == [[0, 1, 2]]

    def test_keeps_different_actions(self):
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "a", "state": {"action": "plan_proposal"}},
            {"turn_index": 1, "role": "催收员", "text": "b", "state": {"action": "pressure"}},
            {"turn_index": 2, "role": "催收员", "text": "c", "state": {"action": "pressure"}},
        ]
        indices = [0, 1, 2]
        partition = [[0], [1], [2]]
        result = _ensure_same_action_merged(turns, indices, partition)
        assert result == [[0], [1, 2]]

    def test_llm_kept_same_action_separate_gets_merged(self, monkeypatch):
        import infra.llm_client as llm_client
        monkeypatch.setattr(llm_client, "call_deepseek_json", lambda p: {"groups": [[0], [1], [2]], "reason": "keep all"})
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "a", "state": {"action": "pressure"}},
            {"turn_index": 1, "role": "催收员", "text": "b", "state": {"action": "plan_proposal"}},
            {"turn_index": 2, "role": "催收员", "text": "c", "state": {"action": "pressure"}},
            {"turn_index": 3, "role": "催收员", "text": "d", "state": {"action": "pressure"}},
        ]
        group = {"collector_indices": [0, 1, 2, 3], "interruption_indices": []}
        result = _llm_should_merge(turns, group)
        assert [2, 3] in result


class TestApplyMerges:
    def test_merges_applied(self, monkeypatch):
        import infra.llm_client as llm_client
        monkeypatch.setattr(llm_client, "call_deepseek_json", lambda p: {"groups": [[0, 1]], "reason": "same"})
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
        import infra.llm_client as llm_client
        monkeypatch.setattr(llm_client, "call_deepseek_json", lambda p: {"groups": [[0], [1]], "reason": "different"})
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "方案A", "state": {"action": "plan_proposal"}},
            {"turn_index": 1, "role": "客户", "text": "嗯", "state": {}},
            {"turn_index": 2, "role": "催收员", "text": "方案B", "state": {"action": "pressure"}},
        ]
        merge_decisions = {}
        result = _apply_merges(turns, "call1", merge_decisions)
        collector_turns = [t for t in result if t["role"] == "催收员"]
        assert len(collector_turns) == 2

    def test_partial_merge(self, monkeypatch):
        import infra.llm_client as llm_client
        monkeypatch.setattr(llm_client, "call_deepseek_json", lambda p: {"groups": [[0, 1], [2]], "reason": "first two same"})
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "方案A", "state": {"action": "plan_proposal"}},
            {"turn_index": 1, "role": "催收员", "text": "方案A续", "state": {"action": "pressure"}},
            {"turn_index": 2, "role": "催收员", "text": "方案B", "state": {"action": "empathy"}},
            {"turn_index": 3, "role": "客户", "text": "好的", "state": {}},
        ]
        merge_decisions = {}
        result = _apply_merges(turns, "call1", merge_decisions)
        collector_turns = [t for t in result if t["role"] == "催收员"]
        assert len(collector_turns) == 2
        assert "_merged_entry" in collector_turns[0]
        assert "_merged_entry" not in collector_turns[1]

    def test_cache_used(self):
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "方案A", "state": {"action": "plan_proposal"}},
            {"turn_index": 1, "role": "催收员", "text": "方案A续", "state": {"action": "plan_proposal"}},
            {"turn_index": 2, "role": "客户", "text": "好的", "state": {}},
        ]
        merge_decisions = {("call1", (0, 1)): [[0, 1]]}
        result = _apply_merges(turns, "call1", merge_decisions)
        collector_turns = [t for t in result if t["role"] == "催收员"]
        assert len(collector_turns) == 1

    def test_cache_keep(self):
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "方案A", "state": {"action": "plan_proposal"}},
            {"turn_index": 1, "role": "催收员", "text": "方案A续", "state": {"action": "plan_proposal"}},
            {"turn_index": 2, "role": "客户", "text": "好的", "state": {}},
        ]
        merge_decisions = {("call1", (0, 1)): [[0], [1]]}
        result = _apply_merges(turns, "call1", merge_decisions)
        collector_turns = [t for t in result if t["role"] == "催收员"]
        assert len(collector_turns) == 2

    def test_interruption_removed_only_for_merged_group(self, monkeypatch):
        import infra.llm_client as llm_client
        monkeypatch.setattr(llm_client, "call_deepseek_json", lambda p: {"groups": [[0, 1], [2]], "reason": "partial"})
        turns = [
            {"turn_index": 0, "role": "催收员", "text": "方案A", "state": {"action": "plan_proposal"}},
            {"turn_index": 1, "role": "客户", "text": "嗯", "state": {}},
            {"turn_index": 2, "role": "催收员", "text": "方案A续", "state": {"action": "pressure"}},
            {"turn_index": 3, "role": "客户", "text": "好", "state": {}},
            {"turn_index": 4, "role": "催收员", "text": "方案B", "state": {"action": "empathy"}},
        ]
        merge_decisions = {}
        result = _apply_merges(turns, "call1", merge_decisions)
        customer_turns = [t for t in result if t["role"] == "客户"]
        assert len(customer_turns) == 1
        assert customer_turns[0]["text"] == "好"
