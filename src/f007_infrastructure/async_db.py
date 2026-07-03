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
        from f007_infrastructure.migrations.runner import run_migrations
        async with self._acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
            await self._ensure_vector_registered(conn)
            await run_migrations(conn)

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
                    WHERE node_id = ANY($2) AND embedding IS NOT NULL
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
                    WHERE node_id = ANY($2) AND embedding IS NOT NULL
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

    async def fetch_null_embedding_rows(self) -> list[dict]:
        async with self._acquire() as conn:
            rows = await conn.fetch(
                "SELECT script_id, conversation_context FROM sentences WHERE embedding IS NULL"
            )
            return [_row_to_dict(r) for r in rows]

    async def count_null_embeddings(self) -> int:
        async with self._acquire() as conn:
            row = await conn.fetchval("SELECT count(*) FROM sentences WHERE embedding IS NULL")
            return int(row or 0)

    async def update_embedding(self, script_id: str, vec: list[float]) -> None:
        qvec = np.array(vec, dtype=np.float32)
        async with self._acquire() as conn:
            await self._ensure_vector_registered(conn)
            await conn.execute(
                "UPDATE sentences SET embedding = $1::vector WHERE script_id = $2",
                qvec, script_id,
            )

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

    async def load_taxonomy_from_db(self) -> dict:
        async with self._acquire() as conn:
            rows = await conn.fetch(
                "SELECT group_name, category, keyword, frequency FROM taxonomy_keywords ORDER BY category, group_name"
            )
        taxonomy: dict[str, list] = {"facts": [], "emotions": [], "collector_actions": []}
        cat_map = {"facts": "facts", "emotions": "emotions", "collector_actions": "collector_actions"}
        groups: dict[tuple[str, str], dict] = {}
        for r in rows:
            cat = cat_map.get(r["category"])
            if cat is None:
                continue
            key = (cat, r["group_name"])
            g = groups.get(key)
            if g is None:
                g = {"group_name": r["group_name"], "keywords": [], "frequency": 0}
                groups[key] = g
                taxonomy[cat].append(g)
            g["keywords"].append(r["keyword"])
            g["frequency"] = max(g["frequency"], int(r["frequency"] or 0))
        return taxonomy

    async def save_session(self, session_id: str, cust_no: str, context: dict, conversation_state: dict) -> None:
        import json
        async with self._acquire() as conn:
            await conn.execute(
                """
                INSERT INTO sessions (session_id, cust_no, context, conversation_state)
                VALUES ($1, $2, $3::jsonb, $4::jsonb)
                ON CONFLICT (session_id) DO UPDATE SET
                    cust_no = EXCLUDED.cust_no,
                    context = EXCLUDED.context,
                    conversation_state = EXCLUDED.conversation_state,
                    last_active = now()
                """,
                session_id, cust_no, json.dumps(context), json.dumps(conversation_state),
            )

    async def append_transcript_turn(self, session_id: str, turn_index: int, role: str, utterance: str, extra: dict | None = None) -> None:
        import json
        async with self._acquire() as conn:
            await conn.execute(
                "INSERT INTO transcript_turns (session_id, turn_index, role, utterance, extra) VALUES ($1, $2, $3, $4, $5::jsonb)",
                session_id, turn_index, role, utterance, json.dumps(extra or {}),
            )

    async def load_session(self, session_id: str) -> dict | None:
        import json
        async with self._acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM sessions WHERE session_id = $1", session_id)
            if row is None:
                return None
            d = _row_to_dict(row)
            for k in ("context", "conversation_state"):
                if isinstance(d.get(k), str):
                    d[k] = json.loads(d[k])
            return d

    async def load_transcript_turns(self, session_id: str) -> list[dict]:
        import json
        async with self._acquire() as conn:
            rows = await conn.fetch(
                "SELECT turn_index, role, utterance, extra FROM transcript_turns WHERE session_id = $1 ORDER BY turn_index",
                session_id,
            )
        result = []
        for r in rows:
            entry = {"turn": r["turn_index"], "role": r["role"], "utterance": r["utterance"]}
            extra = r["extra"]
            if extra:
                if isinstance(extra, str):
                    extra = json.loads(extra)
                entry.update(extra)
            result.append(entry)
        return result

    async def ping(self) -> bool:
        async with self._acquire() as conn:
            await conn.fetchval("SELECT 1")
        return True

    async def save_relabel_mapping(self, category: str, tag: str, new_label: str) -> None:
        async with self._acquire() as conn:
            await conn.execute(
                """
                INSERT INTO relabel_map (category, tag, new_label)
                VALUES ($1, $2, $3)
                ON CONFLICT (category, tag) DO UPDATE SET new_label = EXCLUDED.new_label, updated_at = now()
                """,
                category, tag, new_label,
            )

    async def load_relabel_map_from_db(self, category: str) -> dict[str, str]:
        async with self._acquire() as conn:
            rows = await conn.fetch("SELECT tag, new_label FROM relabel_map WHERE category = $1", category)
        return {r["tag"]: r["new_label"] for r in rows}


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
