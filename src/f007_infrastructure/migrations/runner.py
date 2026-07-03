"""Schema migration runner (F012 Phase F, item 5.1).

Replaces the bare `create_tables` with a versioned migration set. Each
migration is applied once and tracked in a `_migrations` table. Re-running
is idempotent (pending migrations only).
"""

from dataclasses import dataclass

from f007_infrastructure.config import get as _cfg
from f007_infrastructure.embeddings import EMBEDDING_DIM


@dataclass
class Migration:
    version: int
    name: str
    statements: list[str]


def _baseline_statements() -> list[str]:
    m = _cfg("hnsw.m", 16)
    ef = _cfg("hnsw.ef_construction", 64)
    return [
        "CREATE EXTENSION IF NOT EXISTS vector",
        "CREATE EXTENSION IF NOT EXISTS pg_trgm",
        """
        CREATE TABLE IF NOT EXISTS nodes (
            id              SERIAL PRIMARY KEY,
            state_id        TEXT NOT NULL,
            path_signature  TEXT NOT NULL UNIQUE,
            branch_key      JSONB,
            parent_id       INTEGER REFERENCES nodes(id),
            depth           INTEGER NOT NULL DEFAULT 0
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_nodes_path_sig ON nodes(path_signature)",
        "CREATE INDEX IF NOT EXISTS idx_nodes_parent ON nodes(parent_id)",
        f"""
        CREATE TABLE IF NOT EXISTS sentences (
            id                  SERIAL PRIMARY KEY,
            script_id           TEXT NOT NULL UNIQUE,
            node_id             INTEGER NOT NULL REFERENCES nodes(id),
            script_text         TEXT NOT NULL,
            bg_bitmask_int      INTEGER NOT NULL DEFAULT 0,
            win_rate            REAL NOT NULL DEFAULT 0,
            sas                 REAL NOT NULL DEFAULT 0,
            bg_background       JSONB,
            conversation_context TEXT,
            embedding           vector({EMBEDDING_DIM}),
            script_tsv          tsvector GENERATED ALWAYS AS (to_tsvector('simple', script_text)) STORED
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_sentences_node_id ON sentences(node_id)",
        "CREATE INDEX IF NOT EXISTS idx_sentences_bg_bitmask ON sentences(bg_bitmask_int)",
        f"""
        CREATE INDEX IF NOT EXISTS idx_sentences_embedding ON sentences USING hnsw (embedding vector_cosine_ops)
        WITH (m = {m}, ef_construction = {ef})
        """,
        "CREATE INDEX IF NOT EXISTS idx_sentences_tsv ON sentences USING gin (script_tsv)",
        "CREATE INDEX IF NOT EXISTS idx_sentences_script_text_trgm ON sentences USING gin (script_text gin_trgm_ops)",
        """
        CREATE TABLE IF NOT EXISTS taxonomy_keywords (
            id          SERIAL PRIMARY KEY,
            group_name  TEXT NOT NULL,
            category    TEXT NOT NULL,
            keyword     TEXT NOT NULL,
            frequency   INTEGER NOT NULL DEFAULT 0,
            tsv         tsvector GENERATED ALWAYS AS (to_tsvector('simple', keyword)) STORED
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_taxonomy_tsv ON taxonomy_keywords USING gin (tsv)",
        "CREATE INDEX IF NOT EXISTS idx_taxonomy_group ON taxonomy_keywords(group_name, category)",
    ]


def _phase_f_statements() -> list[str]:
    return [
        """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id      TEXT PRIMARY KEY,
            cust_no         TEXT,
            context         JSONB,
            conversation_state JSONB,
            start_time      TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_active     TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS transcript_turns (
            id              SERIAL PRIMARY KEY,
            session_id      TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
            turn_index      INTEGER NOT NULL,
            role            TEXT NOT NULL,
            utterance       TEXT NOT NULL,
            extra           JSONB,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS relabel_map (
            category        TEXT NOT NULL,
            tag             TEXT NOT NULL,
            new_label       TEXT NOT NULL,
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (category, tag)
        )
        """,
    ]


MIGRATIONS: list[Migration] = [
    Migration(1, "baseline", _baseline_statements()),
    Migration(2, "phase_f_sessions_relabel", _phase_f_statements()),
    Migration(3, "f014_call_info_agent", [
        "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS call_info JSONB",
        "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS agent JSONB",
    ]),
]


async def run_migrations(conn) -> int:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS _migrations (
            version     INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    applied_count = await conn.fetchval("SELECT count(*) FROM _migrations")
    applied_count = int(applied_count or 0)
    applied = 0
    for mig in MIGRATIONS:
        exists = await conn.fetchval("SELECT 1 FROM _migrations WHERE version = $1", mig.version)
        if exists:
            continue
        for stmt in mig.statements:
            await conn.execute(stmt)
        await conn.execute("INSERT INTO _migrations (version, name) VALUES ($1, $2)", mig.version, mig.name)
        applied += 1
    return applied
