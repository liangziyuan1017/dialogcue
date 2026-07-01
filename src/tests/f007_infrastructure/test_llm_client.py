from unittest.mock import MagicMock, patch

from f007_infrastructure.llm_client import call_deepseek, call_deepseek_json


def _mock_client(response_text):
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content=response_text))]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp
    return mock_client


def test_call_deepseek_returns_string():
    with patch("f007_infrastructure.llm_client._get_client", return_value=_mock_client("test response")):
        result = call_deepseek("hello")
        assert isinstance(result, str)
        assert result == "test response"


def test_call_deepseek_json_returns_dict():
    with patch("f007_infrastructure.llm_client._get_client", return_value=_mock_client('{"key": "value"}')):
        result = call_deepseek_json("hello")
        assert isinstance(result, dict)
        assert result["key"] == "value"


def test_call_deepseek_uses_low_temperature():
    mock_client = _mock_client("ok")
    with patch("f007_infrastructure.llm_client._get_client", return_value=mock_client):
        call_deepseek("hello")
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0.1
        assert call_kwargs["model"] == "deepseek-chat"
