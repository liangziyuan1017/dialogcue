import json
import os

import pytest

from f005_context_scoring.score_tree import (
    BITMASK_FIELDS,
    BG_BACKGROUND_FIELDS,
    build_conversation_context_lookup,
    build_context_lookup,
    build_customer_info_lookup,
    build_reward_lookup,
    build_turns_lookup,
    score_tree,
    _extract_conversation_context,
    _score_sentence_pool,
)


@pytest.fixture
def context_lookup():
    return build_context_lookup()


@pytest.fixture
def reward_lookup():
    return build_reward_lookup()


@pytest.fixture
def customer_info_lookup():
    return build_customer_info_lookup()


class TestScoreSentencePool:
    def test_augments_all_fields(self, context_lookup, reward_lookup, customer_info_lookup):
        pool = [
            {"script_text": "hello", "script_id": "t1", "source_call_ids": ["2317941550352385028"]},
        ]
        _score_sentence_pool(pool, context_lookup, reward_lookup, customer_info_lookup)
        s = pool[0]
        for field in ["bg_constraints", "bg_bitmask", "bg_bitmask_int", "bg_background", "win_rate", "sas", "uplift_score", "csi", "deferred"]:
            assert field in s, f"missing {field}"

    def test_bg_bitmask_is_dict(self, context_lookup, reward_lookup, customer_info_lookup):
        pool = [
            {"script_text": "hello", "script_id": "t1", "source_call_ids": ["2317941550352385028"]},
        ]
        _score_sentence_pool(pool, context_lookup, reward_lookup, customer_info_lookup)
        s = pool[0]
        assert isinstance(s["bg_bitmask"], dict)
        assert all(f in s["bg_bitmask"] for f in BITMASK_FIELDS)
        assert all(v in (0, 1) for v in s["bg_bitmask"].values())

    def test_bg_bitmask_int_is_integer(self, context_lookup, reward_lookup, customer_info_lookup):
        pool = [
            {"script_text": "hello", "script_id": "t1", "source_call_ids": ["2317941550352385028"]},
        ]
        _score_sentence_pool(pool, context_lookup, reward_lookup, customer_info_lookup)
        s = pool[0]
        max_mask = (1 << len(BITMASK_FIELDS)) - 1
        assert isinstance(s["bg_bitmask_int"], int)
        assert 0 <= s["bg_bitmask_int"] <= max_mask

    def test_bg_background_has_fields(self, context_lookup, reward_lookup, customer_info_lookup):
        pool = [
            {"script_text": "hello", "script_id": "t1", "source_call_ids": ["2317941550352385028"]},
        ]
        _score_sentence_pool(pool, context_lookup, reward_lookup, customer_info_lookup)
        s = pool[0]
        assert isinstance(s["bg_background"], dict)
        for eng, _ in BG_BACKGROUND_FIELDS:
            assert eng in s["bg_background"]

    def test_deferred_fields(self, context_lookup, reward_lookup, customer_info_lookup):
        pool = [
            {"script_text": "hello", "script_id": "t1", "source_call_ids": ["2317941550352385028"]},
        ]
        _score_sentence_pool(pool, context_lookup, reward_lookup, customer_info_lookup)
        s = pool[0]
        assert s["uplift_score"] == 0
        assert s["csi"] == 0
        assert s["deferred"] is True

    def test_win_rate_in_range(self, context_lookup, reward_lookup, customer_info_lookup):
        pool = [
            {"script_text": "hello", "script_id": "t1", "source_call_ids": ["2317941550352385028"]},
        ]
        _score_sentence_pool(pool, context_lookup, reward_lookup, customer_info_lookup)
        assert 0 <= pool[0]["win_rate"] <= 1

    def test_sas_computed(self, context_lookup, reward_lookup, customer_info_lookup):
        pool = [
            {"script_text": "您可以尽快还款吗", "script_id": "t1", "source_call_ids": ["2317941550352385028"]},
            {"script_text": "我们建议您办理分期", "script_id": "t2", "source_call_ids": ["2317941550352385028"]},
        ]
        _score_sentence_pool(pool, context_lookup, reward_lookup, customer_info_lookup)
        assert 0 <= pool[0]["sas"] <= 1
        assert 0 <= pool[1]["sas"] <= 1


class TestScoreTree:
    def test_preserves_structure(self, context_lookup, reward_lookup, customer_info_lookup):
        with open(os.path.join(os.path.dirname(__file__), "../..", "f004_decision_tree", "decision_tree.json"), encoding="utf-8") as f:
            tree = json.load(f)
        import copy
        original = copy.deepcopy(tree)
        scored = score_tree(tree, context_lookup, reward_lookup, customer_info_lookup)
        assert scored["state_id"] == original["state_id"]
        assert len(scored.get("children", [])) == len(original.get("children", []))

    def test_all_sentences_scored(self, context_lookup, reward_lookup, customer_info_lookup):
        with open(os.path.join(os.path.dirname(__file__), "../..", "f004_decision_tree", "decision_tree.json"), encoding="utf-8") as f:
            tree = json.load(f)
        scored = score_tree(tree, context_lookup, reward_lookup, customer_info_lookup)
        missing = []
        def check(node):
            for s in node.get("sentence_pool", []):
                for field in ["bg_constraints", "bg_bitmask", "bg_bitmask_int", "bg_background", "win_rate", "sas", "uplift_score", "csi", "deferred"]:
                    if field not in s:
                        missing.append((s.get("script_id"), field))
            for child in node.get("children", []):
                check(child)
        check(scored)
        assert missing == []

    def test_all_sentences_have_conversation_context(self, context_lookup, reward_lookup, customer_info_lookup):
        with open(os.path.join(os.path.dirname(__file__), "../..", "f004_decision_tree", "decision_tree.json"), encoding="utf-8") as f:
            tree = json.load(f)
        turns_lookup = build_turns_lookup()
        conv_ctx_lookup = build_conversation_context_lookup(tree, turns_lookup)
        scored = score_tree(tree, context_lookup, reward_lookup, customer_info_lookup, conv_ctx_lookup)
        missing = []
        def check(node):
            for s in node.get("sentence_pool", []):
                if "conversation_context" not in s:
                    missing.append(s.get("script_id"))
            for child in node.get("children", []):
                check(child)
        check(scored)
        assert missing == []


class TestConversationContext:
    def test_extract_with_matching_turn(self):
        turns = [
            {"text": "你好"},
            {"text": "请问您是张先生吗"},
            {"text": "您有一笔欠款需要处理"},
        ]
        ctx = _extract_conversation_context("您有一笔欠款需要处理", turns)
        assert "请问您是张先生吗" in ctx

    def test_extract_empty_turns(self):
        assert _extract_conversation_context("hello", []) == ""

    def test_extract_no_match_uses_all_previous(self):
        turns = [
            {"text": "第一句"},
            {"text": "第二句"},
            {"text": "第三句"},
        ]
        ctx = _extract_conversation_context("不存在", turns)
        assert "第一句" in ctx
        assert "第二句" in ctx

    def test_build_conversation_context_lookup(self):
        with open(os.path.join(os.path.dirname(__file__), "../..", "f004_decision_tree", "decision_tree.json"), encoding="utf-8") as f:
            tree = json.load(f)
        turns_lookup = build_turns_lookup()
        ctx_lookup = build_conversation_context_lookup(tree, turns_lookup)
        assert len(ctx_lookup) > 0
