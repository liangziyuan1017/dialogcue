import random


def generate_fake_call_id() -> str:
    return "9999" + "".join(str(random.randint(0, 9)) for _ in range(15))


def generate_unique_call_id(
    existing_script_ids: set[str],
    count: int,
    max_retries: int = 100,
) -> str:
    for _ in range(max_retries):
        call_id = generate_fake_call_id()
        if not any(f"{call_id}_t{i}" in existing_script_ids for i in range(1, count + 1)):
            return call_id
    raise RuntimeError(f"Could not generate unique call_id after {max_retries} retries")


def generate_random_profile() -> dict:
    return {
        "business_loan_balance": random.choice([0, 0, 0, 50000, 200000]),
        "complaint_score": random.randint(0, 30),
        "current_balance": random.randint(1000, 5_000_000),
        "days_delinquent": 30,
        "education": random.choice(["bachelor", "college", "other", "unknown"]),
        "has_business_loan": random.choice([False, False, True]),
        "has_mortgage": random.choice([False, False, True]),
        "has_other_loan": random.choice([False, True, True]),
        "has_social_insurance": random.choice([True, False]),
        "is_high_risk_proxy_complaint": random.choice([False, False, True]),
        "is_proxy_intermediary_complaint": random.choice([False, True]),
        "mortgage_balance": random.choice([0, 0, 300000, 800000]),
        "other_loan_balance": random.randint(0, 200000),
        "recent_contact_count": random.randint(0, 13),
        "recent_repayment": random.choice([False, False, True]),
        "risk_level": random.randint(0, 4),
        "vehicle_count": random.randint(0, 3),
        "wealth_value": random.randint(0, 500000),
    }
