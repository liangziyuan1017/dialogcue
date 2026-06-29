from f007_infrastructure.config import get as _cfg
from f007_infrastructure.llm_client import call_deepseek_json

BATCH_SIZE = _cfg("batch_size.analysis", 20)


def _build_batch_classify_prompt(turns: list) -> str:
    turns_text = ""
    for idx, (turn_text, context) in enumerate(turns):
        ctx = "\n".join(f"    {t['role']}: {t['text']}" for t in context)
        turns_text += f"\n---\n发言{idx+1}:\n上下文:\n{ctx}\n客户: {turn_text}"
    return f"""分析以下{len(turns)}条连续的客户发言，只标注**有明确还款态度**的意愿信号。

{turns_text}

请以JSON格式输出一个数组，每条发言对应一个元素:
[
  {{
    "willingness_signal": "resistant|weak|conditional|negotiating|strong" | null
  }}
]

标注规则:
- resistant: 明确拒绝还款、挂断、否认债务
- weak: 有还款意愿但表达无力（"想还但没钱"、"困难"）
- conditional: 有条件同意（"如果分期我可以"、"减免的话"）
- negotiating: 主动协商、讨价还价
- strong: 明确承诺还款、给出具体时间或金额
- **null**: 短应答（嗯/好/对）、纯反问、确认身份、无还款态度的发言 → 设为null，不要硬编
- 输出数组长度必须等于{len(turns)}"""


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
- 每个等级至少2个example_turn（从观测数据中选取真实发言）
- boundary要具体说明区分标准
- 等级数量由数据自然聚类决定，不要预设"""


def _build_classify_prompt(turn_text: str, context_turns: list) -> str:
    return _build_batch_classify_prompt([(turn_text, context_turns)])


def define_willingness_levels(records: list) -> list:
    all_turns = []
    for record in records:
        dialog = record["response"]["dialog"]
        for i, turn in enumerate(dialog):
            if turn["role"] != "客户":
                continue
            context_start = max(0, i - _cfg("context_window.analysis_turns_before", 3))
            context_turns = dialog[context_start:i]
            all_turns.append((turn["text"], context_turns))

    signals = []
    for batch_start in range(0, len(all_turns), BATCH_SIZE):
        batch = all_turns[batch_start:batch_start + BATCH_SIZE]
        prompt = _build_batch_classify_prompt(batch)
        try:
            results = call_deepseek_json(prompt)
            if isinstance(results, list):
                for r in results:
                    sig = r.get("willingness_signal")
                    if sig:
                        signals.append(sig)
        except Exception:
            pass

    unique_signals = list(dict.fromkeys(signals))
    if not unique_signals:
        return []

    cluster_prompt = _build_cluster_prompt(unique_signals)
    try:
        cluster_result = call_deepseek_json(cluster_prompt)
        levels = cluster_result.get("levels", [])
    except Exception:
        levels = []

    return levels
