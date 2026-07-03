"""Tag mapping: external cust_tags → internal context bitmask fields.

F014 — pure function used by POST /api/v1/session/start to convert the
external system's customer tags into the internal BITMASK_FIELDS context.
"""

_TAG_MAP = {
    "经营贷款余额": ("has_auto_loan", "float_positive"),
    "商业房贷余额": ("has_mortgage", "float_positive"),
    "持卡人当前是否缴纳社保": ("social_insurance_stable", "is_yes"),
    "客户风险标识等级": ("credit_rating_good", "credit_rating"),
    "持卡用户是否疑似高风险代理投诉": ("has_complaint_history", "is_yes"),
    "持卡用户是否疑似代理中介投诉": ("has_complaint_history", "is_yes"),
}


def _float_positive(value: str) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _is_yes(value: str) -> bool:
    return str(value).strip() == "是"


def _credit_rating(value: str) -> bool:
    return str(value).strip() in ("1级", "2级")


_INTERPRETERS = {
    "float_positive": _float_positive,
    "is_yes": _is_yes,
    "credit_rating": _credit_rating,
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
