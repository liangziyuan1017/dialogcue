def build_augmentation_prompt(
    node: dict,
    profile: dict,
    existing_sentences: list[dict],
    n: int,
) -> str:
    role = node.get("role", "")
    action_key = node.get("branch_key", {})
    collector_action = action_key.get("action", "") if isinstance(action_key, dict) else ""
    inherited_facts = node.get("inherited_facts", [])

    facts_str = "、".join(inherited_facts) if inherited_facts else "无"
    risk_level = profile.get("risk_level", 0)
    risk_desc = {0: "极低", 1: "较低", 2: "中等", 3: "较高", 4: "极高"}.get(risk_level, "中等")

    examples_section = ""
    if existing_sentences:
        lines = []
        for i, s in enumerate(existing_sentences[:3], 1):
            text = s.get("script_text", "")
            if text:
                lines.append(f"{i}. {text[:120]}")
        if lines:
            examples_section = "\n## 参考真实话术\n" + "\n".join(lines)

    prompt = f"""你正在模拟一段催收通话。请先想象客户说的话，再写出你的回复。

## 你的身份
你是银行贷后管理专员，正在和一位逾期客户通电话。

## 客户情况
- 逾期{profile.get('days_delinquent', 0)}天，欠款{profile.get('current_balance', 0)}元，风险等级{risk_desc}
- 已被联系{profile.get('recent_contact_count', 0)}次，投诉分数{profile.get('complaint_score', 0)}

## 当前对话状态
- 阶段: {collector_action} | 客户事实: {facts_str}
{examples_section}

## 任务
请想象{n}个不同的客户反应，然后针对每句话直接回应：
- 你的回复要像在通电话，直接接客户的话
- 口语化，有"嗯""呃""那个""对"等自然停顿
- 用引导式提问代替评判（如"您看您这边大概什么时候能处理一部分？"而不是"您还款意愿不强"）
- {n}条回复措辞、节奏、开场都要不同
- 每条50-200字

## 禁忌（必须遵守）
- 不要引用或复述客户的话来反驳（如"光说知道了过两天"）
- 不要对客户使用内部标签或分类术语（如"还款意愿""意愿不强""风险等级""标签"等）
- 不要暴露系统内部概念（如"挂标签""系统报警""风险等级"）
- 不要评判客户（如"您还款意愿不强"），用引导式提问代替
- 不要用"您好"开头，直接接话

- 返回JSON: {{"sentences": ["你的回复1", "你的回复2", ...]}}"""

    return prompt
