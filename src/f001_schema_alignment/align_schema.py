import importlib.util
import json
import os
import re

from f007_infrastructure.logging import get_logger as _get_logger

from f001_schema_alignment.relabel_state import relabel_all as _relabel_all

_log = _get_logger(__name__)


def _load_output_manual():
    data_path = os.path.join(os.path.dirname(__file__), "..", "f000_keyword_discovery", "data", "output_labeled.py")
    spec = importlib.util.spec_from_file_location("output_labeled", data_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.results


def _load_output_labeled():
    data_path = os.path.join(os.path.dirname(__file__), "..", "f000_keyword_discovery", "data", "output_labeled.py")
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


def _parse_custInfo(raw):
    if not raw:
        return {}
    try:
        tags = json.loads(raw) if isinstance(raw, str) else raw
        return {t["tagName"]: t.get("tagValue", "") for t in tags if "tagName" in t}
    except (json.JSONDecodeError, TypeError):
        return {}


def build_context(customer_info, mob_typ):
    return {
        "business_loan_balance": _parse_int(customer_info.get("经营贷款余额", "0")),
        "mortgage_balance": _parse_int(customer_info.get("商业房贷余额", "0")),
        "other_loan_balance": _parse_int(customer_info.get("其他贷款余额", "0")),
        "wealth_value": _parse_int(customer_info.get("理财时点值", "0")),
        "current_balance": _parse_int(customer_info.get("目前余额", "0")),
        "has_business_loan": _parse_int(customer_info.get("经营贷款余额", "0")) > 0,
        "has_mortgage": _parse_int(customer_info.get("商业房贷余额", "0")) > 0,
        "has_other_loan": _parse_int(customer_info.get("其他贷款余额", "0")) > 0,
        "risk_level": _parse_int(customer_info.get("客户风险标识等级", "0")),
        "complaint_score": _parse_int(customer_info.get("客户投诉评分", "0")),
        "education": _map_education(customer_info.get("学历", "")),
        "days_delinquent": _map_days_delinquent(mob_typ),
        "recent_repayment": customer_info.get("（掌生APP操作）近7天-还款操作", "") == "Y",
        "recent_contact_count": _parse_int(customer_info.get("近7日接通次数", "0")),
        "is_high_risk_proxy_complaint": customer_info.get("持卡用户是否疑似高风险代理投诉", "") == "是",
        "is_proxy_intermediary_complaint": customer_info.get("持卡用户是否疑似代理中介投诉", "") == "是",
        "has_social_insurance": bool(customer_info.get("持卡人当前是否缴纳社保", "")),
        "vehicle_count": _parse_int(customer_info.get("持卡用户名下历史车辆数", "0")),
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
    cust_info_dict = _parse_custInfo(record.get("custInfo", ""))
    labeled_dialog = None
    if labeled_lookup is not None:
        labeled_rec = labeled_lookup.get(record["call_id"])
        if labeled_rec is not None:
            labeled_dialog = labeled_rec["response"]["dialog"]
    return {
        "call_id": record["call_id"],
        "cust_no": record.get("cust_no") or record.get("custno", ""),
        "dialDate": record.get("dialDate", ""),
        "connectDate": record.get("connectDate", ""),
        "dialType": record.get("dialType", ""),
        "ringTime": record.get("ringTime", ""),
        "collUserId": record.get("collUserId", ""),
        "collId": record.get("collId", ""),
        "collArea": record.get("collArea", ""),
        "collGroupId": record.get("collGroupId", ""),
        "acNo": record.get("acNo", ""),
        "isRecorded": record.get("isRecorded", ""),
        "result": record.get("result", ""),
        "talkTime": record.get("talkTime", ""),
        "channel": record.get("channel", ""),
        "corpCode": record.get("corpCode", ""),
        "calledNo": record.get("calledNo", ""),
        "mobTyp": record.get("mobTyp", ""),
        "phoneRoute": record.get("phoneRoute", ""),
        "agentTalkTime": record.get("agentTalkTime", ""),
        "custInfo": record.get("custInfo", ""),
        "turns_annotated": build_turns_annotated(dialog, labeled_dialog),
        "reward": None,
        "state_transitions": [],
        "context": build_context(cust_info_dict, record.get("mobTyp", "")),
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
        output_path = os.path.join(os.path.dirname(__file__), "data", "output_aligned.py")
    aligned = align_all()
    aligned, relabel_stats = _relabel_all(aligned)
    _log.info(f"Relabel stats: {relabel_stats}")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("results = ")
        f.write(_python_dumps(aligned))
    return len(aligned)


if __name__ == "__main__":
    count = write_output_aligned()
    _log.info(f"Wrote {count} aligned records to output_aligned.py")
