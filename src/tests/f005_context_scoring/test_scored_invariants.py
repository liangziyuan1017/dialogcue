import json
import os

import pytest


SCORED_TREE_PATH = os.path.join(
    os.path.dirname(__file__), "../..", "f005_context_scoring", "data", "decision_tree_scored.json"
)


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


@pytest.fixture(scope="module")
def scored_tree():
    if not os.path.exists(SCORED_TREE_PATH):
        pytest.skip("decision_tree_scored.json not yet generated")
    with open(SCORED_TREE_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def all_sentences(scored_tree):
    return list(_all_sentences(scored_tree))


EXPECTED_BITMASK_FIELDS = {
    "has_auto_loan",
    "has_mortgage",
    "has_negotiation_history",
    "social_insurance_stable",
    "credit_rating_good",
    "card_restricted",
    "is_cash_out_customer",
    "has_complaint_history",
    "has_legal_tools",
    "is_negotiation_brain_customer",
}


class TestF005Bitmask:
    def test_bg_constraints_has_exactly_5_keys(self, all_sentences):
        for s in all_sentences:
            bg = s.get("bg_constraints", {})
            assert set(bg.keys()) == EXPECTED_BITMASK_FIELDS, (
                f"Sentence {s.get('script_id')} bg_constraints keys: {set(bg.keys())}"
            )

    def test_bg_bitmask_has_5_fields(self, all_sentences):
        for s in all_sentences:
            bm = s.get("bg_bitmask", {})
            assert set(bm.keys()) == EXPECTED_BITMASK_FIELDS, (
                f"Sentence {s.get('script_id')} bg_bitmask keys: {set(bm.keys())}"
            )

    def test_bg_bitmask_int_in_0_1023(self, all_sentences):
        for s in all_sentences:
            val = s.get("bg_bitmask_int", -1)
            assert 0 <= val <= 1023, (
                f"Sentence {s.get('script_id')} bg_bitmask_int={val}, expected 0-1023"
            )


class TestF005WinRate:
    def test_win_rate_in_0_1(self, all_sentences):
        for s in all_sentences:
            wr = s.get("win_rate", -1)
            assert 0 <= wr <= 1, f"Sentence {s.get('script_id')} win_rate={wr}"

    def test_win_rate_node_exists(self, all_sentences):
        for s in all_sentences:
            assert "win_rate_node" in s, f"Sentence {s.get('script_id')} missing win_rate_node"

    def test_win_rate_node_in_0_1(self, all_sentences):
        for s in all_sentences:
            wrn = s.get("win_rate_node", -1)
            assert 0 <= wrn <= 1, f"Sentence {s.get('script_id')} win_rate_node={wrn}"

    def test_sas_in_0_1(self, all_sentences):
        for s in all_sentences:
            sas = s.get("sas", -1)
            assert 0 <= sas <= 1, f"Sentence {s.get('script_id')} sas={sas}"


class TestF005Embedding:
    def test_embedding_absent_from_json(self, all_sentences):
        for s in all_sentences:
            assert "embedding" not in s, (
                f"Sentence {s.get('script_id')} has embedding field (should be DB-only)"
            )

    def test_conversation_context_present(self, all_sentences):
        for s in all_sentences:
            assert "conversation_context" in s, (
                f"Sentence {s.get('script_id')} missing conversation_context"
            )


class TestF005DefaultScores:
    def test_uplift_score_zero(self, all_sentences):
        for s in all_sentences:
            assert s.get("uplift_score") == 0, (
                f"Sentence {s.get('script_id')} uplift_score={s.get('uplift_score')}"
            )

    def test_csi_zero(self, all_sentences):
        for s in all_sentences:
            assert s.get("csi") == 0, f"Sentence {s.get('script_id')} csi={s.get('csi')}"

    def test_deferred_true(self, all_sentences):
        for s in all_sentences:
            assert s.get("deferred") is True, (
                f"Sentence {s.get('script_id')} deferred={s.get('deferred')}"
            )
