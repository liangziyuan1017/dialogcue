from f009_api_server.tag_mapping import map_cust_tags_to_context


def test_business_loan_positive():
    result = map_cust_tags_to_context([{"tag": "经营贷款余额", "value": "5000.0"}])
    assert result["has_business_loan"] is True


def test_business_loan_zero():
    result = map_cust_tags_to_context([{"tag": "经营贷款余额", "value": "0.0"}])
    assert result["has_business_loan"] is False


def test_mortgage_positive():
    result = map_cust_tags_to_context([{"tag": "商业房贷余额", "value": "100000"}])
    assert result["has_mortgage"] is True


def test_other_loan_positive():
    result = map_cust_tags_to_context([{"tag": "其他贷款余额", "value": "50000"}])
    assert result["has_other_loan"] is True


def test_social_insurance_yes():
    result = map_cust_tags_to_context([{"tag": "持卡人当前是否缴纳社保", "value": "是"}])
    assert result["has_social_insurance"] is True


def test_social_insurance_no():
    result = map_cust_tags_to_context([{"tag": "持卡人当前是否缴纳社保", "value": "否"}])
    assert result["has_social_insurance"] is False


def test_risk_flag_positive():
    result = map_cust_tags_to_context([{"tag": "客户风险标识等级", "value": "3级"}])
    assert result["has_risk_flag"] is True


def test_risk_flag_zero():
    result = map_cust_tags_to_context([{"tag": "客户风险标识等级", "value": "0级"}])
    assert result["has_risk_flag"] is False


def test_high_risk_complaint():
    result = map_cust_tags_to_context([{"tag": "持卡用户是否疑似高风险代理投诉", "value": "是"}])
    assert result["is_high_risk_proxy_complaint"] is True


def test_agent_complaint():
    result = map_cust_tags_to_context([{"tag": "持卡用户是否疑似代理中介投诉", "value": "是"}])
    assert result["is_proxy_intermediary_complaint"] is True


def test_complaint_neither():
    result = map_cust_tags_to_context([{"tag": "持卡用户是否疑似高风险代理投诉", "value": "否"}])
    assert result["is_high_risk_proxy_complaint"] is False


def test_recent_repayment_yes():
    result = map_cust_tags_to_context([{"tag": "（掌生APP操作）近7天-还款操作", "value": "Y"}])
    assert result["recent_repayment"] is True


def test_recent_repayment_no():
    result = map_cust_tags_to_context([{"tag": "（掌生APP操作）近7天-还款操作", "value": "N"}])
    assert result["recent_repayment"] is False


def test_has_vehicle_positive():
    result = map_cust_tags_to_context([{"tag": "持卡用户名下历史车辆数", "value": "2"}])
    assert result["has_vehicle"] is True


def test_has_vehicle_zero():
    result = map_cust_tags_to_context([{"tag": "持卡用户名下历史车辆数", "value": "0"}])
    assert result["has_vehicle"] is False


def test_education_passthrough():
    result = map_cust_tags_to_context([{"tag": "学历", "value": "大专"}])
    assert result["education"] == "大专"


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
    assert result["has_business_loan"] is True
    assert result["has_risk_flag"] is True
