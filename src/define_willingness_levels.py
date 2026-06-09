from src.llm_client import call_deepseek_json


def _build_classify_prompt(turn_text: str, context_turns: list) -> str:
    ctx = "\n".join(f"  {t['role']}: {t['text']}" for t in context_turns)
    return f"""分析以下催收对话中客户的还款意愿信号。

上下文:
{ctx}

客户发言: {turn_text}

请以JSON格式输出:
{{
  "willingness_signal": "resistant|weak|conditional|negotiating|strong"
}}

- resistant: 明确拒绝、挂断、否认债务
- weak: 有意愿但表达无力（没钱、困难）
- conditional: 有条件同意（如果分期、如果减免）
- negotiating: 主动协商、讨价还价
- strong: 明确承诺还款、给出具体时间/金额"""


def _build_cluster_prompt(signals: list) -> str:
    sig_text = "\n".join(f"  - {s}" for s in signals)
    return f"""根据以下从催收对话中提取的还款意愿信号，将它们聚类为有序的意愿等级（从最抗拒到最配合）。

观测到的信号:
{sig_text}

请以JSON格式输出:
{{
  "levels": [
    {{
      "level": "等级名(英文)",
      "definition": "该等级的含义",
      "boundary": "与相邻等级的区别（为什么分在这里而不是上/下一级）",
      "example_turns": [
        {{"text": "原始发言原文", "reason": "为什么归入此等级"}}
      ]
    }}
  ]
}}

要求:
- 等级从最抗拒到最配合排序
- 每个等级至少1个example_turn
- boundary要具体说明区分标准
- 等级数量由数据自然聚类决定，不要预设"""


def define_willingness_levels(records: list) -> list:
    signals = []
    example_turns_by_signal = {}

    for record in records:
        dialog = record["response"]["dialog"]
        for i, turn in enumerate(dialog):
            if turn["role"] != "客户":
                continue
            context_start = max(0, i - 3)
            context_turns = dialog[context_start:i]
            prompt = _build_classify_prompt(turn["text"], context_turns)
            try:
                result = call_deepseek_json(prompt)
                sig = result.get("willingness_signal", "weak")
                signals.append(sig)
                if sig not in example_turns_by_signal:
                    example_turns_by_signal[sig] = []
                example_turns_by_signal[sig].append(turn["text"])
            except Exception:
                pass

    unique_signals = list(dict.fromkeys(signals))
    cluster_prompt = _build_cluster_prompt(unique_signals)
    try:
        cluster_result = call_deepseek_json(cluster_prompt)
        levels = cluster_result.get("levels", [])
    except Exception:
        levels = []

    return levels
