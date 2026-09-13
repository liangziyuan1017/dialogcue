import pytest

from f005_context_scoring.score_tree import (
    _score_sentence_pool,
    build_context_lookup,
    build_reward_lookup,
)
from f005_context_scoring.scoring_metrics import (
    BG_BACKGROUND_FIELDS,
    BITMASK_FIELDS,
    _extract_bg_background,
    _extract_bg_constraints,
    compute_bg_background,
    compute_bg_constraints,
    compute_hwr,
    compute_sas_for_pool,
    cosine_similarity,
    encode_bitmask,
    encode_bitmask_int,
)


@pytest.fixture
def context_lookup():
    return build_context_lookup()


@pytest.fixture
def reward_lookup():
    return build_reward_lookup()


class TestContextLookup:
    def test_returns_105_records(self, context_lookup):
        assert len(context_lookup) == 5  # current checked-in corpus

    def test_all_have_context_fields(self, context_lookup):
        for _cid, ctx in context_lookup.items():
            assert "has_business_loan" in ctx
            assert "has_mortgage" in ctx
            assert "has_other_loan" in ctx
            assert "recent_repayment" in ctx
            assert "is_high_risk_proxy_complaint" in ctx
            assert "is_proxy_intermediary_complaint" in ctx
            assert "has_social_insurance" in ctx
            assert "risk_level" in ctx
            assert "complaint_score" in ctx
            assert "vehicle_count" in ctx
            assert "business_loan_balance" in ctx
            assert "mortgage_balance" in ctx
            assert "other_loan_balance" in ctx
            assert "wealth_value" in ctx
            assert "current_balance" in ctx
            assert "education" in ctx
            assert "days_delinquent" in ctx
            assert "recent_contact_count" in ctx

    def test_known_call_id_present(self, context_lookup):
        assert "2346089320444241687" in context_lookup


class TestRewardLookup:
    def test_returns_105_records(self, reward_lookup):

        assert len(reward_lookup) == 5  # current checked-in corpus
    def test_all_rewards_are_0_or_1(self, reward_lookup):
        for _cid, r in reward_lookup.items():
            assert r in (0, 1)
    def test_78_rewards_are_1(self, reward_lookup):

        assert sum(1 for r in reward_lookup.values() if r == 1) == 3  # current checked-in corpus


class TestBitmaskEncoding:
    def test_all_false_is_zero_dict(self):
        bg = {f: False for f in BITMASK_FIELDS}
        result = encode_bitmask(bg)
        assert isinstance(result, dict)
        assert all(v == 0 for v in result.values())

    def test_all_true_is_all_ones_dict(self):
        bg = {f: True for f in BITMASK_FIELDS}
        result = encode_bitmask(bg)
        assert all(v == 1 for v in result.values())

    def test_single_bit_0(self):
        bg = {f: False for f in BITMASK_FIELDS}
        bg["has_business_loan"] = True
        result = encode_bitmask(bg)
        assert result["has_business_loan"] == 1
        assert result["has_mortgage"] == 0

    def test_bitmask_int_from_dict(self):
        bg_bitmask = {f: 0 for f in BITMASK_FIELDS}
        bg_bitmask["has_business_loan"] = 1
        assert encode_bitmask_int(bg_bitmask) == 1

    def test_bitmask_int_all_ones(self):
        bg_bitmask = {f: 1 for f in BITMASK_FIELDS}
        assert encode_bitmask_int(bg_bitmask) == (1 << len(BITMASK_FIELDS)) - 1

    def test_bitmask_int_all_zeros(self):
        bg_bitmask = {f: 0 for f in BITMASK_FIELDS}
        assert encode_bitmask_int(bg_bitmask) == 0

    def test_extract_bg_constraints_from_context(self):
        ctx = {
            "has_business_loan": True,
            "has_mortgage": False,
            "has_other_loan": True,
            "recent_repayment": True,
            "is_high_risk_proxy_complaint": False,
            "is_proxy_intermediary_complaint": True,
            "has_social_insurance": False,
            "risk_level": 2,
            "complaint_score": 10,
            "vehicle_count": 1,
        }
        bg = _extract_bg_constraints(ctx)
        assert bg["has_business_loan"] is True
        assert bg["has_mortgage"] is False
        assert bg["has_other_loan"] is True
        assert bg["recent_repayment"] is True
        assert bg["is_high_risk_proxy_complaint"] is False
        assert bg["is_proxy_intermediary_complaint"] is True
        assert bg["has_social_insurance"] is False
        assert bg["has_risk_flag"] is True
        assert bg["has_complaint"] is True
        assert bg["has_vehicle"] is True

    def test_derived_flags_zero(self):
        ctx = {"risk_level": 0, "complaint_score": 0, "vehicle_count": 0}
        bg = _extract_bg_constraints(ctx)
        assert bg["has_risk_flag"] is False
        assert bg["has_complaint"] is False
        assert bg["has_vehicle"] is False

    def test_compute_bg_constraints_single_source(self, context_lookup):
        cid = "2346089320444241687"
        bg = compute_bg_constraints([cid], context_lookup)
        assert all(f in bg for f in BITMASK_FIELDS)

    def test_compute_bg_constraints_empty(self):
        bg = compute_bg_constraints([], {})
        assert all(bg[f] is False for f in BITMASK_FIELDS)

    def test_compute_bg_constraints_intersection(self):
        lookup = {
            "a": {"has_business_loan": True, "has_mortgage": True, "has_other_loan": False,
                  "recent_repayment": False, "is_high_risk_proxy_complaint": False,
                  "is_proxy_intermediary_complaint": False, "has_social_insurance": False,
                  "risk_level": 1, "complaint_score": 0, "vehicle_count": 0},
            "b": {"has_business_loan": True, "has_mortgage": False, "has_other_loan": False,
                  "recent_repayment": False, "is_high_risk_proxy_complaint": False,
                  "is_proxy_intermediary_complaint": False, "has_social_insurance": False,
                  "risk_level": 0, "complaint_score": 0, "vehicle_count": 0},
        }
        bg = compute_bg_constraints(["a", "b"], lookup)
        assert bg["has_business_loan"] is True
        assert bg["has_mortgage"] is False
        assert bg["has_risk_flag"] is False

    def test_bitmask_int_range(self, context_lookup):
        max_mask = (1 << len(BITMASK_FIELDS)) - 1
        for _cid, ctx in context_lookup.items():
            bg = _extract_bg_constraints(ctx)
            mask = encode_bitmask(bg)
            assert 0 <= encode_bitmask_int(mask) <= max_mask


class TestBgBackground:
    def test_extract_from_context(self, context_lookup):
        ctx = context_lookup["2346089320444241687"]
        bg = _extract_bg_background(ctx)
        assert "business_loan_digits" in bg
        assert "mortgage_balance_digits" in bg
        assert "other_loan_digits" in bg
        assert "wealth_digits" in bg
        assert "current_balance_digits" in bg
        assert "education" in bg
        assert "days_delinquent" in bg
        assert "recent_contact_count" in bg
        assert "risk_level" in bg
        assert "complaint_score" in bg

    def test_digit_count_transform(self):
        ctx = {"other_loan_balance": 142870, "current_balance": 3280796,
               "business_loan_balance": 0, "mortgage_balance": 0, "wealth_value": 0}
        bg = _extract_bg_background(ctx)
        assert bg["other_loan_digits"] == 6
        assert bg["current_balance_digits"] == 7
        assert bg["business_loan_digits"] == 0
        assert bg["mortgage_balance_digits"] == 0
        assert bg["wealth_digits"] == 0

    def test_compute_single_source(self, context_lookup):
        bg = compute_bg_background(["2346089320444241687"], context_lookup)
        assert isinstance(bg["other_loan_digits"], int)
        assert isinstance(bg["education"], str)

    def test_compute_empty(self):
        bg = compute_bg_background([], {})
        for field, _, transform in BG_BACKGROUND_FIELDS:
            assert field in bg
            if transform == "passthrough":
                assert bg[field] == ""
            else:
                assert bg[field] == 0

    def test_all_fields_present(self, context_lookup):
        bg = compute_bg_background(["2346089320444241687"], context_lookup)
        assert len(bg) == len(BG_BACKGROUND_FIELDS)


class TestHWR:
    def test_single_r1(self):
        assert compute_hwr(["a"], {"a": 1}) == pytest.approx(2 / 3, abs=1e-9)

    def test_single_r0(self):
        assert compute_hwr(["a"], {"a": 0}) == pytest.approx(1 / 3, abs=1e-9)

    def test_empty_is_half(self):
        assert compute_hwr([], {}) == 0.5

    def test_all_r1(self):
        rl = {"a": 1, "b": 1, "c": 1}
        assert compute_hwr(["a", "b", "c"], rl) == pytest.approx(4 / 5, abs=1e-9)

    def test_all_r0(self):
        rl = {"a": 0, "b": 0}
        assert compute_hwr(["a", "b"], rl) == pytest.approx(1 / 4, abs=1e-9)

    def test_mixed(self):
        rl = {"a": 1, "b": 0, "c": 1}
        assert compute_hwr(["a", "b", "c"], rl) == pytest.approx(3 / 5, abs=1e-9)

    def test_unknown_call_id_treated_as_r0(self):
        assert compute_hwr(["unknown"], {}) == pytest.approx(1 / 3, abs=1e-9)


class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0, abs=1e-9)

    def test_orthogonal_vectors(self):
        assert cosine_similarity([1, 0, 0], [0, 1, 0]) == pytest.approx(0.0, abs=1e-9)

    def test_known_value(self):
        a = [1, 1, 0]
        b = [1, 0, 0]
        expected = 1 / (2**0.5)
        assert cosine_similarity(a, b) == pytest.approx(expected, abs=1e-9)

    def test_zero_vector(self):
        assert cosine_similarity([0, 0, 0], [1, 0, 0]) == 0.0


class TestSAS:
    def test_single_sentence_is_one(self):
        sentences = [{"script_text": "hello", "script_id": "t1", "win_rate": 0.5}]
        assert compute_sas_for_pool(sentences) == [1.0]

    def test_identical_texts(self):
        sentences = [
            {"script_text": "你好", "script_id": "t1", "win_rate": 0.7},
            {"script_text": "你好", "script_id": "t2", "win_rate": 0.3},
        ]
        scores = compute_sas_for_pool(sentences)
        assert scores[0] == pytest.approx(1.0, abs=1e-6)
        assert scores[1] == pytest.approx(1.0, abs=1e-6)

    def test_sas_in_range(self):
        sentences = [
            {"script_text": "您可以尽快还款吗", "script_id": "t1", "win_rate": 0.7},
            {"script_text": "我们建议您办理分期", "script_id": "t2", "win_rate": 0.3},
        ]
        scores = compute_sas_for_pool(sentences)
        for s in scores:
            assert 0 <= s <= 1

    def test_reference_is_highest_hwr(self):
        sentences = [
            {"script_text": "低胜率句子", "script_id": "t1", "win_rate": 0.2},
            {"script_text": "高胜率句子不同的文本", "script_id": "t2", "win_rate": 0.8},
        ]
        scores = compute_sas_for_pool(sentences)
        assert scores[1] == pytest.approx(1.0, abs=1e-6)


class TestWriteScoredTreeWithDB:
    def test_calls_upsert_nodes_and_sentences(self):
        from unittest.mock import MagicMock, patch
        mock_db = MagicMock()
        mock_db.upsert_nodes = MagicMock()
        mock_db.upsert_sentences = MagicMock()
        with patch("f005_context_scoring.score_tree._load_decision_tree") as mock_tree, \
             patch("f005_context_scoring.score_tree.build_context_lookup", return_value={}), \
             patch("f005_context_scoring.score_tree.build_reward_lookup", return_value={}), \
             patch("f005_context_scoring.score_tree.build_turns_lookup", return_value={}), \
             patch("f005_context_scoring.score_tree.build_conversation_context_lookup", return_value={}), \
             patch("f005_context_scoring.score_tree._load_state_keywords", return_value={}):
            mock_tree.return_value = {
                "state_id": "root", "branch_key": {}, "inherited_facts": [],
                "sentence_pool": [{"script_text": "hi", "script_id": "s1", "source_call_ids": []}],
                "children": [],
            }
            import os
            import tempfile

            from f005_context_scoring.score_tree import write_scored_tree
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                tmp = f.name
            try:
                write_scored_tree(output_path=tmp, db=mock_db)
                mock_db.upsert_nodes.assert_called_once()
                mock_db.upsert_sentences.assert_called_once()
            finally:
                os.unlink(tmp)

    def test_json_has_context_vec_id_not_context_vec(self):
        from unittest.mock import patch
        with patch("f005_context_scoring.score_tree._load_decision_tree") as mock_tree, \
             patch("f005_context_scoring.score_tree.build_context_lookup", return_value={}), \
             patch("f005_context_scoring.score_tree.build_reward_lookup", return_value={}), \
             patch("f005_context_scoring.score_tree.build_turns_lookup", return_value={}), \
             patch("f005_context_scoring.score_tree.build_conversation_context_lookup", return_value={}), \
             patch("f005_context_scoring.score_tree._load_state_keywords", return_value={}):
            mock_tree.return_value = {
                "state_id": "root", "branch_key": {}, "inherited_facts": [],
                "sentence_pool": [{"script_text": "hi", "script_id": "s1", "source_call_ids": []}],
                "children": [],
            }
            import json
            import os
            import tempfile

            from f005_context_scoring.score_tree import write_scored_tree
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                tmp = f.name
            try:
                write_scored_tree(output_path=tmp, db=None)
                with open(tmp, encoding="utf-8") as f:
                    data = json.load(f)
                s = data["sentence_pool"][0]
                assert "context_vec_id" in s
                assert s["context_vec_id"] == "s1"
                assert "_context_vec" not in s
            finally:
                os.unlink(tmp)
