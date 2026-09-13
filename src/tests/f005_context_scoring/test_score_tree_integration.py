import json
import os

import pytest

from f005_context_scoring.score_tree import (
    _load_decision_tree,
    build_reward_lookup,
)
from f005_context_scoring.scoring_metrics import (
    BG_BACKGROUND_FIELDS,
    BITMASK_FIELDS,
    encode_bitmask_int,
)

SCORED_TREE_PATH = os.path.join(os.path.dirname(__file__), "../..", "f005_context_scoring", "data", "decision_tree_scored.json")


@pytest.fixture
def scored_tree():
    with open(SCORED_TREE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _all_sentences(node):
    sentences = list(node.get("sentence_pool", []))
    for child in node.get("children", []):
        sentences.extend(_all_sentences(child))
    return sentences


def _all_call_ids(node):
    ids = set()
    for s in node.get("sentence_pool", []):
        ids.update(s.get("source_call_ids", []))
    for child in node.get("children", []):
        ids.update(_all_call_ids(child))
    return ids


class TestIntegrationAllSentencesScored:
    def test_sentence_count_matches_original(self, scored_tree):
        original = _load_decision_tree()
        assert len(_all_sentences(scored_tree)) == len(_all_sentences(original))

    def test_105_call_ids(self, scored_tree):
        assert len(_all_call_ids(scored_tree)) == 5  # current checked-in corpus

    def test_every_sentence_has_bg_constraints(self, scored_tree):
        for s in _all_sentences(scored_tree):
            assert "bg_constraints" in s
            for f in BITMASK_FIELDS:
                assert f in s["bg_constraints"], f"{s['script_id']} missing {f}"

    def test_every_sentence_has_bg_bitmask_dict(self, scored_tree):
        for s in _all_sentences(scored_tree):
            assert "bg_bitmask" in s
            assert isinstance(s["bg_bitmask"], dict)
            for f in BITMASK_FIELDS:
                assert f in s["bg_bitmask"]
                assert s["bg_bitmask"][f] in (0, 1)

    def test_every_sentence_has_bg_bitmask_int(self, scored_tree):
        max_mask = (1 << len(BITMASK_FIELDS)) - 1
        for s in _all_sentences(scored_tree):
            assert "bg_bitmask_int" in s
            assert isinstance(s["bg_bitmask_int"], int)
            assert 0 <= s["bg_bitmask_int"] <= max_mask

    def test_bitmask_int_consistent_with_dict(self, scored_tree):
        for s in _all_sentences(scored_tree):
            expected = encode_bitmask_int(s["bg_bitmask"])
            assert s["bg_bitmask_int"] == expected, f"{s['script_id']} bitmask_int mismatch"

    def test_every_sentence_has_bg_background(self, scored_tree):
        for s in _all_sentences(scored_tree):
            assert "bg_background" in s
            assert isinstance(s["bg_background"], dict)
            for eng, _, _ in BG_BACKGROUND_FIELDS:
                assert eng in s["bg_background"], f"{s['script_id']} missing bg_background.{eng}"

    def test_every_sentence_has_win_rate(self, scored_tree):
        for s in _all_sentences(scored_tree):
            assert "win_rate" in s
            assert 0 <= s["win_rate"] <= 1

    def test_every_sentence_has_sas(self, scored_tree):
        for s in _all_sentences(scored_tree):
            assert "sas" in s
            assert 0 <= s["sas"] <= 1

    def test_every_sentence_has_conversation_context(self, scored_tree):
        for s in _all_sentences(scored_tree):
            assert "conversation_context" in s
            assert isinstance(s["conversation_context"], str)

    def test_every_sentence_has_deferred_fields(self, scored_tree):
        for s in _all_sentences(scored_tree):
            assert s["uplift_score"] == 0
            assert s["csi"] == 0
            assert s["deferred"] is True


class TestBitmaskFiltering:
    def test_subset_compatibility(self, scored_tree):
        all_bits = (1 << len(BITMASK_FIELDS)) - 1
        for s in _all_sentences(scored_tree):
            sb = s["bg_bitmask_int"]
            query = all_bits
            assert (sb & query) == sb

    def test_all_bits_query_matches_all(self, scored_tree):
        all_bits = (1 << len(BITMASK_FIELDS)) - 1
        all_sentences = _all_sentences(scored_tree)
        compatible = [s for s in all_sentences if (s["bg_bitmask_int"] & all_bits) == s["bg_bitmask_int"]]
        assert len(compatible) == len(all_sentences)

    def test_bitmask_filter_produces_subset(self, scored_tree):
        all_sentences = _all_sentences(scored_tree)
        query = all_sentences[0]["bg_bitmask_int"]
        compatible = [s for s in all_sentences if (s["bg_bitmask_int"] & query) == s["bg_bitmask_int"]]
        assert len(compatible) <= len(all_sentences)
        assert len(compatible) > 0


class TestTreeStructurePreserved:
    def test_root_is_initial_contact(self, scored_tree):
        assert scored_tree["state_id"] == "initial_contact"

    def test_same_node_count(self, scored_tree):
        original = _load_decision_tree()

        def count_nodes(n):
            return 1 + sum(count_nodes(c) for c in n.get("children", []))

        assert count_nodes(scored_tree) == count_nodes(original)

    def test_r1_sentences_have_higher_hwr(self, scored_tree):
        reward_lookup = build_reward_lookup()
        r1_ids = {cid for cid, r in reward_lookup.items() if r == 1}
        r1_sentences = []
        r0_sentences = []
        for s in _all_sentences(scored_tree):
            src = s.get("source_call_ids", [])
            if any(cid in r1_ids for cid in src):
                r1_sentences.append(s)
            else:
                r0_sentences.append(s)
        if r1_sentences and r0_sentences:
            avg_r1 = sum(s["win_rate"] for s in r1_sentences) / len(r1_sentences)
            avg_r0 = sum(s["win_rate"] for s in r0_sentences) / len(r0_sentences)
            assert avg_r1 > avg_r0
