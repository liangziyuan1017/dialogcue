"""Dialog correction via DeepSeek LLM.

Loads the ASR correction prompt and the first dialog record from
(basic) data_0520.json, sends them to DeepSeek V4 via the OpenAI
compatible API, and writes the corrected output to output.py.
"""

import json
import os
import sys
from pathlib import Path

from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "(basic) data_0520.json"
OUTPUT_FILE = BASE_DIR / "output.py"

ASR_PROMPT = """
你是中文催收通话 ASR 转写校正专家。

任务：
对招商银行信用卡催收通话 ASR 文本进行最小必要校正，恢复真实对话。

核心原则：
- 只修正 ASR 错误
- 不润色
- 不改写
- 不总结
- 不补充事实
- 保留真实口语状态

必须保留：
- 口吃、犹豫、重复
- 情绪表达
- 口语化表达
- 语气词
- 不完整句子

例如：
"嗯""呃""对对对""我我现在没办法""唉压力很大"

需要修正：
- 同音/近音错误
- 粘连识别
- 截断识别
- 数字误识别
- 角色标签误入正文

常见ASR错误模式：

| 错误转写 | 正确文本 | 错误类型 |
|---------|---------|---------|
| 诊端部门 | 前端部门 | 近音误识别 |
| 寄收 | 催收 | 近音误识别 |
| 刑专员 | 行专员 | 近音误识别 |
| 书证 | 书面证明 / 协商凭证 | 近音误识别 |
| 全额销售 | 全额催收 | 近音误识别 |
| 标红即前转转 | 标红，即将转 | 语音粘连误识别 |
| 停卡审务 | 停卡审核 | 近音误识别 |
| 收员： | 催收员： | 角色标签截断 |
| 诊端 | 前端 | 近音误识别 |
| 预预散件 | 预审件 | 语音粘连误识别 |
| 法派成序 | 法派程序 | 近音误识别 |
| 法败 | 法院判决 | 语音截断误识别 |
| 盖解封封利 | 和解封封利 | 近音误识别 |
| 102.钟 | 10点钟 | 符号误识别 |
| 1000千292 | 一千二百九十二 | 数字格式混乱 |
| 9毛一 | 9毛1 | 口语数字格式 |
| 这理 | 这里 | 近音误识别 |
| 协商商 | 协商 | 重复误识别 |
| 案件件 | 案件 | 重复误识别 |
| 这这个 | 这个 | 重复误识别 |

请根据上下文语义判断并修正所有ASR转写错误，不仅是上表所列的已知模式。

角色规则：
若正文中出现"催收员："或"客户："，判断是否为真实角色切换：
- 是：拆分轮次
- 否：移除标签

轮次规则：
连续同角色时：
- 若明显属于一句话被切断，则合并
- 若属于正常连续表达，则保留
- 仅在高度合理时补短回应

允许补充的回应仅限：
"嗯""好""对""是""知道了"等短确认。

禁止补充：
- 金额
- 承诺
- 还款计划
- 时间
- 法律态度
- 任何事实信息

宁可缺失，不要臆造。

输出要求：
- 输出合法 JSON
- 不输出解释
- 不输出 markdown

输入：
{
  "call_id": "通话ID",
  "dialog": "催收员:...;客户:...",
  "calldate": "通话日期",
  "custno": "客户编号",
  "colluserid": "催收员工号"
}

输出：
{
  "call_id": "原通话ID",
  "dialog": [
    {
      "role": "催收员|客户",
      "text": "校正后文本",
      "source": "original"
    },
    {
      "role": "催收员|客户",
      "text": "推测的回应内容",
      "source": "ai-generated",
      "confidence": "low|medium|high"
    }
  ],
  "calldate": "原通话日期",
  "custno": "原客户编号",
  "colluserid": "原催收员工号",
  "correction_notes": ["修正说明1", "修正说明2"]
}

规则：
- confidence 仅 ai-generated 时出现
- correction_notes 仅记录关键修正
- 最大目标：恢复真实通话，而不是生成通顺文本
"""


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

    Returns:
        Dictionary with call_id, dialog, calldate, custno, colluserid.
    """
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    record = data[0]
    return {
        "call_id": record.get("call_id", ""),
        "dialog": record.get("dialog", ""),
        "calldate": record.get("calldate", ""),
        "custno": record.get("custno", ""),
        "colluserid": record.get("colluserid", ""),
    }


def correct_dialog(client: OpenAI, record: dict) -> dict:
    """Sends a dialog record to DeepSeek V4 for ASR correction.

    Args:
        client: OpenAI client configured for DeepSeek.
        record: Dialog record dict with call_id, dialog, etc.

    Returns:
        Corrected dialog as a parsed JSON dict from the LLM response.
    """
    user_message = json.dumps(record, ensure_ascii=False)

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": ASR_PROMPT.strip()},
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,
        max_tokens=16384,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    finish_reason = response.choices[0].finish_reason

    if finish_reason == "length":
        print(f"Warning: response truncated (finish_reason=length)")
        print(f"Response length: {len(content)} chars")

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"Raw response (last 500 chars): ...{content[-500:]}")
        raise


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
    """Main entry point: load data, call LLM, write corrected output."""
    client = create_client()
    record = load_first_record()

    print(f"Input call_id: {record['call_id']}")
    print(f"Input dialog length: {len(record['dialog'])} chars")
    print("Calling DeepSeek V4 for correction...")
    print()

    result = correct_dialog(client, record)

    write_output(result)

    print(f"Corrected output written to {OUTPUT_FILE}")
    print(f"  Turns: {len(result.get('dialog', []))}")
    notes = result.get("correction_notes", [])
    print(f"  Corrections: {len(notes)}")
    if notes:
        for note in notes[:10]:
            print(f"    - {note}")
        if len(notes) > 10:
            print(f"    ... and {len(notes) - 10} more")


if __name__ == "__main__":
    main()
