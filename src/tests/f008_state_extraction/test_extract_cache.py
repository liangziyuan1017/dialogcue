import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from f008_state_extraction import state_extraction as se


@pytest.fixture(autouse=True)
def reset_cache():
    se._extract_cache.clear()
    se._taxonomy_version = 0
    yield
    se._extract_cache.clear()
    se._taxonomy_version = 0


@pytest.mark.asyncio
async def test_repeated_utterance_uses_cache():
    llm_calls = []

    def fake_llm(utterance, taxonomy):
        llm_calls.append(utterance)
        return {"facts": ["financial_hardship"], "emotions": [], "actions": [], "confidence": 0.9, "method": "llm"}

    with patch.object(se, "extract_state_llm", side_effect=fake_llm), \
         patch.object(se, "extract_state_keyword", new_callable=AsyncMock, return_value={"facts": [], "emotions": [], "actions": [], "confidence": 0.1, "method": "keyword"}), \
         patch.object(se, "_apply_relabel", lambda r: None):
        r1 = await se.extract_state("我现在没钱还", {"facts": [], "emotions": [], "collector_actions": []})
        r2 = await se.extract_state("我现在没钱还", {"facts": [], "emotions": [], "collector_actions": []})

    assert len(llm_calls) == 1
    assert r1 == r2


@pytest.mark.asyncio
async def test_different_utterance_bypasses_cache():
    llm_calls = []

    def fake_llm(utterance, taxonomy):
        llm_calls.append(utterance)
        return {"facts": [], "emotions": [], "actions": [], "confidence": 0.5, "method": "llm"}

    with patch.object(se, "extract_state_llm", side_effect=fake_llm), \
         patch.object(se, "extract_state_keyword", new_callable=AsyncMock, return_value={"facts": [], "emotions": [], "actions": [], "confidence": 0.1, "method": "keyword"}), \
         patch.object(se, "_apply_relabel", lambda r: None):
        await se.extract_state("utterance A", {"facts": [], "emotions": [], "collector_actions": []})
        await se.extract_state("utterance B", {"facts": [], "emotions": [], "collector_actions": []})

    assert len(llm_calls) == 2


@pytest.mark.asyncio
async def test_taxonomy_version_change_invalidates_cache():
    llm_calls = []

    def fake_llm(utterance, taxonomy):
        llm_calls.append(utterance)
        return {"facts": [], "emotions": [], "actions": [], "confidence": 0.5, "method": "llm"}

    with patch.object(se, "extract_state_llm", side_effect=fake_llm), \
         patch.object(se, "extract_state_keyword", new_callable=AsyncMock, return_value={"facts": [], "emotions": [], "actions": [], "confidence": 0.1, "method": "keyword"}), \
         patch.object(se, "_apply_relabel", lambda r: None):
        await se.extract_state("same utterance", {"facts": [], "emotions": [], "collector_actions": []})
        se.invalidate_extract_cache()
        await se.extract_state("same utterance", {"facts": [], "emotions": [], "collector_actions": []})

    assert len(llm_calls) == 2
