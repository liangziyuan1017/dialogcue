import importlib.util
import os

from f004_decision_tree.build_decision_tree import (
    MAX_MERGED_WORDS,
    _apply_merges,
    _build_merge_prompt,
    _find_merge_candidates,
    _is_ack_interruption,
    _word_count,
)


def _load_record(index):
    data_path = os.path.join(os.path.dirname(__file__), "../..", "f003_reward_labeling", "data", "output_rewarded.py")
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
        import f007_infrastructure.llm_client as llm_client
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

    def test_dialog2_merge_group_exists(self):
        r = _load_record(2)
        groups = _find_merge_candidates(r["turns_annotated"])
        assert len(groups) >= 1

    def test_dialog2_t0_t2_t4_merged(self):
        r = _load_record(2)
        groups = _find_merge_candidates(r["turns_annotated"])
        has_0_2_4 = any(0 in g["collector_indices"] and 2 in g["collector_indices"] and 4 in g["collector_indices"] for g in groups)
        assert has_0_2_4

    def test_dialog2_facts_break_chain(self):
        r = _load_record(2)
        turns = r["turns_annotated"]
        groups = _find_merge_candidates(turns)
        merged_indices = set()
        for g in groups:
            merged_indices.update(g["collector_indices"])
        t15 = turns[15]
        if t15["role"] == "客户" and t15.get("state", {}).get("facts"):
            assert 15 not in merged_indices

    def test_dialog2_no_merge_beyond_data(self):
        r = _load_record(2)
        turns = r["turns_annotated"]
        groups = _find_merge_candidates(turns)
        max_idx = len(turns) - 1
        for g in groups:
            for idx in g["collector_indices"]:
                assert idx <= max_idx


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
