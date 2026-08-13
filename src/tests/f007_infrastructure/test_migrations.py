from unittest.mock import AsyncMock, MagicMock

import pytest

from f007_infrastructure.migrations.runner import Migration, run_migrations, MIGRATIONS


def test_migrations_are_versioned_and_sorted():
    versions = [m.version for m in MIGRATIONS]
    assert versions == sorted(versions)
    assert all(m.version >= 1 for m in MIGRATIONS)
    assert any(m.name == "baseline" for m in MIGRATIONS)


def test_f017_migration_creates_sentence_sources_table():
    migration = next(m for m in MIGRATIONS if m.name == "f017_sentence_sources")
    assert any("CREATE TABLE IF NOT EXISTS sentence_sources" in statement for statement in migration.statements)


async def _fetchval(query, *args):
    if "count(*)" in query:
        return 0
    return None


@pytest.mark.asyncio
async def test_run_migrations_applies_all_on_fresh_db():
    conn = MagicMock()
    conn.fetchval = AsyncMock(side_effect=_fetchval)
    conn.execute = AsyncMock()
    applied = await run_migrations(conn)
    assert applied == len(MIGRATIONS)


@pytest.mark.asyncio
async def test_run_migrations_idempotent_when_all_applied():
    async def _all_applied(query, *args):
        if "count(*)" in query:
            return len(MIGRATIONS)
        return 1
    conn = MagicMock()
    conn.fetchval = AsyncMock(side_effect=_all_applied)
    conn.execute = AsyncMock()
    applied = await run_migrations(conn)
    assert applied == 0


@pytest.mark.asyncio
async def test_run_migrations_applies_only_pending():
    async def _one_applied(query, *args):
        if "count(*)" in query:
            return 1
        if args and args[0] == 1:
            return 1
        return None
    conn = MagicMock()
    conn.fetchval = AsyncMock(side_effect=_one_applied)
    conn.execute = AsyncMock()
    applied = await run_migrations(conn)
    assert applied == len(MIGRATIONS) - 1
