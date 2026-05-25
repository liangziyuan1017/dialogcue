"""Dialog correction via DeepSeek LLM (two-pass pipeline).

Pass 1: Fix ASR transcription errors in dialog text.
Pass 2: Logical turn alignment via segmented LLM calls
  (merge fragmented, insert missing, reorder out-of-sequence).

Each pass uses a focused prompt to improve instruction adherence.
Long dialogs are split into segments for Pass 2 to stay within
token limits. Results are written to output.py.
"""

import json
import os
import re
import sys
from pathlib import Path

from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "(basic) data_0520.json"
OUTPUT_FILE = BASE_DIR / "output.py"

SEGMENT_SIZE = 35

PASS1_PROMPT = """你是中文催收通话 ASR 转写校正专家。你的唯一任务是对话文本中的 ASR 转写错误。

【最重要规则】你必须直接在 dialog 数组的 text 字段中输出修正后的文本。不要只在 correction_notes 中记录修正而不修改 text。text 字段必须已经是修正后的结果。

核心原则：
- 只修正 ASR 错误，不润色、不改写、不总结、不补充事实
- 保留真实口语状态：口吃、犹豫、重复、情绪表达、语气词、不完整句子
- 例如保留："嗯""呃""对对对""我我现在没办法""唉压力很大"

需要修正的 ASR 错误类型：
1. 同音/近音错误
2. 语音粘连误识别
3. 语音截断误识别
4. 数字格式混乱
5. 角色标签误入正文（如文本中出现"催收员："或"客户："，拆分为独立轮次）

常见ASR错误模式（不仅限于此）：

| 错误转写 | 正确文本 | 错误类型 |
|---------|---------|---------|
| 诊端部门 | 前端部门 | 近音误识别 |
| 寄收 | 催收 | 近音误识别 |
| 刑专员 | 行专员 | 近音误识别 |
| 书证 | 书面证明 | 近音误识别 |
| 全额销售 | 全额催收 | 近音误识别 |
| 标红即前转转 | 标红，即将转 | 语音粘连 |
| 停卡审务 | 停卡审核 | 近音误识别 |
| 收员： | 催收员： | 角色标签截断 |
| 预预散件 | 预审件 | 语音粘连 |
| 法派成序 | 法派程序 | 近音误识别 |
| 法败 | 法院判决 | 语音截断 |
| 102.钟 | 10点钟 | 符号误识别 |
| 1000千292 | 一千二百九十二 | 数字格式混乱 |
| 9毛一 | 9毛1 | 口语数字格式 |
| 这理 | 这里 | 近音误识别 |
| 协商商 | 协商 | 重复误识别 |
| 案件件 | 案件 | 重复误识别 |
| 这这个 | 这个 | 重复误识别 |
| 需帮利交 | 循环利息 | 近音误识别 |
| 检系系统 | 检测系统 | 近音误识别 |
| 合动卡 | 和冻卡 | 近音误识别 |
| 利求 | 利息 | 近音误识别 |
| 循环利求 | 循环利息 | 近音误识别 |
| 再线话 | 再电话 | 近音误识别 |
| 方可抵消时 | 方案可以抵消 | 语音粘连 |
| 20000万6000 | 26000 | 数字误识别 |
| 将产 | 将 | 重复误识别 |
| 开发工资 | 发工资 | 重复误识别 |
| 为该说 | 就是说 | 近音误识别 |
| 做完天 | 怎么 | 近音误识别 |
| 什意思 | 什么意思 | 截断误识别 |
| 分期相才也经 | 分期刚才已经 | 近音误识别 |

角色标签渗入正文规则：
当 text 中出现 "催收员：" 或 "客户：" 时，将其作为角色切换点拆分为两个独立轮次。

输入格式：
{
  "call_id": "通话ID",
  "dialog": [
    {"role": "催收员|客户", "text": "原始ASR文本"}
  ],
  "calldate": "通话日期",
  "custno": "客户编号",
  "colluserid": "催收员工号"
}

输出格式（JSON，与输入相同结构，但 text 已修正）：
{
  "call_id": "原通话ID",
  "dialog": [
    {"role": "催收员|客户", "text": "修正后的文本"}
  ],
  "calldate": "原通话日期",
  "custno": "原客户编号",
  "colluserid": "原催收员工号",
  "correction_notes": ["诊端→前端", "寄收→催收"]
}

再次强调：dialog 中每个 turn 的 text 必须是修正后的文本，不是原始文本！"""

PASS2_PROMPT = """你是中文催收通话对话轮次对齐专家。

【最重要规则】
1. 你必须在 dialog 中输出调整后的完整轮次列表，反映你的所有判断结果。
2. 输出的 dialog 必须与你的 alignment_decisions 一致。
3. 不要原样返回输入 dialog，必须执行你的判断。

你的任务：对每个连续同角色轮次对，先判断再操作。

判断分类：

情况A（碎片化）：同一说话人的一句话被ASR切成多段。
  判断依据：前后轮次语义连贯，属于同一话题的延续，对方没有理由插话。
  操作：合并为一个轮次，用逗号连接文本。
  示例：催收员说"女士您好"和"您目前的欠款是61000多"→合并为"女士您好, 您目前的欠款是61000多"

情况B（缺失回应）：对方的回应被ASR遗漏。
  判断依据：前一轮次是提问（含"吗""呢""？"）或需要对方回应的陈述，对方理应插话确认。
  操作：在两轮之间插入对方的短确认轮次，标记 source="ai-generated"。
  允许补充的回应仅限："嗯""好""对""是""知道了""明白""噢""啊"。
  禁止补充：金额、承诺、还款计划、时间、法律态度、任何事实信息。

情况C（顺序错乱）：轮次被ASR放错了位置。
  判断依据：当前轮次的回应内容与紧邻的上一轮次不匹配，但与更早的某轮次构成问答关系。
  操作：将该轮次移到逻辑上正确的位置。

情况D（合理连续）：同一说话人合理连续发言，逻辑连贯。
  判断依据：说话人在陈述一段较长内容，对方无需插话。
  操作：保持原样，不合并也不插入。

保留项（不可修改）：
- 口吃、犹豫、重复、情绪表达、语气词、不完整句子

输入格式（JSON）：
{
  "dialog": [
    {"role": "催收员|客户", "text": "文本"}
  ]
}

输出格式（JSON）：
{
  "alignment_decisions": [
    {"index": 0, "type": "A|B|C|D", "reason": "判断理由", "action": "执行的操作描述"}
  ],
  "dialog": [
    {"role": "催收员|客户", "text": "文本", "source": "original"},
    {"role": "客户", "text": "嗯", "source": "ai-generated", "confidence": "high"}
  ]
}

规则：
- source 默认为 "original"，仅插入的轮次为 "ai-generated"
- confidence 仅 ai-generated 时出现，取值 high/medium/low
- alignment_decisions 记录每个判断，最多20条
- dialog 必须是执行判断后的结果，不是原始输入"""


def create_client() -> OpenAI:
    """Creates an OpenAI client configured for DeepSeek V4.

    Reads the API key from the DEEPSEEK_API_KEY environment variable.

    Returns:
        Configured OpenAI client instance.

    Raises:
        SystemExit: If DEEPSEEK_API_KEY is not set.
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("Error: DEEPSEEK_API_KEY environment variable is not set.")
        print("Export it before running: export DEEPSEEK_API_KEY=your_key")
        sys.exit(1)
    return OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
    )


def load_first_record() -> dict:
    """Loads the first dialog record from the basic data file.

    Converts the semicolon-separated dialog string into a turns array
    for the LLM input format.

    Returns:
        Dictionary with call_id, dialog (as turns array), calldate,
        custno, colluserid.
    """
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    record = data[0]

    dialog_raw = record.get("dialog", "")
    turns = []
    for seg in re.split(r"[；;]", dialog_raw):
        seg = seg.strip()
        if not seg:
            continue
        m = re.match(r"^(催收员|客户)[：:]\s*(.*)", seg)
        if m:
            turns.append({"role": m.group(1), "text": m.group(2).strip()})
        elif turns:
            turns[-1]["text"] += seg

    return {
        "call_id": record.get("call_id", ""),
        "dialog": turns,
        "calldate": record.get("calldate", ""),
        "custno": record.get("custno", ""),
        "colluserid": record.get("colluserid", ""),
    }


def _call_llm(
    client: OpenAI,
    system_prompt: str,
    user_data: dict,
    max_tokens: int = 16384,
) -> dict:
    """Calls DeepSeek V4 with a system prompt and user data.

    Args:
        client: OpenAI client configured for DeepSeek.
        system_prompt: System prompt for the specific pass.
        user_data: Dialog record dict to send as user message.
        max_tokens: Maximum tokens in the response.

    Returns:
        Parsed JSON dict from the LLM response.
    """
    user_message = json.dumps(user_data, ensure_ascii=False)

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    finish_reason = response.choices[0].finish_reason

    if finish_reason == "length":
        print(f"  Warning: response truncated (finish_reason=length)")

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        print(f"  Raw response (last 500 chars): ...{content[-500:]}")
        raise


def pass1_fix_asr(client: OpenAI, record: dict) -> dict:
    """Pass 1: Fixes ASR transcription errors in dialog text.

    Args:
        client: OpenAI client configured for DeepSeek.
        record: Dialog record with turns array.

    Returns:
        Record with corrected text in each turn.
    """
    print("Pass 1: Fixing ASR transcription errors...")
    result = _call_llm(client, PASS1_PROMPT, record)

    corrected_count = len(result.get("correction_notes", []))
    turns_count = len(result.get("dialog", []))
    print(f"  Turns: {turns_count}, Corrections applied: {corrected_count}")

    return result


def _split_into_segments(turns: list[dict], size: int) -> list[list[dict]]:
    """Splits a turns list into overlapping segments.

    Each segment overlaps by 2 turns with the next to maintain
    conversational context across segment boundaries.

    Args:
        turns: List of dialog turn dicts.
        size: Target number of turns per segment.

    Returns:
        List of turn segments (lists).
    """
    if len(turns) <= size:
        return [turns]

    segments = []
    i = 0
    while i < len(turns):
        end = min(i + size, len(turns))
        segments.append(turns[i:end])
        if end >= len(turns):
            break
        i += size - 2
    return segments


def _align_segment(client: OpenAI, segment: list[dict]) -> list[dict]:
    """Aligns a single segment of turns via LLM.

    Args:
        client: OpenAI client configured for DeepSeek.
        segment: List of dialog turn dicts.

    Returns:
        Aligned list of turns with source annotations.
    """
    payload = {"dialog": segment}
    result = _call_llm(client, PASS2_PROMPT, payload, max_tokens=16384)
    return result.get("dialog", segment)


def _stitch_segments(
    segments: list[list[dict]],
    aligned_segments: list[list[dict]],
) -> list[dict]:
    """Stitches aligned segments back into a single turns list.

    Removes overlap duplicates by keeping the version from the
    later segment (which has more context for boundary turns).

    Args:
        segments: Original segments (for overlap reference).
        aligned_segments: LLM-aligned segments.

    Returns:
        Single merged list of turns.
    """
    if len(aligned_segments) == 1:
        return aligned_segments[0]

    result = list(aligned_segments[0])
    for i in range(1, len(aligned_segments)):
        overlap = 2
        orig_overlap = segments[i][:overlap]
        aligned = aligned_segments[i]

        skip = 0
        for j, t in enumerate(aligned[:overlap + 2]):
            if j < len(orig_overlap) and t.get("text", "") == orig_overlap[j].get("text", ""):
                skip = j + 1
            else:
                break

        result.extend(aligned[max(skip, overlap):])

    return result


def pass2_align_turns(client: OpenAI, record: dict) -> dict:
    """Pass 2: Aligns dialog turns using segmented LLM calls.

    Splits long dialogs into segments, aligns each via LLM, then
    stitches results back together.

    Args:
        client: OpenAI client configured for DeepSeek.
        record: Dialog record with ASR-corrected turns.

    Returns:
        Record with aligned turns and source annotations.
    """
    turns = record.get("dialog", [])
    segments = _split_into_segments(turns, SEGMENT_SIZE)

    print(f"Pass 2: Aligning dialog turns ({len(turns)} turns, {len(segments)} segments)...")

    aligned_segments = []
    for i, seg in enumerate(segments):
        print(f"  Segment {i+1}/{len(segments)}: {len(seg)} turns")
        aligned = _align_segment(client, seg)
        ai_in_seg = sum(1 for t in aligned if t.get("source") == "ai-generated")
        print(f"    -> {len(aligned)} turns, {ai_in_seg} ai-generated")
        aligned_segments.append(aligned)

    final_turns = _stitch_segments(segments, aligned_segments)

    ai_count = sum(1 for t in final_turns if t.get("source") == "ai-generated")
    print(f"  Stitched: {len(final_turns)} turns, {ai_count} ai-generated")

    record["dialog"] = final_turns
    return record


KNOWN_ASR_FIXES = [
    (r"收员[：:]", "催收员:"),
    (r"诊端", "前端"),
    (r"寄收", "催收"),
    (r"刑专员", "行专员"),
    (r"书证", "书面证明"),
    (r"全额销售", "全额催收"),
    (r"标红即前转转", "标红，即将转"),
    (r"停卡审务", "停卡审核"),
    (r"预预散件", "预审件"),
    (r"法派成序", "法派程序"),
    (r"102\.钟", "10点钟"),
    (r"1000千292", "一千二百九十二"),
    (r"9毛一", "9毛1"),
    (r"利求", "利息"),
    (r"需帮利交", "循环利息"),
    (r"检系系统", "检测系统"),
    (r"合动卡", "和冻卡"),
    (r"风险金我", "风险，我"),
    (r"方可抵消时", "方案可以抵消"),
    (r"20000万6000", "26000"),
    (r"将产,", "将，"),
    (r"开发工资", "发工资"),
    (r"为该说", "就是说"),
    (r"做完天", "怎么"),
    (r"什意思", "什么意思"),
    (r"分期相才也经", "分期刚才已经"),
    (r"再线话", "再电话"),
    (r"出后", "后续"),
    (r"如话", "如果"),
    (r"20026000", "26000"),
    (r"121999", "121999"),
    (r"462块6毛一", "462块6毛1"),
    (r"22800我就28000", "28000"),
    (r"绑到绑到", "宽限到"),
    (r"明这你这", "明天这"),
    (r"以后续要", "后续由"),
    (r"催收员[：:]", "催收员:"),
    (r"催催收员[：:]", "催收员:"),
]


def apply_known_corrections(record: dict) -> dict:
    """Applies known ASR fixes programmatically as a safety net.

    Catches errors the LLM may have missed by applying regex
    replacements to each turn's text.

    Args:
        record: Dialog record with turns array.

    Returns:
        Record with all known corrections applied.
    """
    turns = record.get("dialog", [])
    fix_count = 0
    for turn in turns:
        text = turn.get("text", "")
        for pattern, replacement in KNOWN_ASR_FIXES:
            new_text = re.sub(pattern, replacement, text)
            if new_text != text:
                fix_count += 1
                text = new_text
        turn["text"] = text

    notes = record.get("correction_notes", [])
    if fix_count > 0:
        notes.append(f"程序化补充修正{fix_count}处ASR错误")
    record["correction_notes"] = notes
    print(f"  Programmatic fixes applied: {fix_count}")
    return record


def split_role_labels(record: dict) -> dict:
    """Splits turns where role labels appear embedded in text.

    When a turn's text contains "催收员:" or "客户:", splits it
    into separate turns at those boundaries.

    Args:
        record: Dialog record with turns array.

    Returns:
        Record with role-label bleeds split into separate turns.
    """
    turns = record.get("dialog", [])
    result = []
    split_count = 0

    for t in turns:
        text = t.get("text", "")
        parts = re.split(r"(催收员|客户)[：:]", text)
        if len(parts) <= 1:
            result.append(t)
            continue

        roles_in_text = re.findall(r"(催收员|客户)[：:]", text)

        if parts[0].strip():
            result.append({"role": t["role"], "text": parts[0].strip()})

        for j, role in enumerate(roles_in_text):
            text_idx = j * 2 + 2
            if text_idx < len(parts):
                chunk = parts[text_idx].strip()
                if chunk:
                    new_turn = {"role": role, "text": chunk}
                    if t.get("source"):
                        new_turn["source"] = t["source"]
                    result.append(new_turn)
                    split_count += 1

    record["dialog"] = result
    notes = record.get("alignment_notes", [])
    if split_count > 0:
        notes.append(f"拆分{split_count}个角色标签渗入的轮次")
    record["alignment_notes"] = notes
    print(f"  Split {split_count} turns with embedded role labels")
    return record


def write_output(result: dict) -> None:
    """Writes the corrected result to output.py as a Python variable.

    Args:
        result: Corrected dialog dict from the LLM.
    """
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("corrected_output = ")
        f.write(json.dumps(result, ensure_ascii=False, indent=2))
        f.write("\n")


def main() -> None:
    """Main entry point: load data, run two-pass LLM correction, write output."""
    client = create_client()
    record = load_first_record()

    print(f"Input call_id: {record['call_id']}")
    print(f"Input turns: {len(record['dialog'])}")
    print()

    result1 = pass1_fix_asr(client, record)
    result1 = apply_known_corrections(result1)
    print()

    result2 = pass2_align_turns(client, result1)
    result2 = split_role_labels(result2)
    result2 = apply_known_corrections(result2)
    print()

    write_output(result2)

    turns = result2.get("dialog", [])
    ai_count = sum(1 for t in turns if t.get("source") == "ai-generated")
    print(f"Final output written to {OUTPUT_FILE}")
    print(f"  Total turns: {len(turns)}")
    print(f"  AI-generated turns: {ai_count}")
    print(f"  Original turns: {len(turns) - ai_count}")


if __name__ == "__main__":
    main()
