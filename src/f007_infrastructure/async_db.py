import asyncpg
import numpy as np
from pgvector.asyncpg import register_vector as _register_vector

from f007_infrastructure.config import get as _cfg
from f007_infrastructure.embeddings import EMBEDDING_DIM
from f007_infrastructure.logging import get_logger as _get_logger

_log = _get_logger(__name__)


class AsyncSentenceDB:
    def __init__(self, dsn: str, pool_max: int | None = None):
        self._dsn = dsn
        if pool_max is None:
            pool_max = _cfg("db.pool_max", 10)
        self._pool_max = pool_max
        self._pool: asyncpg.Pool | None = None
        self._vector_registered_conns: set[int] = set()

    async def connect(self):
        if self._pool is not None:
            await self._pool.close()
        self._pool = await asyncpg.create_pool(
            self._dsn, min_size=1, max_size=self._pool_max,
        )

    async def close(self):
        if self._pool:
            await self._pool.close()
            self._pool = None

    def _acquire(self):
        if self._pool is None:
            raise RuntimeError("AsyncSentenceDB not connected — call connect() first")
        return self._pool.acquire()

    async def _ensure_vector_registered(self, conn):
        conn_id = id(conn)
        if conn_id not in self._vector_registered_conns:
            await _register_vector(conn)
            self._vector_registered_conns.add(conn_id)

    async def create_tables(self):
        async with self._acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
            await self._ensure_vector_registered(conn)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id              SERIAL PRIMARY KEY,
                    state_id        TEXT NOT NULL,
                    path_signature  TEXT NOT NULL UNIQUE,
                    branch_key      JSONB,
                    parent_id       INTEGER REFERENCES nodes(id),
                    depth           INTEGER NOT NULL DEFAULT 0
                )
            """)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_path_sig ON nodes(path_signature)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_parent ON nodes(parent_id)")

            await conn.execute(f"""
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
            """)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_sentences_node_id ON sentences(node_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_sentences_bg_bitmask ON sentences(bg_bitmask_int)")
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_sentences_embedding ON sentences USING hnsw (embedding vector_cosine_ops)
                WITH (m = {_cfg("hnsw.m", 16)}, ef_construction = {_cfg("hnsw.ef_construction", 64)})
            """)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_sentences_tsv ON sentences USING gin (script_tsv)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_sentences_script_text_trgm ON sentences USING gin (script_text gin_trgm_ops)")

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS taxonomy_keywords (
                    id          SERIAL PRIMARY KEY,
                    group_name  TEXT NOT NULL,
                    category    TEXT NOT NULL,
                    keyword     TEXT NOT NULL,
                    frequency   INTEGER NOT NULL DEFAULT 0,
                    tsv         tsvector GENERATED ALWAYS AS (to_tsvector('simple', keyword)) STORED
                )
            """)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_taxonomy_tsv ON taxonomy_keywords USING gin (tsv)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_taxonomy_group ON taxonomy_keywords(group_name, category)")

    async def upsert_nodes(self, nodes: list[dict]):
        if not nodes:
            return
        async with self._acquire() as conn:
            for n in nodes:
                await conn.execute(
                    """
                    INSERT INTO nodes (state_id, path_signature, branch_key, parent_id, depth)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (path_signature) DO UPDATE SET
                        state_id = EXCLUDED.state_id,
                        branch_key = EXCLUDED.branch_key,
                        parent_id = EXCLUDED.parent_id,
                        depth = EXCLUDED.depth
                    """,
                    n["state_id"], n["path_signature"], n.get("branch_key", {}), n.get("parent_id"), n.get("depth", 0),
                )

    async def get_node_by_signature(self, path_signature: str) -> dict | None:
        async with self._acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM nodes WHERE path_signature = $1",
                path_signature,
            )
            return _row_to_dict(row) if row else None

    async def get_node_ids_by_signatures(self, path_signatures: list[str]) -> dict[str, int]:
        if not path_signatures:
            return {}
        async with self._acquire() as conn:
            rows = await conn.fetch(
                "SELECT path_signature, id FROM nodes WHERE path_signature = ANY($1)",
                path_signatures,
            )
            return {r["path_signature"]: r["id"] for r in rows}

    async def search_by_nodes(self, query_vec: list[float], node_ids: list[int], limit: int | None = None) -> list[dict]:
        if not node_ids:
            return []
        qvec = np.array(query_vec, dtype=np.float32)
        async with self._acquire() as conn:
            await self._ensure_vector_registered(conn)
            if limit is not None:
                rows = await conn.fetch(
                    """
                    SELECT script_id, script_text, bg_bitmask_int, win_rate, sas,
                           bg_background, conversation_context, node_id,
                           1 - (embedding <=> $1::vector) AS vec_score
                    FROM sentences
                    WHERE node_id = ANY($2)
                    ORDER BY vec_score DESC
                    LIMIT $3
                    """,
                    qvec, node_ids, limit,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT script_id, script_text, bg_bitmask_int, win_rate, sas,
                           bg_background, conversation_context, node_id,
                           1 - (embedding <=> $1::vector) AS vec_score
                    FROM sentences
                    WHERE node_id = ANY($2)
                    ORDER BY vec_score DESC
                    """,
                    qvec, node_ids,
                )
            return [_row_to_dict(r) for r in rows]

    async def get_sentences_by_node(self, node_id: int) -> list[dict]:
        async with self._acquire() as conn:
            rows = await conn.fetch(
                "SELECT script_id, script_text, bg_bitmask_int, win_rate, sas, bg_background, conversation_context FROM sentences WHERE node_id = $1",
                node_id,
            )
            return [_row_to_dict(r) for r in rows]

    async def search_similar(self, query_vec: list[float], node_id: int, query_bitmask: int, limit: int | None = None) -> list[dict]:
        if limit is None:
            limit = _cfg("search.vector_limit", 50)
        qvec = np.array(query_vec, dtype=np.float32)
        async with self._acquire() as conn:
            await self._ensure_vector_registered(conn)
            rows = await conn.fetch(
                """
                SELECT script_id, script_text, bg_bitmask_int, win_rate, sas, bg_background,
                       1 - (embedding <=> $1::vector) AS vec_score
                FROM sentences
                WHERE node_id = $2 AND (bg_bitmask_int & $3) = bg_bitmask_int
                ORDER BY vec_score DESC
                LIMIT $4
                """,
                qvec, node_id, query_bitmask, limit,
            )
            return [_row_to_dict(r) for r in rows]

    async def upsert_sentences(self, sentences: list[dict]):
        if not sentences:
            return
        async with self._acquire() as conn:
            await self._ensure_vector_registered(conn)
            for s in sentences:
                emb = np.array(s["embedding"], dtype=np.float32) if s.get("embedding") else None
                await conn.execute(
                    """
                    INSERT INTO sentences (script_id, node_id, script_text, bg_bitmask_int, win_rate, sas, bg_background, conversation_context, embedding)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::vector)
                    ON CONFLICT (script_id) DO UPDATE SET
                        node_id = EXCLUDED.node_id,
                        script_text = EXCLUDED.script_text,
                        bg_bitmask_int = EXCLUDED.bg_bitmask_int,
                        win_rate = EXCLUDED.win_rate,
                        sas = EXCLUDED.sas,
                        bg_background = EXCLUDED.bg_background,
                        conversation_context = EXCLUDED.conversation_context,
                        embedding = EXCLUDED.embedding
                    """,
                    s["script_id"],
                    s["node_id"],
                    s["script_text"],
                    s.get("bg_bitmask_int", 0),
                    s.get("win_rate", 0),
                    s.get("sas", 0),
                    s.get("bg_background"),
                    s.get("conversation_context"),
                    emb,
                )

    async def get_vectors(self, script_ids: list[str]) -> dict[str, list[float]]:
        if not script_ids:
            return {}
        async with self._acquire() as conn:
            await self._ensure_vector_registered(conn)
            rows = await conn.fetch(
                "SELECT script_id, embedding FROM sentences WHERE script_id = ANY($1)",
                script_ids,
            )
            result = {}
            for r in rows:
                emb = r["embedding"]
                if emb is None:
                    emb = [0.0] * EMBEDDING_DIM
                elif isinstance(emb, np.ndarray):
                    emb = emb.tolist()
                else:
                    emb = list(emb)
                result[r["script_id"]] = emb
            return result

    async def keyword_search(self, query_text: str, limit: int | None = None) -> list[dict]:
        if limit is None:
            limit = _cfg("search.keyword_limit", 20)
        if not query_text.strip():
            return []
        tokens = " & ".join(query_text.split())
        async with self._acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT script_id, script_text, ts_rank(script_tsv, to_tsquery('simple', $1)) AS rank
                FROM sentences
                WHERE script_tsv @@ to_tsquery('simple', $1)
                ORDER BY rank DESC
                LIMIT $2
                """,
                tokens, limit,
            )
            if not rows:
                rows = await conn.fetch(
                    """
                    SELECT script_id, script_text, similarity(script_text, $1) AS rank
                    FROM sentences
                    WHERE similarity(script_text, $1) > $2
                    ORDER BY rank DESC
                    LIMIT $3
                    """,
                    query_text, _cfg("search.trigram_threshold", 0.01), limit,
                )
            return [_row_to_dict(r) for r in rows]

    async def taxonomy_keyword_search(self, query_text: str, limit: int | None = None) -> list[dict]:
        if limit is None:
            limit = _cfg("search.taxonomy_limit", 20)
        if not query_text.strip():
            return []
        async with self._acquire() as conn:
            tokens = " & ".join(query_text.split())
            if len(tokens) > 1:
                rows = await conn.fetch(
                    """
                    SELECT group_name, category, keyword, ts_rank(tsv, to_tsquery('simple', $1)) AS rank
                    FROM taxonomy_keywords
                    WHERE tsv @@ to_tsquery('simple', $1)
                    ORDER BY rank DESC
                    LIMIT $2
                    """,
                    tokens, limit,
                )
                if rows:
                    return [dict(r) for r in rows]
            rows = await conn.fetch(
                """
                SELECT group_name, category, keyword, similarity(keyword, $1) AS rank
                FROM taxonomy_keywords
                WHERE similarity(keyword, $1) > $2
                ORDER BY rank DESC
                LIMIT $3
                """,
                query_text, _cfg("search.taxonomy_trigram_threshold", 0.1), limit,
            )
            return [dict(r) for r in rows]


def _row_to_dict(r: asyncpg.Record) -> dict:
    d = {}
    for k, v in dict(r).items():
        if isinstance(v, np.ndarray):
            v = v.tolist()
        elif isinstance(v, (np.floating, np.integer)):
            v = float(v)
        if isinstance(v, float) and k == "vec_score" and v != v:
            v = 0.0
        d[k] = v
    return d
