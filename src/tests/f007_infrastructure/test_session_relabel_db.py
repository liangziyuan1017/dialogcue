from unittest.mock import AsyncMock, MagicMock

import pytest

from f007_infrastructure.async_db import AsyncSentenceDB


@pytest.mark.asyncio
async def test_save_session_calls_upsert():
    db = MagicMock(spec=AsyncSentenceDB)
    db.save_session = AsyncMock()
    await db.save_session("sess_1", "cust_1", {"a": 1}, {"branch_key": {}})
    db.save_session.assert_awaited_once()


@pytest.mark.asyncio
async def test_append_transcript_turn_calls_insert():
    db = MagicMock(spec=AsyncSentenceDB)
    db.append_transcript_turn = AsyncMock()
    await db.append_transcript_turn("sess_1", 0, "customer", "hi", {"rec": "x"})
    db.append_transcript_turn.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_and_load_relabel_mapping():
    db = MagicMock(spec=AsyncSentenceDB)
    db.save_relabel_mapping = AsyncMock()
    db.load_relabel_map_from_db = AsyncMock(return_value={"tag_a": "canonical_a"})
    await db.save_relabel_mapping("facts", "tag_a", "canonical_a")
    result = await db.load_relabel_map_from_db("facts")
    assert result == {"tag_a": "canonical_a"}
