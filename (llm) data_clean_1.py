"""Dialog correction pipeline: Pre-process → Identify → Apply → Verify.

Step 1: Programmatic pre-processing (CN punct, known ASR, role labels).
Step 2: LLM identifies structural issues (merge/insert/reorder).
Step 3: Apply structural changes programmatically.
Step 4: LLM identifies remaining ASR errors.
Step 5: Apply ASR corrections programmatically with validation.
Step 6: Verify and safety net.

Key design: LLM only outputs a small list of changes, never the
entire dialog. This avoids token limits, truncation, and the
"LLM lists fixes but doesn't apply them" problem.
"""

import json
import os
import re
import sys
from copy import deepcopy
from pathlib import Path

from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "(basic) data_0520.json"
OUTPUT_FILE = BASE_DIR / "output_1.py"

STRUCTURAL_PROMPT = """你是中文催收通话对话结构分析专家。

你的任务是分析对话轮次的结构问题，输出一个操作列表。你不需要修改对话文本，只需要识别结构问题并输出操作指令。

对每个连续同角色轮次对，判断属于哪种情况：

A. MERGE（碎片化）：同一说话人的一句话被ASR切成多段。
   判断依据：前后轮次语义连贯，属于同一话题延续，对方没有理由插话。
   示例：催收员说"女士您好"后继续说"您目前的欠款是61000多" → 合并

B. INSERT（缺失回应）：对方的回应被ASR遗漏。
   判断依据：前一轮次是提问（含"吗""呢""？"）或需要对方回应的陈述，但下一轮次仍是同一说话人。
   允许插入的回应仅限短确认："嗯""好""对""是""知道了""明白""噢""啊"。
   禁止插入：金额、承诺、还款计划、时间、法律态度、任何事实信息。

C. REORDER（顺序错乱）：轮次被ASR放错了位置。
   判断依据：当前轮次的回应内容与紧邻的上一轮次不匹配，但与更早的某轮次构成问答关系。

D. KEEP（合理连续）：同一说话人合理连续发言。
   判断依据：说话人在陈述一段较长内容，逻辑连贯，对方无需插话。

输入（JSON）：
{
  "dialog": [
    {"index": 0, "role": "催收员", "text": "..."},
    {"index": 1, "role": "客户", "text": "..."}
  ]
}

输出（JSON）：
{
  "operations": [
    {"type": "merge", "from_index": 5, "to_index": 7, "reason": "同一说话人连续发言，语义连贯"},
    {"type": "insert", "after_index": 10, "role": "客户", "text": "嗯", "confidence": "high", "reason": "催收员提问后缺失客户回应"},
    {"type": "reorder", "index": 12, "move_after_index": 10, "reason": "该轮次回答的是第10轮的提问"}
  ]
}

注意：
- 只输出需要操作的轮次，KEEP的不需要列出
- index 使用输入中的 index 字段
- operations 列表按执行顺序排列（先reorder，再merge，再insert）
- 最多输出50个操作"""

ASR_FIX_PROMPT = """你是中文催收通话 ASR 转写校正专家。

你的任务是识别对话文本中剩余的 ASR 转写错误，输出一个修正列表。你不需要输出整个对话，只需要列出需要修正的地方。

注意：以下错误已经被程序化修正，不需要再识别：
诊端→前端, 寄收→催收, 刑专员→行专员, 书证→书面证明, 全额销售→全额催收,
标红即前转转, 停卡审务→停卡审核, 预预散件→预审件, 法派成序→法派程序,
利求→利息, 需帮利交→循环利息, 检系系统→检测系统, 合动卡→和冻卡,
方可抵消时→方案可以抵消, 再线话→再电话, 为该说→就是说, 做完天→怎么,
什意思→什么意思, 分期相才也经→分期刚才已经, 开发工资→发工资,
20000万6000→26000, 9毛一→9毛1, 102.钟→10点钟

你需要识别的是以上未覆盖的 ASR 错误，例如：
- 其他近音/同音错误
- 其他语音粘连
- 其他数字格式问题
- 口语中常见的ASR混淆（如"还"→"返", "行"→"姓"等）

保留项（不可标记为错误）：
- 口吃、犹豫、重复、情绪表达、语气词、不完整句子

输入（JSON）：
{
  "dialog": [
    {"index": 0, "role": "催收员", "text": "..."},
    {"index": 1, "role": "客户", "text": "..."}
  ]
}

输出（JSON）：
{
  "corrections": [
    {"index": 5, "from": "错误原文", "to": "正确文本", "reason": "近音误识别"},
    {"index": 12, "from": "错误原文", "to": "正确文本", "reason": "语音粘连"}
  ]
}

注意：
- from 必须是 turn 中实际存在的文本片段（用于验证定位）
- 每个修正只替换 from 为 to，不影响该 turn 的其他文本
- 最多输出30个修正"""


CN_TO_EN_PUNCT = {
    "\uff0c": ",", "\u3002": ".", "\uff1f": "?", "\uff01": "!",
    "\uff1a": ":", "\uff1b": ";", "\u3001": ",",
    "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
    "\uff08": "(", "\uff09": ")", "\u3010": "[", "\u3011": "]",
    "\u300a": "<", "\u300b": ">",
}

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
    (r"462块6毛一", "462块6毛1"),
    (r"22800我就28000", "28000"),
    (r"绑到绑到", "宽限到"),
    (r"明这你这", "明天这"),
    (r"以后续要", "后续由"),
    (r"催收员[：:]", "催收员:"),
    (r"催催收员[：:]", "催收员:"),
]


def create_client() -> OpenAI:
    """Creates an OpenAI client configured for DeepSeek V4."""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("Error: DEEPSEEK_API_KEY environment variable is not set.")
        sys.exit(1)
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")


def load_first_record() -> dict:
    """Loads the first dialog record as a turns array with indices."""
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

    for i, t in enumerate(turns):
        t["index"] = i
        t["source"] = "original"

    return {
        "call_id": record.get("call_id", ""),
        "dialog": turns,
        "calldate": record.get("calldate", ""),
        "custno": record.get("custno", ""),
        "colluserid": record.get("colluserid", ""),
    }


def _call_llm(client: OpenAI, system_prompt: str, user_data: dict,
              max_tokens: int = 8192) -> dict:
    """Calls DeepSeek V4 and returns parsed JSON."""
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
    if response.choices[0].finish_reason == "length":
        print("  Warning: response truncated")
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        raise


# ── Step 1: Programmatic Pre-processing ──────────────────────────

def step1_preprocess(record: dict) -> dict:
    """Normalizes punctuation, fixes known ASR patterns, splits role labels.

    Args:
        record: Dialog record with turns array.

    Returns:
        Pre-processed record.
    """
    turns = record["dialog"]
    fix_count = 0

    for t in turns:
        text = t["text"]

        for cn, en in CN_TO_EN_PUNCT.items():
            text = text.replace(cn, en)

        text = re.sub(r"催收[：:]", "催收员:", text)

        for pattern, replacement in KNOWN_ASR_FIXES:
            new_text = re.sub(pattern, replacement, text)
            if new_text != text:
                fix_count += 1
                text = new_text

        t["text"] = text

    turns = _split_role_labels_in_turns(turns)

    print(f"Step 1: Pre-processed {len(turns)} turns, {fix_count} regex fixes")
    return record


def _split_role_labels_in_turns(turns: list[dict]) -> list[dict]:
    """Splits turns with embedded role labels."""
    result = []
    for t in turns:
        text = t.get("text", "")
        parts = re.split(r"(催收员|客户)[：:]", text)
        if len(parts) <= 1:
            result.append(t)
            continue
        roles_in_text = re.findall(r"(催收员|客户)[：:]", text)
        if parts[0].strip():
            result.append({"role": t["role"], "text": parts[0].strip(),
                           "source": t.get("source", "original")})
        for j, role in enumerate(roles_in_text):
            text_idx = j * 2 + 2
            if text_idx < len(parts) and parts[text_idx].strip():
                result.append({"role": role, "text": parts[text_idx].strip(),
                               "source": t.get("source", "original")})
    return result


# ── Step 2: LLM Identify Structural Issues ───────────────────────

def step2_identify_structure(client: OpenAI, record: dict) -> list[dict]:
    """Asks LLM to identify merge/insert/reorder operations.

    Args:
        client: OpenAI client.
        record: Pre-processed dialog record.

    Returns:
        List of operation dicts from the LLM.
    """
    print("Step 2: LLM identifying structural issues...")
    turns = record["dialog"]
    payload = {"dialog": turns}
    result = _call_llm(client, STRUCTURAL_PROMPT, payload, max_tokens=4096)
    ops = result.get("operations", [])
    merges = sum(1 for o in ops if o.get("type") == "merge")
    inserts = sum(1 for o in ops if o.get("type") == "insert")
    reorders = sum(1 for o in ops if o.get("type") == "reorder")
    print(f"  Operations: {merges} merge, {inserts} insert, {reorders} reorder")
    return ops


# ── Step 3: Apply Structural Changes ─────────────────────────────

def step3_apply_structure(record: dict, operations: list[dict]) -> dict:
    """Applies structural operations programmatically.

    Order: reorder first, then merge, then insert.

    Args:
        record: Dialog record.
        operations: List of operation dicts from step 2.

    Returns:
        Record with structural changes applied.
    """
    print("Step 3: Applying structural changes...")
    turns = deepcopy(record["dialog"])

    reorders = [o for o in operations if o.get("type") == "reorder"]
    merges = [o for o in operations if o.get("type") == "merge"]
    inserts = [o for o in operations if o.get("type") == "insert"]

    reorder_count = _apply_reorders(turns, reorders)
    merge_count, turns = _apply_merges(turns, merges)
    insert_count, turns = _apply_inserts(turns, inserts)

    for i, t in enumerate(turns):
        t["index"] = i

    record["dialog"] = turns
    record["structural_ops"] = {
        "reorders": reorder_count,
        "merges": merge_count,
        "inserts": insert_count,
    }
    print(f"  Applied: {reorder_count} reorder, {merge_count} merge, {insert_count} insert")
    return record


def _apply_reorders(turns: list[dict], reorders: list[dict]) -> int:
    """Applies reorder operations. Returns count of successful reorders."""
    count = 0
    for op in reorders:
        idx = op.get("index")
        target = op.get("move_after_index")
        if idx is None or target is None:
            continue
        match_idx = next((i for i, t in enumerate(turns) if t.get("index") == idx), None)
        match_target = next((i for i, t in enumerate(turns) if t.get("index") == target), None)
        if match_idx is not None and match_target is not None and match_idx != match_target:
            turn = turns.pop(match_idx)
            new_pos = match_target + (0 if match_idx > match_target else 1)
            turns.insert(new_pos, turn)
            count += 1
    return count


def _apply_merges(turns: list[dict], merges: list[dict]) -> tuple[int, list[dict]]:
    """Applies merge operations. Returns (count, new_turns)."""
    if not merges:
        return 0, turns

    indices_to_merge = set()
    for op in merges:
        from_idx = op.get("from_index")
        to_idx = op.get("to_index")
        if from_idx is not None and to_idx is not None:
            for i in range(from_idx, to_idx + 1):
                indices_to_merge.add(i)

    if not indices_to_merge:
        return 0, turns

    result = []
    i = 0
    count = 0
    while i < len(turns):
        if turns[i].get("index") in indices_to_merge:
            merged_text = turns[i]["text"]
            merged_role = turns[i]["role"]
            j = i + 1
            while j < len(turns) and turns[j].get("index") in indices_to_merge:
                if turns[j]["role"] == merged_role:
                    merged_text += ", " + turns[j]["text"]
                    count += 1
                else:
                    result.append(turns[j])
                j += 1
            result.append({"role": merged_role, "text": merged_text,
                           "source": turns[i].get("source", "original")})
            i = j
        else:
            result.append(turns[i])
            i += 1

    return count, result


def _apply_inserts(turns: list[dict], inserts: list[dict]) -> tuple[int, list[dict]]:
    """Applies insert operations. Returns (count, new_turns)."""
    if not inserts:
        return 0, turns

    result = list(turns)
    offset = 0
    count = 0

    for op in sorted(inserts, key=lambda x: x.get("after_index", 0)):
        after_idx = op.get("after_index")
        if after_idx is None:
            continue
        pos = next((i for i, t in enumerate(result) if t.get("index") == after_idx), None)
        if pos is not None:
            new_turn = {
                "role": op.get("role", "客户"),
                "text": op.get("text", "嗯"),
                "source": "ai-generated",
                "confidence": op.get("confidence", "medium"),
            }
            result.insert(pos + 1 + offset, new_turn)
            offset += 1
            count += 1

    return count, result


# ── Step 4: LLM Identify Remaining ASR Errors ────────────────────

def step4_identify_asr(client: OpenAI, record: dict) -> list[dict]:
    """Asks LLM to identify remaining ASR errors.

    Args:
        client: OpenAI client.
        record: Structurally aligned dialog record.

    Returns:
        List of correction dicts from the LLM.
    """
    print("Step 4: LLM identifying remaining ASR errors...")
    turns = record["dialog"]
    payload = {"dialog": turns}
    result = _call_llm(client, ASR_FIX_PROMPT, payload, max_tokens=4096)
    corrections = result.get("corrections", [])
    print(f"  Corrections identified: {len(corrections)}")
    return corrections


# ── Step 5: Apply ASR Corrections ────────────────────────────────

def step5_apply_asr(record: dict, corrections: list[dict]) -> dict:
    """Applies ASR corrections with validation.

    Each correction specifies an index, a "from" substring to find,
    and a "to" replacement. Validates that "from" exists in the turn
    before applying.

    Args:
        record: Dialog record.
        corrections: List of correction dicts from step 4.

    Returns:
        Record with ASR corrections applied.
    """
    print("Step 5: Applying ASR corrections...")
    turns = record["dialog"]
    applied = 0
    failed = 0

    for corr in corrections:
        idx = corr.get("index")
        from_text = corr.get("from", "")
        to_text = corr.get("to", "")

        if idx is None or not from_text:
            failed += 1
            continue

        match = next((t for t in turns if t.get("index") == idx), None)
        if match and from_text in match["text"]:
            match["text"] = match["text"].replace(from_text, to_text, 1)
            applied += 1
        else:
            failed += 1

    record["asr_corrections"] = {"applied": applied, "failed": failed}
    print(f"  Applied: {applied}, Failed (not found): {failed}")
    return record


# ── Step 6: Verify & Safety Net ──────────────────────────────────

def step6_verify(record: dict) -> dict:
    """Re-applies known patterns, re-splits role labels, validates flow.

    Args:
        record: Dialog record after all LLM steps.

    Returns:
        Final verified record.
    """
    print("Step 6: Verify & safety net...")
    turns = record["dialog"]
    fix_count = 0

    for t in turns:
        text = t.get("text", "")
        for pattern, replacement in KNOWN_ASR_FIXES:
            new_text = re.sub(pattern, replacement, text)
            if new_text != text:
                fix_count += 1
                text = new_text
        t["text"] = text

    turns = _split_role_labels_in_turns(turns)

    for i, t in enumerate(turns):
        t["index"] = i

    record["dialog"] = turns

    ai_count = sum(1 for t in turns if t.get("source") == "ai-generated")
    consec = 0
    for i in range(1, len(turns)):
        if turns[i]["role"] == turns[i-1]["role"]:
            if turns[i].get("source") == "original" and turns[i-1].get("source") == "original":
                consec += 1

    print(f"  Safety net fixes: {fix_count}")
    print(f"  Final: {len(turns)} turns, {ai_count} ai-generated, {consec} consecutive same-role")
    return record


# ── Output ───────────────────────────────────────────────────────

def write_output(record: dict) -> None:
    """Writes the corrected record to output.py."""
    output = {
        "call_id": record["call_id"],
        "dialog": [
            {k: v for k, v in t.items() if k != "index"}
            for t in record["dialog"]
        ],
        "calldate": record["calldate"],
        "custno": record["custno"],
        "colluserid": record["colluserid"],
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("corrected_output = ")
        f.write(json.dumps(output, ensure_ascii=False, indent=2))
        f.write("\n")


# ── Main ─────────────────────────────────────────────────────────

def main() -> None:
    """Runs the full pipeline: pre-process → identify → apply → verify."""
    client = create_client()
    record = load_first_record()

    print(f"Input: call_id={record['call_id']}, turns={len(record['dialog'])}")
    print()

    record = step1_preprocess(record)
    print()

    operations = step2_identify_structure(client, record)
    record = step3_apply_structure(record, operations)
    print()

    corrections = step4_identify_asr(client, record)
    record = step5_apply_asr(record, corrections)
    print()

    record = step6_verify(record)
    print()

    write_output(record)
    print(f"Output written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
