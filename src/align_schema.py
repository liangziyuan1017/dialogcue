import importlib.util
import json
import os
import re


def _load_output_manual():
    data_path = os.path.join(os.path.dirname(__file__), "..", "data", "output_manual.py")
    spec = importlib.util.spec_from_file_location("output_manual", data_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.results


def _load_output_labeled():
    data_path = os.path.join(os.path.dirname(__file__), "output_labeled.py")
    if not os.path.exists(data_path):
        data_path = os.path.join(os.path.dirname(__file__), "..", "data", "output_labeled.py")
    if not os.path.exists(data_path):
        return None
    spec = importlib.util.spec_from_file_location("output_labeled", data_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {r["call_id"]: r for r in mod.results}


def _parse_int(text):
    digits = re.sub(r"[^\d]", "", str(text))
    return int(digits) if digits else 0


def _parse_bool_has(text, pattern):
    return pattern in str(text)


def _map_credit_rating(raw):
    first = raw[0] if raw else "0"
    mapping = {"Z": "good", "B": "moderate", "2": "moderate", "3": "moderate", "0": "bad"}
    return mapping.get(first, "unknown")


def _map_days_delinquent(mob_typ):
    mapping = {"M1": 30, "M2": 60, "M3": 90, "M4": 120, "M5": 150, "M6": 180}
    return mapping.get(mob_typ, 0)


def _parse_available_plans(text):
    plans = []
    if "调减" in text:
        plans.append("reduction")
    if "MINA" in text:
        plans.append("mina")
    if "分期" in text:
        plans.append("installment")
    return plans


def _parse_external_debt(text):
    match = re.search(r"总余额(\d+)", text)
    return int(match.group(1)) if match else 0


def _parse_percentage(text):
    match = re.search(r"(\d+)%", str(text))
    return float(match.group(1)) / 100.0 if match else 0.0


def _parse_external_debt_institutions(text):
    match = re.search(r"共(\d+)家", str(text))
    return int(match.group(1)) if match else 0


def _map_education(text):
    mapping = {"未填": "unknown", "高中": "high_school", "大专": "college", "本科": "bachelor", "硕士": "master", "博士": "phd"}
    return mapping.get(str(text).strip(), "other")


def build_context(customer_info, mob_typ):
    return {
        "has_auto_loan": _parse_bool_has(customer_info.get("他行是否有车贷", ""), "有车贷")
        or _parse_bool_has(customer_info.get("我行是否有车贷", ""), "有车贷"),
        "has_mortgage": _parse_bool_has(customer_info.get("他行是否有房贷", ""), "有房贷")
        or _parse_bool_has(customer_info.get("我行是否有房贷", ""), "有房贷"),
        "credit_rating": _map_credit_rating(customer_info.get("24期缴款评等", "")),
        "days_delinquent": _map_days_delinquent(mob_typ),
        "total_debt": _parse_int(customer_info.get("总欠款", "0")),
        "external_debt": _parse_external_debt(customer_info.get("外部欠款金额", "")),
        "has_negotiation_history": customer_info.get("历史协商情况", "") != "无协商历史",
        "available_plans": _parse_available_plans(customer_info.get("当前可使用的协商方案", "")),
        "social_insurance_stable": "有社保" in customer_info.get("社保缴纳情况", "")
        and "灵活就业" not in customer_info.get("社保缴纳情况", ""),
        "card_restricted": customer_info.get("是否管制", "") != "可正常使用卡片",
        "is_cash_out_customer": customer_info.get("是否为套现客户", "") != "非套现客户",
        "external_debt_institutions": _parse_external_debt_institutions(customer_info.get("外部共债机构数", "")),
        "interest_ratio": _parse_percentage(customer_info.get("利息占欠款比例", "0%")),
        "installment_ratio": _parse_percentage(customer_info.get("分期金额占欠款比例", "0%")),
        "age": _parse_int(customer_info.get("年龄", "0")),
        "gender": customer_info.get("性别", ""),
        "education": _map_education(customer_info.get("学历", "")),
        "industry": customer_info.get("行业", ""),
        "has_complaint_history": "没有" not in customer_info.get("历史投诉情况", "没有"),
        "has_legal_tools": customer_info.get("当前可使用的法务工具", "") != "无可用的法务工具",
        "is_negotiation_brain_customer": customer_info.get("是否谈判大脑客户", "") == "Y",
    }


def build_turns_annotated(dialog, labeled_dialog=None):
    turns = []
    for i, turn in enumerate(dialog):
        entry = {
            "turn_index": i,
            "role": turn["role"],
            "text": turn["text"],
        }
        if labeled_dialog is not None and i < len(labeled_dialog):
            if "state" in labeled_dialog[i]:
                entry["state"] = labeled_dialog[i]["state"]
        turns.append(entry)
    return turns


def align_record(record, labeled_lookup=None):
    dialog = record["response"]["dialog"]
    customer_info = record.get("customer_info", {})
    labeled_dialog = None
    if labeled_lookup is not None:
        labeled_rec = labeled_lookup.get(record["call_id"])
        if labeled_rec is not None:
            labeled_dialog = labeled_rec["response"]["dialog"]
    return {
        "call_id": record["call_id"],
        "cust_no": record.get("cust_no") or record.get("custno", ""),
        "call_date": record.get("call_date", ""),
        "coll_user_id": record.get("coll_user_id", ""),
        "mob_typ": record.get("mob_typ", ""),
        "talk_time": record.get("talk_time", ""),
        "plan_evaluation": record.get("plan_evaluation", ""),
        "customer_info": customer_info,
        "turns_annotated": build_turns_annotated(dialog, labeled_dialog),
        "reward": None,
        "state_transitions": [],
        "context": build_context(customer_info, record.get("mob_typ", "")),
    }


def align_all(records=None):
    if records is None:
        records = _load_output_manual()
    labeled_lookup = _load_output_labeled()
    return [align_record(r, labeled_lookup) for r in records]


def _python_dumps(obj, indent=2):
    text = json.dumps(obj, indent=indent, ensure_ascii=False)
    text = text.replace(": null", ": None")
    text = text.replace(": true", ": True")
    text = text.replace(": false", ": False")
    return text


def write_output_aligned(output_path=None):
    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), "output_aligned.py")
    aligned = align_all()
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("results = ")
        f.write(_python_dumps(aligned))
    return len(aligned)


if __name__ == "__main__":
    count = write_output_aligned()
    print(f"Wrote {count} aligned records to output_aligned.py")
