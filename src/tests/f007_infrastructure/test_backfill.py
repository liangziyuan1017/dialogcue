from unittest.mock import AsyncMock, MagicMock

import pytest

from f007_infrastructure.backfill_embeddings import backfill
from f007_infrastructure.async_db import AsyncSentenceDB


def test_backfill_importable():
    assert callable(backfill)


@pytest.mark.asyncio
async def test_backfill_fills_null_embeddings():
    db = MagicMock(spec=AsyncSentenceDB)
    db.fetch_null_embedding_rows = AsyncMock(return_value=[
        {"script_id": "s1", "conversation_context": "ctx1"},
        {"script_id": "s2", "conversation_context": "ctx2"},
    ])
    db.update_embedding = AsyncMock()
    embed_fn = MagicMock(side_effect=[[0.1] * 4, [0.2] * 4])

    filled = await backfill(db, embed_fn)

    assert filled == 2
    assert embed_fn.call_count == 2
    assert db.update_embedding.await_count == 2


@pytest.mark.asyncio
async def test_backfill_noop_when_none_null():
    db = MagicMock(spec=AsyncSentenceDB)
    db.fetch_null_embedding_rows = AsyncMock(return_value=[])
    db.update_embedding = AsyncMock()
    embed_fn = MagicMock()

    filled = await backfill(db, embed_fn)
    assert filled == 0
    embed_fn.assert_not_called()
