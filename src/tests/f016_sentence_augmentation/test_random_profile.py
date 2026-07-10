import random

import pytest

from f016_sentence_augmentation.random_profile import (
    generate_fake_call_id,
    generate_random_profile,
    generate_unique_call_id,
)

EXPECTED_PROFILE_KEYS = {
    "business_loan_balance",
    "complaint_score",
    "current_balance",
    "days_delinquent",
    "education",
    "has_business_loan",
    "has_mortgage",
    "has_other_loan",
    "has_social_insurance",
    "is_high_risk_proxy_complaint",
    "is_proxy_intermediary_complaint",
    "mortgage_balance",
    "other_loan_balance",
    "recent_contact_count",
    "recent_repayment",
    "risk_level",
    "vehicle_count",
    "wealth_value",
}

VALID_EDUCATION = {"bachelor", "college", "other", "unknown"}


class TestGenerateFakeCallId:
    def test_returns_19_digit_string(self):
        cid = generate_fake_call_id()
        assert isinstance(cid, str)
        assert len(cid) == 19
        assert cid.isdigit()

    def test_starts_with_9999(self):
        cid = generate_fake_call_id()
        assert cid.startswith("9999")

    def test_reproducible_with_seed(self):
        random.seed(42)
        cid1 = generate_fake_call_id()
        random.seed(42)
        cid2 = generate_fake_call_id()
        assert cid1 == cid2

    def test_different_calls_differ(self):
        random.seed(42)
        cid1 = generate_fake_call_id()
        cid2 = generate_fake_call_id()
        assert cid1 != cid2


class TestGenerateRandomProfile:
    def test_has_all_17_fields(self):
        profile = generate_random_profile()
        assert set(profile.keys()) == EXPECTED_PROFILE_KEYS

    def test_days_delinquent_always_30(self):
        for _ in range(100):
            profile = generate_random_profile()
            assert profile["days_delinquent"] == 30

    def test_education_in_valid_set(self):
        for _ in range(100):
            profile = generate_random_profile()
            assert profile["education"] in VALID_EDUCATION

    def test_risk_level_range(self):
        for _ in range(100):
            profile = generate_random_profile()
            assert 0 <= profile["risk_level"] <= 4

    def test_recent_contact_count_range(self):
        for _ in range(100):
            profile = generate_random_profile()
            assert 0 <= profile["recent_contact_count"] <= 13

    def test_complaint_score_range(self):
        for _ in range(100):
            profile = generate_random_profile()
            assert 0 <= profile["complaint_score"] <= 30

    def test_boolean_fields_are_bool(self):
        bool_keys = [
            "has_business_loan",
            "has_mortgage",
            "has_other_loan",
            "has_social_insurance",
            "is_high_risk_proxy_complaint",
            "is_proxy_intermediary_complaint",
            "recent_repayment",
        ]
        for _ in range(50):
            profile = generate_random_profile()
            for k in bool_keys:
                assert isinstance(profile[k], bool)

    def test_reproducible_with_seed(self):
        random.seed(123)
        p1 = generate_random_profile()
        random.seed(123)
        p2 = generate_random_profile()
        assert p1 == p2


class TestGenerateUniqueId:
    def test_no_collision_when_ids_clear(self):
        random.seed(42)
        cid = generate_unique_call_id(set(), count=2)
        assert isinstance(cid, str)
        assert len(cid) == 19
        assert cid.startswith("9999")

    def test_retries_on_collision(self):
        random.seed(42)
        first_cid = generate_fake_call_id()
        random.seed(42)
        colliding_ids = {f"{first_cid}_t1", f"{first_cid}_t2"}
        cid = generate_unique_call_id(colliding_ids, count=2)
        assert cid != first_cid
        assert f"{cid}_t1" not in colliding_ids
        assert f"{cid}_t2" not in colliding_ids

    def test_checks_all_turn_indices(self):
        random.seed(42)
        first_cid = generate_fake_call_id()
        random.seed(42)
        colliding_ids = {f"{first_cid}_t1"}
        cid = generate_unique_call_id(colliding_ids, count=2)
        assert f"{cid}_t1" not in colliding_ids

    def test_raises_after_max_retries(self):
        import pytest
        with pytest.raises(RuntimeError, match="Could not generate unique call_id"):
            generate_unique_call_id(set(), count=1, max_retries=0)
