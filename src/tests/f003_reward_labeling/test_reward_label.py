from f003_reward_labeling.reward_label import label_reward, label_all, cross_validate


def _sample_record(reward_trigger=True, plan_eval_provides=True):
    rec = {
        "call_id": "test-001",
        "custno": "0100252354",
        "plan_evaluation": "调减方案   | 提供" if plan_eval_provides else "调减方案   | 未提供",
        "turns_annotated": [
            {"turn_index": 0, "role": "催收员", "text": "您好，请问是张女士吗？", "state": {"action": "greeting"}},
            {"turn_index": 1, "role": "客户", "text": "对。"},
            {"turn_index": 2, "role": "催收员", "text": "女士，我帮您申请减免，您看还26000多可以吗？", "state": {"action": "plan_proposal"}},
            {"turn_index": 3, "role": "客户", "text": "好的，我同意。" if reward_trigger else "我再想想。"},
        ],
        "reward": None,
        "state_transitions": [],
        "context": {},
    }
    return rec


def test_label_reward_returns_zero_or_one():
    rec = _sample_record(reward_trigger=True)
    result = label_reward(rec)
    assert result["reward"] in (0, 1)


def test_label_reward_positive_has_evidence():
    rec = _sample_record(reward_trigger=True)
    result = label_reward(rec)
    if result["reward"] == 1:
        assert "reward_evidence" in result
        assert result["reward_evidence"] is not None
        assert "reward_action_credit" in result
        assert result["reward_action_credit"] is not None


def test_label_reward_negative_has_no_action_credit():
    rec = _sample_record(reward_trigger=False)
    result = label_reward(rec)
    if result["reward"] == 0:
        assert result.get("reward_action_credit") is None


def test_label_reward_positive_has_action_credit():
    rec = _sample_record(reward_trigger=True)
    result = label_reward(rec)
    if result["reward"] == 1:
        assert "reward_action_credit" in result
        credit = result["reward_action_credit"]
        assert "turn_index" in credit
        assert "action" in credit
        assert "text" in credit


def test_label_all_returns_all_records():
    recs = [_sample_record(), _sample_record()]
    recs[0]["call_id"] = "test-001"
    recs[1]["call_id"] = "test-002"
    results = label_all(recs)
    assert len(results) == 2


def test_label_all_every_record_has_reward():
    recs = [_sample_record(reward_trigger=True), _sample_record(reward_trigger=False)]
    results = label_all(recs)
    for r in results:
        assert r["reward"] in (0, 1)


def test_cross_validate_flags_mismatch():
    rec_r1_plan_fail = {
        "call_id": "mismatch-001",
        "reward": 1,
        "reward_evidence": "customer agreed",
        "reward_action_credit": {"turn_index": 2, "action": "plan_proposal", "text": "我帮您申请减免"},
        "plan_evaluation": "调减方案   | 未提供",
    }
    warnings = cross_validate([rec_r1_plan_fail])
    assert len(warnings) >= 1
    assert any("mismatch-001" in w for w in warnings)


def test_cross_validate_no_warning_on_match():
    rec_r1_plan_ok = {
        "call_id": "match-001",
        "reward": 1,
        "reward_evidence": "customer agreed",
        "reward_action_credit": {"turn_index": 2, "action": "plan_proposal", "text": "我帮您申请减免"},
        "plan_evaluation": "调减方案   | 提供",
    }
    warnings = cross_validate([rec_r1_plan_ok])
    assert len(warnings) == 0


def test_cross_validate_r0_no_warning():
    rec_r0 = {
        "call_id": "r0-001",
        "reward": 0,
        "plan_evaluation": "调减方案   | 未提供",
    }
    warnings = cross_validate([rec_r0])
    assert len(warnings) == 0


def test_r0_record_has_no_action_credit():
    rec = _sample_record(reward_trigger=False)
    result = label_reward(rec)
    if result["reward"] == 0:
        assert result.get("reward_action_credit") is None


def test_reward_evidence_structure():
    rec = _sample_record(reward_trigger=True)
    result = label_reward(rec)
    if result["reward"] == 1:
        evidence = result["reward_evidence"]
        assert isinstance(evidence, dict)
        assert "trigger_text" in evidence
        assert "trigger_turn_index" in evidence


def test_reward_action_credit_points_to_customer_turn():
    rec = _sample_record(reward_trigger=True)
    result = label_reward(rec)
    if result["reward"] == 1:
        credit = result["reward_action_credit"]
        trigger_turn_index = result["reward_evidence"]["trigger_turn_index"]
        assert credit["turn_index"] == trigger_turn_index
        customer_turns = [t for t in rec["turns_annotated"] if t["role"] == "客户"]
        trigger_text = result["reward_evidence"]["trigger_text"]
        assert any(trigger_text in t["text"] for t in customer_turns)


def test_reward_action_credit_is_customer_acceptance():
    rec = _sample_record(reward_trigger=True)
    result = label_reward(rec)
    if result["reward"] == 1:
        credit = result["reward_action_credit"]
        assert credit["role"] == "客户"
        assert credit["action"] in ("accept_plan", "promise_to_pay", "agree_to_pay")


def test_r1_only_when_customer_accepts_plan_or_promises():
    rec_no_accept = {
        "call_id": "no-accept-001",
        "custno": "0100252354",
        "plan_evaluation": "调减方案   | 未提供",
        "turns_annotated": [
            {"turn_index": 0, "role": "催收员", "text": "您好，请问是张女士吗？", "state": {"action": "greeting"}},
            {"turn_index": 1, "role": "客户", "text": "嗯。"},
            {"turn_index": 2, "role": "催收员", "text": "女士，您看还26000多可以吗？", "state": {"action": "plan_proposal"}},
            {"turn_index": 3, "role": "客户", "text": "我知道了。"},
        ],
        "reward": None,
        "state_transitions": [],
        "context": {},
    }
    result = label_reward(rec_no_accept)
    assert result["reward"] == 0


def test_reward_action_credit_has_explanation():
    rec = _sample_record(reward_trigger=True)
    result = label_reward(rec)
    if result["reward"] == 1:
        credit = result["reward_action_credit"]
        assert "explanation" in credit
        assert isinstance(credit["explanation"], str)
        assert len(credit["explanation"]) > 0
        assert len(credit["explanation"].split()) <= 100
