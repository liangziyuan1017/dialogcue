
from f004_decision_tree.build_decision_tree import (
    _apply_merges,
    _ensure_same_action_merged,
    _llm_should_merge,
    _merge_turns,
)


class TestLLMShouldMerge:
    def test_merge_response(self, monkeypatch):
        import f007_infrastructure.llm_client as llm_client
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
        import f007_infrastructure.llm_client as llm_client
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
        import f007_infrastructure.llm_client as llm_client
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
        import f007_infrastructure.llm_client as llm_client
        long_a = "字" * 40
        long_b = "字" * 40
        long_c = "字" * 30
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
        assert result == [[0, 1], [2, 3]]

    def test_word_count_single_exceeds_limit_kept_alone(self, monkeypatch):
        import f007_infrastructure.llm_client as llm_client
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
        import f007_infrastructure.llm_client as llm_client
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
        import f007_infrastructure.llm_client as llm_client
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
        import f007_infrastructure.llm_client as llm_client
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
        import f007_infrastructure.llm_client as llm_client
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
        import f007_infrastructure.llm_client as llm_client
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
