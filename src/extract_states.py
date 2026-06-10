import importlib.util
import json
import os
import time

from llm_client import call_deepseek_json


def build_taxonomy_index(taxonomy):
    return {
        "fact_groups": [
            {"group_name": g["group_name"], "keywords": g["keywords"]}
            for g in taxonomy["facts"]
        ],
        "emotion_groups": [
            {"group_name": g["group_name"], "keywords": g["keywords"]}
            for g in taxonomy["emotions"]
        ],
        "willingness_levels": [
            {"level": w["level"], "definition": w["definition"]}
            for w in taxonomy["willingness_levels"]
        ],
        "collector_action_groups": [
            {"group_name": g["group_name"], "keywords": g["keywords"]}
            for g in taxonomy["collector_actions"]
            if g.get("group_name") is not None
        ],
    }


def build_customer_prompt(turn_text, taxonomy_index):
    fact_names = [g["group_name"] for g in taxonomy_index["fact_groups"]]
    emotion_names = [g["group_name"] for g in taxonomy_index["emotion_groups"]]
    willingness_names = [w["level"] for w in taxonomy_index["willingness_levels"]]
    willingness_defs = "\n".join(
        f"- {w['level']}: {w['definition']}" for w in taxonomy_index["willingness_levels"]
    )
    return f"""你是一个催收对话分析专家。请分析以下客户（债务人）的发言，提取其状态关键词。

客户发言：{turn_text}

可选的事实标签：{', '.join(fact_names)}
可选的情绪标签：{', '.join(emotion_names)}
可选的意愿等级：
{willingness_defs}

请以JSON格式输出：
{{
  "facts": ["一个或多个事实标签"],
  "emotions": ["一个或多个情绪标签"],
  "willingness": "一个意愿等级"
}}

要求：
- facts至少选一个标签
- emotions至少选一个标签
- willingness必须从可选等级中选一个
- 如果发言太短或信息不足，选择最接近的标签"""


def build_collector_prompt(turn_text, taxonomy_index):
    action_names = [g["group_name"] for g in taxonomy_index["collector_action_groups"]]
    return f"""你是一个催收对话分析专家。请分析以下催收员的发言，提取其动作类型。

催收员发言：{turn_text}

可选的动作类型：{', '.join(action_names)}

请以JSON格式输出：
{{
  "action_type": "一个动作类型"
}}

要求：
- action_type必须从可选类型中选一个
- 选择最匹配该发言的动作类型"""


def extract_turn_state(turn, taxonomy_index):
    text = turn["text"]
    if turn["role"] == "客户":
        prompt = build_customer_prompt(text, taxonomy_index)
        result = call_deepseek_json(prompt)
        return {
            "facts": result.get("facts", []),
            "emotions": result.get("emotions", []),
            "willingness": result.get("willingness", "Ambivalent"),
        }
    else:
        prompt = build_collector_prompt(text, taxonomy_index)
        result = call_deepseek_json(prompt)
        return {"action_type": result.get("action_type", "information")}


def _normalize_labeled_state(turn):
    state = turn["state"]
    if turn["role"] == "催收员":
        if "action" in state and "action_type" not in state:
            state["action_type"] = state.pop("action")
        if "action_text" not in state:
            state["action_text"] = turn["text"]
    else:
        if "emotions" not in state:
            state["emotions"] = []
        if "facts" not in state:
            state["facts"] = []
        if "willingness" not in state:
            state["willingness"] = "Ambivalent"
        w = state["willingness"]
        if w in ("strong", "conditional", "weak"):
            mapping = {"strong": "Cooperative", "conditional": "Ambivalent", "weak": "Resistant"}
            state["willingness"] = mapping.get(w, "Ambivalent")


def extract_all_states(records, taxonomy_index, delay=0.5):
    total = sum(len(r["turns_annotated"]) for r in records)
    processed = 0
    for record in records:
        for turn in record["turns_annotated"]:
            if "state" in turn and turn["state"]:
                _normalize_labeled_state(turn)
                turn["labeled"] = True
                continue
            state = extract_turn_state(turn, taxonomy_index)
            if turn["role"] == "催收员":
                state["action_text"] = turn["text"]
            turn["state"] = state
            processed += 1
            if processed % 50 == 0:
                print(f"  {processed} turns processed...")
            if delay > 0:
                time.sleep(delay)
    if processed > 0:
        print(f"  {processed} turns processed (total)")
    return records


def write_output_states(records, output_path):
    lines = ["results = ["]
    for rec in records:
        lines.append("  " + repr(rec) + ",")
    lines.append("]")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _load_aligned():
    src_dir = os.path.dirname(__file__)
    path = os.path.join(src_dir, "output_aligned.py")
    spec = importlib.util.spec_from_file_location("output_aligned", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.results


def _load_taxonomy():
    src_dir = os.path.dirname(__file__)
    path = os.path.join(src_dir, "state_keywords.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(output_path=None):
    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), "output_states.py")
    records = _load_aligned()
    taxonomy = _load_taxonomy()
    index = build_taxonomy_index(taxonomy)
    extract_all_states(records, index)
    write_output_states(records, output_path)
    total = sum(len(r["turns_annotated"]) for r in records)
    annotated = sum(
        1 for r in records for t in r["turns_annotated"] if "state" in t and t["state"]
    )
    print(f"Wrote {len(records)} records, {annotated}/{total} turns annotated to {output_path}")


if __name__ == "__main__":
    main()
