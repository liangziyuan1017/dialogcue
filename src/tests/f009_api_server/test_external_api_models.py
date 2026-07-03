import pytest
from pydantic import ValidationError

from f009_api_server.server import ExternalRecommendRequest, ExternalSessionStartRequest


def test_session_start_request_valid():
    req = ExternalSessionStartRequest(
        call_id="call_123",
        call_info={},
        agent={},
        customer={"cust_no": "c1", "ac_no": "a1", "called_no": "123"},
        cust_tags=[{"tag": "经营贷款余额", "value": "5000"}],
    )
    assert req.call_id == "call_123"
    assert req.customer.ac_no == "a1"
    assert req.customer.called_no == "123"


def test_session_start_request_missing_call_id():
    with pytest.raises(ValidationError):
        ExternalSessionStartRequest(
            call_info={},
            agent={},
            customer={},
            cust_tags=[],
        )


def test_recommend_request_valid():
    req = ExternalRecommendRequest(
        call_id="call_123",
        current_text="客户说话内容",
        history_context=["之前的话"],
    )
    assert req.call_id == "call_123"
    assert req.current_text == "客户说话内容"


def test_recommend_request_missing_current_text():
    with pytest.raises(ValidationError):
        ExternalRecommendRequest(call_id="call_123")


def test_recommend_request_missing_call_id():
    with pytest.raises(ValidationError):
        ExternalRecommendRequest(current_text="text")


def test_recommend_request_oversize_current_text():
    with pytest.raises(ValidationError):
        ExternalRecommendRequest(call_id="call_1", current_text="x" * 10000)
