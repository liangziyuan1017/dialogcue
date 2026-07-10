from unittest.mock import patch

import pytest

from f016_sentence_augmentation.score_sentences import (
    score_new_sentence,
    _extract_bg_constraints_single,
    _extract_bg_background_single,
)


SAMPLE_PROFILE = {
    "business_loan_balance": 50000,
    "complaint_score": 5,
    "current_balance": 500000,
    "days_delinquent": 30,
    "education": "bachelor",
    "has_business_loan": True,
    "has_mortgage": False,
    "has_other_loan": True,
    "has_social_insurance": True,
    "is_high_risk_proxy_complaint": False,
    "is_proxy_intermediary_complaint": True,
    "mortgage_balance": 0,
    "other_loan_balance": 100000,
    "recent_contact_count": 3,
    "recent_repayment": False,
    "risk_level": 2,
    "vehicle_count": 1,
    "wealth_value": 200000,
}

SAMPLE_NODE = {
    "state_id": "initial_contact",
    "role": "opening",
    "branch_key": {"action": "greeting"},
    "inherited_facts": ["repayment_inability"],
    "sentence_pool": [
        {"win_rate_node": 0.7383, "collector_action": "greeting"},
    ],
}

FAKE_CALL_ID = "9999384726105938472"


class TestExtractBgConstraintsSingle:
    def test_returns_all_10_keys(self):
        result = _extract_bg_constraints_single(SAMPLE_PROFILE)
        expected_keys = {
            "has_business_loan", "has_mortgage", "has_other_loan",
            "recent_repayment", "is_high_risk_proxy_complaint",
            "is_proxy_intermediary_complaint", "has_social_insurance",
            "has_risk_flag", "has_complaint", "has_vehicle",
        }
        assert set(result.keys()) == expected_keys

    def test_direct_booleans(self):
        result = _extract_bg_constraints_single(SAMPLE_PROFILE)
        assert result["has_business_loan"] is True
        assert result["has_mortgage"] is False
        assert result["has_other_loan"] is True
        assert result["has_social_insurance"] is True
        assert result["is_proxy_intermediary_complaint"] is True

    def test_derived_has_risk_flag(self):
        result = _extract_bg_constraints_single(SAMPLE_PROFILE)
        assert result["has_risk_flag"] is True  # risk_level=2 > 0

    def test_derived_has_risk_flag_zero(self):
        profile = {**SAMPLE_PROFILE, "risk_level": 0}
        result = _extract_bg_constraints_single(profile)
        assert result["has_risk_flag"] is False

    def test_derived_has_complaint(self):
        result = _extract_bg_constraints_single(SAMPLE_PROFILE)
        assert result["has_complaint"] is True  # complaint_score=5 > 0

    def test_derived_has_complaint_zero(self):
        profile = {**SAMPLE_PROFILE, "complaint_score": 0}
        result = _extract_bg_constraints_single(profile)
        assert result["has_complaint"] is False

    def test_derived_has_vehicle(self):
        result = _extract_bg_constraints_single(SAMPLE_PROFILE)
        assert result["has_vehicle"] is True  # vehicle_count=1 > 0


class TestExtractBgBackgroundSingle:
    def test_returns_10_keys(self):
        result = _extract_bg_background_single(SAMPLE_PROFILE)
        expected_keys = {
            "business_loan_digits", "mortgage_balance_digits", "other_loan_digits",
            "wealth_digits", "current_balance_digits", "education",
            "days_delinquent", "recent_contact_count", "risk_level", "complaint_score",
        }
        assert set(result.keys()) == expected_keys

    def test_digit_counts(self):
        result = _extract_bg_background_single(SAMPLE_PROFILE)
        assert result["business_loan_digits"] == 5  # 50000 -> 5 digits
        assert result["mortgage_balance_digits"] == 0  # 0 -> 0
        assert result["other_loan_digits"] == 6  # 100000 -> 6 digits
        assert result["current_balance_digits"] == 6  # 500000 -> 6 digits
        assert result["wealth_digits"] == 6  # 200000 -> 6 digits

    def test_passthrough_fields(self):
        result = _extract_bg_background_single(SAMPLE_PROFILE)
        assert result["education"] == "bachelor"
        assert result["days_delinquent"] == 30
        assert result["recent_contact_count"] == 3
        assert result["risk_level"] == 2
        assert result["complaint_score"] == 5


class TestScoreNewSentence:
    @patch("f016_sentence_augmentation.score_sentences.embed_single")
    def test_script_id_format(self, mock_embed):
        mock_embed.return_value = [0.1] * 1024
        sentence = score_new_sentence("test text", SAMPLE_PROFILE, FAKE_CALL_ID, 1, SAMPLE_NODE)
        assert sentence["script_id"] == "9999384726105938472_t1"

    @patch("f016_sentence_augmentation.score_sentences.embed_single")
    def test_source_call_ids_format(self, mock_embed):
        mock_embed.return_value = [0.1] * 1024
        sentence = score_new_sentence("test text", SAMPLE_PROFILE, FAKE_CALL_ID, 1, SAMPLE_NODE)
        assert sentence["source_call_ids"] == [FAKE_CALL_ID]

    @patch("f016_sentence_augmentation.score_sentences.embed_single")
    def test_win_rate_uses_node_value(self, mock_embed):
        mock_embed.return_value = [0.1] * 1024
        sentence = score_new_sentence("test text", SAMPLE_PROFILE, FAKE_CALL_ID, 1, SAMPLE_NODE)
        assert sentence["win_rate"] == 0.7383
        assert sentence["win_rate_node"] == 0.7383

    @patch("f016_sentence_augmentation.score_sentences.embed_single")
    def test_deferred_is_true(self, mock_embed):
        mock_embed.return_value = [0.1] * 1024
        sentence = score_new_sentence("test text", SAMPLE_PROFILE, FAKE_CALL_ID, 1, SAMPLE_NODE)
        assert sentence["deferred"] is True

    @patch("f016_sentence_augmentation.score_sentences.embed_single")
    def test_uplift_and_csi_zero(self, mock_embed):
        mock_embed.return_value = [0.1] * 1024
        sentence = score_new_sentence("test text", SAMPLE_PROFILE, FAKE_CALL_ID, 1, SAMPLE_NODE)
        assert sentence["uplift_score"] == 0
        assert sentence["csi"] == 0

    @patch("f016_sentence_augmentation.score_sentences.embed_single")
    def test_conversation_context_empty(self, mock_embed):
        mock_embed.return_value = [0.1] * 1024
        sentence = score_new_sentence("test text", SAMPLE_PROFILE, FAKE_CALL_ID, 1, SAMPLE_NODE)
        assert sentence["conversation_context"] == ""

    @patch("f016_sentence_augmentation.score_sentences.embed_single")
    def test_sas_is_zero(self, mock_embed):
        mock_embed.return_value = [0.1] * 1024
        sentence = score_new_sentence("test text", SAMPLE_PROFILE, FAKE_CALL_ID, 1, SAMPLE_NODE)
        assert sentence["sas"] == 0.0

    @patch("f016_sentence_augmentation.score_sentences.embed_single")
    def test_bg_constraints_present(self, mock_embed):
        mock_embed.return_value = [0.1] * 1024
        sentence = score_new_sentence("test text", SAMPLE_PROFILE, FAKE_CALL_ID, 1, SAMPLE_NODE)
        assert "has_business_loan" in sentence["bg_constraints"]
        assert sentence["bg_constraints"]["has_business_loan"] is True

    @patch("f016_sentence_augmentation.score_sentences.embed_single")
    def test_bg_bitmask_present(self, mock_embed):
        mock_embed.return_value = [0.1] * 1024
        sentence = score_new_sentence("test text", SAMPLE_PROFILE, FAKE_CALL_ID, 1, SAMPLE_NODE)
        assert isinstance(sentence["bg_bitmask"], dict)
        assert all(v in (0, 1) for v in sentence["bg_bitmask"].values())

    @patch("f016_sentence_augmentation.score_sentences.embed_single")
    def test_bg_bitmask_int_is_int(self, mock_embed):
        mock_embed.return_value = [0.1] * 1024
        sentence = score_new_sentence("test text", SAMPLE_PROFILE, FAKE_CALL_ID, 1, SAMPLE_NODE)
        assert isinstance(sentence["bg_bitmask_int"], int)

    @patch("f016_sentence_augmentation.score_sentences.embed_single")
    def test_bg_background_10_keys(self, mock_embed):
        mock_embed.return_value = [0.1] * 1024
        sentence = score_new_sentence("test text", SAMPLE_PROFILE, FAKE_CALL_ID, 1, SAMPLE_NODE)
        assert len(sentence["bg_background"]) == 10

    @patch("f016_sentence_augmentation.score_sentences.embed_single")
    def test_gesture_type_absent_for_non_gesture(self, mock_embed):
        mock_embed.return_value = [0.1] * 1024
        node = {**SAMPLE_NODE, "role": "action", "branch_key": {"action": "negotiate"}}
        sentence = score_new_sentence("test text", SAMPLE_PROFILE, FAKE_CALL_ID, 1, node)
        assert "gesture_type" not in sentence

    @patch("f016_sentence_augmentation.score_sentences.embed_single")
    def test_gesture_type_opening_for_greeting(self, mock_embed):
        mock_embed.return_value = [0.1] * 1024
        sentence = score_new_sentence("test text", SAMPLE_PROFILE, FAKE_CALL_ID, 1, SAMPLE_NODE)
        assert sentence.get("gesture_type") == "opening"

    @patch("f016_sentence_augmentation.score_sentences.embed_single")
    def test_embedding_stored_separately(self, mock_embed):
        mock_embed.return_value = [0.1] * 1024
        sentence = score_new_sentence("test text", SAMPLE_PROFILE, FAKE_CALL_ID, 1, SAMPLE_NODE)
        assert "_embedding" in sentence
        assert len(sentence["_embedding"]) == 1024

    @patch("f016_sentence_augmentation.score_sentences.embed_single")
    def test_empty_pool_uses_default_win_rate(self, mock_embed):
        mock_embed.return_value = [0.1] * 1024
        node = {**SAMPLE_NODE, "sentence_pool": []}
        sentence = score_new_sentence("test text", SAMPLE_PROFILE, FAKE_CALL_ID, 1, node)
        assert sentence["win_rate"] == 0.5

    @patch("f016_sentence_augmentation.score_sentences.embed_single")
    def test_embedding_none_when_service_down(self, mock_embed):
        mock_embed.return_value = None
        sentence = score_new_sentence("test text", SAMPLE_PROFILE, FAKE_CALL_ID, 1, SAMPLE_NODE)
        assert sentence["_embedding"] is None
