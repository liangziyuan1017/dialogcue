import json
import os
import re
from pathlib import Path

from f007_infrastructure.jsonl_utils import load_jsonl, write_jsonl
from f007_infrastructure.logging import get_logger as _get_logger

from f001_schema_alignment.relabel_state import relabel_all as _relabel_all

_log = _get_logger(__name__)


def _load_output_manual():
    data_path = os.path.join(os.path.dirname(__file__), "..", "f000_keyword_discovery", "data", "output_labeled.jsonl")
    return load_jsonl(Path(data_path))


def _load_output_labeled():
    data_path = os.path.join(os.path.dirname(__file__), "..", "f000_keyword_discovery", "data", "output_labeled.jsonl")
    if not os.path.exists(data_path):
        return None
    return {r["call_id"]: r for r in load_jsonl(Path(data_path))}


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
    mapping = {
        "未填": "unknown",
        "高中": "high_school",
        "高中及中专": "high_school",
        "大专": "college",
        "本科": "bachelor",
        "硕士": "master",
        "博士": "phd",
    }
    return mapping.get(str(text).strip(), "other")


def _parse_custInfo(raw):
    if not raw:
        return {}
    try:
        tags = json.loads(raw) if isinstance(raw, str) else raw
        return {t["tagName"]: t.get("tagValue", "") for t in tags if "tagName" in t}
    except (json.JSONDecodeError, TypeError):
        return {}


def _tag(customer_info, *names, default=""):
    """Return first present tag value; supports renamed external tags."""
    for name in names:
        if name in customer_info:
            return customer_info[name]
    return default


def _parse_risk_level(text):
    raw = str(text).strip()
    if raw in {"高", "中高"}:
        return 3
    if raw in {"中", "中低"}:
        return 2
    if raw in {"低"}:
        return 1
    return _parse_int(raw.rstrip("级"))


def _has_social_insurance(text):
    raw = str(text).strip()
    if raw in {"", "未知", "否", "无", "N", "n"}:
        return False
    if raw in {"是", "有", "Y", "y"}:
        return True
    return bool(raw)


def build_context(customer_info, mob_typ):
    business = _tag(customer_info, "经营贷款余额", default="0")
    mortgage = _tag(customer_info, "商业房贷余额", default="0")
    other_loan = _tag(customer_info, "其他贷款余额", default="0")
    wealth = _tag(customer_info, "理财资产时点值", "理财时点值", default="0")
    balance = _tag(customer_info, "账户当前余额", "目前余额", default="0")
    risk = _tag(customer_info, "客户风险等级", "客户风险标识等级", default="0")
    education = _tag(customer_info, "最高学历", "学历", default="")
    repayment = _tag(
        customer_info,
        "近7日还款操作",
        "（掌生APP操作）近7天-还款操作",
        default="",
    )
    proxy = _tag(
        customer_info,
        "高风险代理投诉",
        "持卡用户是否疑似高风险代理投诉",
        default="",
    )
    intermediary = _tag(
        customer_info,
        "代理中介投诉",
        "持卡用户是否疑似代理中介投诉",
        default="",
    )
    social = _tag(
        customer_info,
        "当前社保缴纳状态",
        "持卡人当前是否缴纳社保",
        default="",
    )
    vehicles = _tag(
        customer_info,
        "历史车辆数量",
        "持卡用户名下历史车辆数",
        default="0",
    )
    return {
        "business_loan_balance": _parse_int(business),
        "mortgage_balance": _parse_int(mortgage),
        "other_loan_balance": _parse_int(other_loan),
        "wealth_value": _parse_int(wealth),
        "current_balance": _parse_int(balance),
        "has_business_loan": _parse_int(business) > 0,
        "has_mortgage": _parse_int(mortgage) > 0,
        "has_other_loan": _parse_int(other_loan) > 0,
        "risk_level": _parse_risk_level(risk),
        "complaint_score": _parse_int(_tag(customer_info, "客户投诉评分", default="0")),
        "education": _map_education(education),
        "days_delinquent": _map_days_delinquent(mob_typ),
        "recent_repayment": str(repayment).strip().upper() == "Y",
        "recent_contact_count": _parse_int(_tag(customer_info, "近7日接通次数", default="0")),
        "is_high_risk_proxy_complaint": str(proxy).strip() == "是",
        "is_proxy_intermediary_complaint": str(intermediary).strip() == "是",
        "has_social_insurance": _has_social_insurance(social),
        "vehicle_count": _parse_int(vehicles),
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


def write_output_aligned(output_path=None):
    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), "data", "output_aligned.jsonl")
    aligned = align_all()
    aligned, relabel_stats = _relabel_all(aligned)
    _log.info(f"Relabel stats: {relabel_stats}")
    write_jsonl(Path(output_path), aligned)
    return len(aligned)


if __name__ == "__main__":
    count = write_output_aligned()
    _log.info(f"Wrote {count} aligned records to output_aligned.jsonl")
