from f016_sentence_augmentation.generate_prompts import build_augmentation_prompt


SAMPLE_NODE = {
    "state_id": "initial_contact",
    "role": "opening",
    "branch_key": {"action": "greeting"},
    "inherited_facts": ["repayment_inability"],
    "inherited_emotions": ["anxious"],
    "sentence_pool": [
        {"script_text": "先生您好，请问是刘伟先生吗？"},
        {"script_text": "您好，我是工行的工作人员，想跟您确认一下还款事宜。"},
        {"script_text": "先生您好，关于您的贷款账户，我们需要沟通一下。"},
    ],
}

SAMPLE_PROFILE = {
    "days_delinquent": 30,
    "risk_level": 2,
    "current_balance": 500000,
    "has_mortgage": True,
    "has_business_loan": False,
    "has_other_loan": True,
    "education": "bachelor",
    "complaint_score": 5,
    "recent_contact_count": 3,
}


class TestBuildAugmentationPrompt:
    def test_prompt_contains_collector_action(self):
        prompt = build_augmentation_prompt(SAMPLE_NODE, SAMPLE_PROFILE, SAMPLE_NODE["sentence_pool"], 5)
        assert "greeting" in prompt

    def test_prompt_contains_facts(self):
        prompt = build_augmentation_prompt(SAMPLE_NODE, SAMPLE_PROFILE, SAMPLE_NODE["sentence_pool"], 5)
        assert "repayment_inability" in prompt

    def test_prompt_contains_profile_info(self):
        prompt = build_augmentation_prompt(SAMPLE_NODE, SAMPLE_PROFILE, SAMPLE_NODE["sentence_pool"], 5)
        assert "30" in prompt
        assert "500000" in prompt
        assert "3" in prompt

    def test_prompt_contains_risk_desc(self):
        prompt = build_augmentation_prompt(SAMPLE_NODE, SAMPLE_PROFILE, SAMPLE_NODE["sentence_pool"], 5)
        assert "中等" in prompt

    def test_prompt_contains_few_shot_examples(self):
        prompt = build_augmentation_prompt(SAMPLE_NODE, SAMPLE_PROFILE, SAMPLE_NODE["sentence_pool"], 5)
        assert "先生您好，请问是刘伟先生吗？" in prompt

    def test_prompt_contains_count(self):
        prompt = build_augmentation_prompt(SAMPLE_NODE, SAMPLE_PROFILE, SAMPLE_NODE["sentence_pool"], 10)
        assert "10" in prompt

    def test_prompt_contains_json_format_instruction(self):
        prompt = build_augmentation_prompt(SAMPLE_NODE, SAMPLE_PROFILE, SAMPLE_NODE["sentence_pool"], 5)
        assert "JSON" in prompt or "json" in prompt

    def test_prompt_handles_empty_pool(self):
        node = {**SAMPLE_NODE, "sentence_pool": []}
        prompt = build_augmentation_prompt(node, SAMPLE_PROFILE, [], 3)
        assert "3" in prompt
        assert len(prompt) > 50

    def test_prompt_handles_missing_optional_fields(self):
        node = {"state_id": "test_node"}
        prompt = build_augmentation_prompt(node, SAMPLE_PROFILE, [], 2)
        assert "2" in prompt
        assert len(prompt) > 50

    def test_prompt_contains_guardrail_section(self):
        prompt = build_augmentation_prompt(SAMPLE_NODE, SAMPLE_PROFILE, SAMPLE_NODE["sentence_pool"], 5)
        assert "禁忌" in prompt

    def test_prompt_contains_no_internal_labels_instruction(self):
        prompt = build_augmentation_prompt(SAMPLE_NODE, SAMPLE_PROFILE, SAMPLE_NODE["sentence_pool"], 5)
        assert "还款意愿" in prompt
        assert "标签" in prompt

    def test_prompt_contains_guided_question_instruction(self):
        prompt = build_augmentation_prompt(SAMPLE_NODE, SAMPLE_PROFILE, SAMPLE_NODE["sentence_pool"], 5)
        assert "引导式提问" in prompt

    def test_prompt_contains_no_quote_back_instruction(self):
        prompt = build_augmentation_prompt(SAMPLE_NODE, SAMPLE_PROFILE, SAMPLE_NODE["sentence_pool"], 5)
        assert "复述" in prompt
