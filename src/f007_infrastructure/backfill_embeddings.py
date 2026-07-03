"""Backfill missing embeddings (F012 Phase E, item 4.1).

Finds sentences with NULL embedding, embeds their conversation_context,
and updates the row. Used when a build skipped unembeddable sentences.
"""

from f007_infrastructure.logging import get_logger as _get_logger

_log = _get_logger(__name__)


async def backfill(db, embed_fn) -> int:
    rows = await db.fetch_null_embedding_rows()
    if not rows:
        _log.info("backfill: no NULL embeddings found")
        return 0
    filled = 0
    for row in rows:
        ctx = row.get("conversation_context") or ""
        try:
            vec = embed_fn(ctx)
        except Exception as e:
            _log.warning("backfill: embed failed for %s: %s", row.get("script_id"), e)
            continue
        await db.update_embedding(row["script_id"], vec)
        filled += 1
    _log.info("backfill: filled %d/%d NULL embeddings", filled, len(rows))
    return filled
