from f009_api_server.tag_mapping import map_cust_tags_to_context


def test_auto_loan_positive():
    result = map_cust_tags_to_context([{"tag": "经营贷款余额", "value": "5000.0"}])
    assert result["has_auto_loan"] is True


def test_auto_loan_zero():
    result = map_cust_tags_to_context([{"tag": "经营贷款余额", "value": "0.0"}])
    assert result["has_auto_loan"] is False


def test_mortgage_positive():
    result = map_cust_tags_to_context([{"tag": "商业房贷余额", "value": "100000"}])
    assert result["has_mortgage"] is True


def test_social_insurance_yes():
    result = map_cust_tags_to_context([{"tag": "持卡人当前是否缴纳社保", "value": "是"}])
    assert result["social_insurance_stable"] is True


def test_social_insurance_no():
    result = map_cust_tags_to_context([{"tag": "持卡人当前是否缴纳社保", "value": "否"}])
    assert result["social_insurance_stable"] is False


def test_credit_rating_good():
    result = map_cust_tags_to_context([{"tag": "客户风险标识等级", "value": "1级"}])
    assert result["credit_rating_good"] is True


def test_credit_rating_bad():
    result = map_cust_tags_to_context([{"tag": "客户风险标识等级", "value": "3级"}])
    assert result["credit_rating_good"] is False


def test_complaint_high_risk():
    result = map_cust_tags_to_context([{"tag": "持卡用户是否疑似高风险代理投诉", "value": "是"}])
    assert result["has_complaint_history"] is True


def test_complaint_agent():
    result = map_cust_tags_to_context([{"tag": "持卡用户是否疑似代理中介投诉", "value": "是"}])
    assert result["has_complaint_history"] is True


def test_complaint_both_or_together():
    result = map_cust_tags_to_context([
        {"tag": "持卡用户是否疑似高风险代理投诉", "value": "是"},
        {"tag": "持卡用户是否疑似代理中介投诉", "value": "是"},
    ])
    assert result["has_complaint_history"] is True


def test_complaint_neither():
    result = map_cust_tags_to_context([{"tag": "持卡用户是否疑似高风险代理投诉", "value": "否"}])
    assert result["has_complaint_history"] is False


def test_unknown_tag_ignored():
    result = map_cust_tags_to_context([{"tag": "未知标签", "value": "whatever"}])
    assert result == {}


def test_empty_list():
    result = map_cust_tags_to_context([])
    assert result == {}


def test_multiple_tags():
    result = map_cust_tags_to_context([
        {"tag": "经营贷款余额", "value": "5000"},
        {"tag": "客户风险标识等级", "value": "2级"},
    ])
    assert result["has_auto_loan"] is True
    assert result["credit_rating_good"] is True
