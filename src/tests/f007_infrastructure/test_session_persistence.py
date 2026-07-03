import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from f007_infrastructure.async_db import AsyncSentenceDB


class _AsyncCtxMgr:
    def __init__(self, value):
        self._value = value

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, *args):
        pass


class _FakeRecord(dict):
    pass


def _make_mock_pool():
    conn = AsyncMock()
    pool = MagicMock()
    pool.acquire.return_value = _AsyncCtxMgr(conn)
    pool.close = AsyncMock()
    return pool, conn


class TestPing:
    @pytest.mark.asyncio
    async def test_ping_returns_true_when_connected(self):
        pool, conn = _make_mock_pool()
        conn.fetchval.return_value = 1
        db = AsyncSentenceDB("dsn")
        db._pool = pool
        assert await db.ping() is True

    @pytest.mark.asyncio
    async def test_ping_raises_when_not_connected(self):
        db = AsyncSentenceDB("dsn")
        with pytest.raises(RuntimeError):
            await db.ping()


class TestLoadTranscriptTurns:
    @pytest.mark.asyncio
    async def test_returns_turns_ordered_with_extra_merged(self):
        pool, conn = _make_mock_pool()
        conn.fetch.return_value = [
            _FakeRecord(turn_index=1, role="customer", utterance="hi", extra=json.dumps({"recommendation": {"script_id": "s1"}})),
            _FakeRecord(turn_index=2, role="collector", utterance="ok", extra=json.dumps({"extracted_actions": ["empathy"]})),
        ]
        db = AsyncSentenceDB("dsn")
        db._pool = pool
        turns = await db.load_transcript_turns("sess_1")
        assert len(turns) == 2
        assert turns[0]["turn"] == 1
        assert turns[0]["role"] == "customer"
        assert turns[0]["utterance"] == "hi"
        assert turns[0]["recommendation"]["script_id"] == "s1"
        assert turns[1]["turn"] == 2
        assert turns[1]["extracted_actions"] == ["empathy"]

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_no_turns(self):
        pool, conn = _make_mock_pool()
        conn.fetch.return_value = []
        db = AsyncSentenceDB("dsn")
        db._pool = pool
        turns = await db.load_transcript_turns("sess_empty")
        assert turns == []

    @pytest.mark.asyncio
    async def test_handles_null_extra(self):
        pool, conn = _make_mock_pool()
        conn.fetch.return_value = [
            _FakeRecord(turn_index=1, role="customer", utterance="hi", extra=None),
        ]
        db = AsyncSentenceDB("dsn")
        db._pool = pool
        turns = await db.load_transcript_turns("sess_1")
        assert turns[0]["turn"] == 1
        assert "recommendation" not in turns[0]


class TestLoadSessionJsonbParsing:
    @pytest.mark.asyncio
    async def test_parses_jsonb_string_fields(self):
        pool, conn = _make_mock_pool()
        conn.fetchrow.return_value = _FakeRecord(
            session_id="sess_1",
            cust_no="c1",
            context=json.dumps({"k": "v"}),
            conversation_state=json.dumps({"branch_key": {"action": "empathy"}}),
            start_time=datetime(2026, 7, 3, 10, 0, 0),
            last_active=datetime(2026, 7, 3, 10, 0, 0),
        )
        db = AsyncSentenceDB("dsn")
        db._pool = pool
        result = await db.load_session("sess_1")
        assert result is not None
        assert result["context"] == {"k": "v"}
        assert result["conversation_state"] == {"branch_key": {"action": "empathy"}}

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_session(self):
        pool, conn = _make_mock_pool()
        conn.fetchrow.return_value = None
        db = AsyncSentenceDB("dsn")
        db._pool = pool
        assert await db.load_session("nonexistent") is None
