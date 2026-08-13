import json
import os
import tempfile
from pathlib import Path

import pytest

from f004_decision_tree.build_decision_tree import (
    add_dialog_to_tree,
    build_registry_from_tree,
    build_tree,
    make_base_tree,
    merge_dialogs,
    write_decision_tree,
)
from f007_infrastructure.jsonl_utils import load_jsonl


def _load_rewarded():
    data_path = os.path.join(os.path.dirname(__file__), "../..", "f003_reward_labeling", "data", "output_rewarded.jsonl")
    return load_jsonl(Path(data_path))


def _sample_record(call_id="test-001", reward=0):
    return {
        "call_id": call_id,
        "reward": reward,
        "turns_annotated": [
            {"turn_index": 0, "role": "催收员", "text": "您好，请问是张女士吗？", "state": {"action": "greeting"}},
            {"turn_index": 1, "role": "客户", "text": "对。"},
            {"turn_index": 2, "role": "催收员", "text": "女士，我帮您申请减免。", "state": {"action": "plan_proposal"}},
            {"turn_index": 3, "role": "客户", "text": "好的，我同意。", "state": {"willingness": "cooperative"}},
            {"turn_index": 4, "role": "催收员", "text": "好的，请尽快还款。", "state": {"action": "closure"}},
        ],
    }


def _sample_record_with_facts(call_id="test-002"):
    return {
        "call_id": call_id,
        "reward": 0,
        "turns_annotated": [
            {"turn_index": 0, "role": "催收员", "text": "您好。", "state": {"action": "greeting"}},
            {"turn_index": 1, "role": "客户", "text": "我没钱。", "state": {"facts": ["financial_hardship"], "emotions": ["distress"], "willingness": "resistant"}},
            {"turn_index": 2, "role": "催收员", "text": "我理解您的困难。", "state": {"action": "empathy"}},
            {"turn_index": 3, "role": "客户", "text": "嗯。", "state": {"facts": ["financial_hardship"], "willingness": "weak"}},
            {"turn_index": 4, "role": "催收员", "text": "建议您还最低还款。", "state": {"action": "plan_proposal"}},
        ],
    }


def _all_sentences(node, visited=None):
    if visited is None:
        visited = set()
    nid = id(node)
    if nid in visited:
        return
    visited.add(nid)
    for s in node.get("sentence_pool", []):
        yield s
    for child in node.get("children", []):
        yield from _all_sentences(child, visited)


class TestMakeBaseTree:
    def test_root_is_opening(self):
        tree = make_base_tree()
        assert tree["state_id"] == "initial_contact"
        assert tree["role"] == "opening"

    def test_has_normal_and_abrupt_end(self):
        tree = make_base_tree()
        child_ids = [c.get("state_id") for c in tree["children"]]
        assert "normal_end" in child_ids
        assert "abrupt_end" in child_ids

    def test_end_nodes_have_ending_role(self):
        tree = make_base_tree()
        for child in tree["children"]:
            assert child.get("role") == "ending"


class TestBuildRegistryFromTree:
    def test_populates_registry(self):
        tree = build_tree([_sample_record_with_facts()])
        registry = build_registry_from_tree(tree)
        assert len(registry) > 0

    def test_registry_entries_are_nodes(self):
        tree = build_tree([_sample_record_with_facts()])
        registry = build_registry_from_tree(tree)
        for identity, node in registry.items():
            assert "state_id" in node
            assert "branch_key" in node


class TestAddDialogToTree:
    def test_adds_greeting_to_root(self):
        tree = make_base_tree()
        registry = {}
        add_dialog_to_tree(tree, _sample_record(), registry)
        greeting_children = [c for c in tree["children"] if c.get("state_id") == "a:greeting"]
        assert len(greeting_children) == 0
        opening = [s for s in tree["sentence_pool"] if s.get("gesture_type") == "opening"]
        assert len(opening) > 0

    def test_adds_facts_branch(self):
        tree = make_base_tree()
        registry = {}
        add_dialog_to_tree(tree, _sample_record_with_facts(), registry)
        fact_children = [c for c in tree["children"] if c.get("state_id") == "f:financial_hardship"]
        assert len(fact_children) >= 1

    def test_idempotent_double_insert(self):
        tree = make_base_tree()
        registry = {}
        rec = _sample_record("call-idem")
        add_dialog_to_tree(tree, rec, registry)
        pool_before = len(list(_all_sentences(tree)))
        add_dialog_to_tree(tree, rec, registry)
        pool_after = len(list(_all_sentences(tree)))
        assert pool_after == pool_before, "Double insert should not duplicate sentences"


class TestMergeDialogs:
    def test_creates_tree_from_scratch(self):
        records = [_sample_record(), _sample_record_with_facts()]
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            merge_dialogs(path, records)
            with open(path, encoding="utf-8") as f:
                tree = json.load(f)
            assert tree["state_id"] == "initial_contact"
        finally:
            os.unlink(path)

    def test_incremental_merge(self):
        records = [_sample_record("call-A"), _sample_record_with_facts("call-B")]
        half = len(records) // 2
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            merge_dialogs(path, records[:half])
            merge_dialogs(path, records[half:])
            with open(path, encoding="utf-8") as f:
                tree = json.load(f)
            all_cids = set()
            for node in _iter_nodes(tree):
                for s in node.get("sentence_pool", []):
                    all_cids.update(s.get("source_call_ids", []))
            assert "call-A" in all_cids or "call-B" in all_cids
        finally:
            os.unlink(path)


class TestAdditiveVsOldEquivalence:
    def test_same_call_id_coverage(self):
        records = _load_rewarded()
        tree_additive = build_tree(records)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            write_decision_tree(records, path)
            with open(path, encoding="utf-8") as f:
                tree_written = json.load(f)
        finally:
            os.unlink(path)
        additive_cids = set()
        for s in _all_sentences(tree_additive):
            additive_cids.update(s.get("source_call_ids", []))
        written_cids = set()
        for s in _all_sentences(tree_written):
            written_cids.update(s.get("source_call_ids", []))
        assert additive_cids == written_cids, (
            f"Additive missing: {written_cids - additive_cids}, "
            f"Extra: {additive_cids - written_cids}"
        )


def _iter_nodes(node, visited=None):
    if visited is None:
        visited = set()
    nid = id(node)
    if nid in visited:
        return
    visited.add(nid)
    yield node
    for child in node.get("children", []):
        yield from _iter_nodes(child, visited)
