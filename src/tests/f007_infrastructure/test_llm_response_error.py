from unittest.mock import MagicMock, patch

import pytest

from f007_infrastructure.llm_client import LLMResponseError, call_deepseek_json


def _mock_client(response_text):
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content=response_text))]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp
    return mock_client


def test_malformed_json_raises_llm_response_error():
    with patch("f007_infrastructure.llm_client._get_client", return_value=_mock_client("this is not json at all")):
        with pytest.raises(LLMResponseError) as exc:
            call_deepseek_json("hello")
    assert exc.value.raw_text == "this is not json at all"


def test_llm_response_error_carries_raw_text():
    raw = "```json\n{broken\n```"
    with patch("f007_infrastructure.llm_client._get_client", return_value=_mock_client(raw)):
        with pytest.raises(LLMResponseError) as exc:
            call_deepseek_json("hello")
    assert exc.value.raw_text == raw


def test_llm_response_error_is_value_error_subclass():
    assert issubclass(LLMResponseError, ValueError)


def test_extract_state_falls_back_to_keyword_on_llm_error():
    from f008_state_extraction.state_extraction import extract_state

    taxonomy = {"facts": [], "emotions": [], "collector_actions": []}
    mock_db = MagicMock()
    mock_db.taxonomy_keyword_search.return_value = []

    with patch("f008_state_extraction.state_extraction.extract_state_llm", side_effect=LLMResponseError("bad", "raw")):
        result = extract_state("test utterance", taxonomy, db=mock_db)

    assert result["method"] == "keyword"
