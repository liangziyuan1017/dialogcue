"""Tag mapping: external cust_tags → internal context bitmask fields.

F014 — pure function used by POST /api/v1/session/start to convert the
external system's customer tags into the internal BITMASK_FIELDS context.
"""

_TAG_MAP = {
    "经营贷款余额": ("has_business_loan", "float_positive"),
    "商业房贷余额": ("has_mortgage", "float_positive"),
    "其他贷款余额": ("has_other_loan", "float_positive"),
    "持卡人当前是否缴纳社保": ("has_social_insurance", "is_yes"),
    "客户风险标识等级": ("has_risk_flag", "risk_level_positive"),
    "持卡用户是否疑似高风险代理投诉": ("is_high_risk_proxy_complaint", "is_yes"),
    "持卡用户是否疑似代理中介投诉": ("is_proxy_intermediary_complaint", "is_yes"),
    "（掌生APP操作）近7天-还款操作": ("recent_repayment", "is_yes_n"),
    "持卡用户名下历史车辆数": ("has_vehicle", "int_positive"),
    "学历": ("education", "passthrough"),
    "目前余额": ("current_balance", "passthrough"),
    "理财时点值": ("wealth_value", "passthrough"),
    "近7日接通次数": ("recent_contact_count", "passthrough"),
}


def _float_positive(value: str) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _is_yes(value: str) -> bool:
    return str(value).strip() == "是"


def _is_yes_n(value: str) -> bool:
    return str(value).strip().upper() == "Y"


def _risk_level_positive(value: str) -> bool:
    try:
        return int(str(value).strip().rstrip("级")) > 0
    except (TypeError, ValueError):
        return False


def _int_positive(value: str) -> bool:
    try:
        return int(float(value)) > 0
    except (TypeError, ValueError):
        return False


def _passthrough(value: str) -> str:
    return str(value).strip()


_INTERPRETERS = {
    "float_positive": _float_positive,
    "is_yes": _is_yes,
    "is_yes_n": _is_yes_n,
    "risk_level_positive": _risk_level_positive,
    "int_positive": _int_positive,
    "passthrough": _passthrough,
}


def map_cust_tags_to_context(cust_tags: list[dict]) -> dict:
    result: dict[str, bool] = {}
    for item in cust_tags:
        tag = item.get("tag", "")
        value = item.get("value", "")
        if tag not in _TAG_MAP:
            continue
        field, interpreter_name = _TAG_MAP[tag]
        interpreter = _INTERPRETERS[interpreter_name]
        if field in result:
            result[field] = result[field] or interpreter(value)
        else:
            result[field] = interpreter(value)
    return result
