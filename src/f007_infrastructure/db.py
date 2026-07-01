import json

import numpy as np
import psycopg2
import psycopg2.extras
from pgvector.psycopg2 import register_vector

from f007_infrastructure.config import get as _cfg
from f007_infrastructure.embeddings import EMBEDDING_DIM


class SentenceDB:
    def __init__(self, dsn: str):
        self._dsn = dsn
        self._conn = psycopg2.connect(dsn)
        self._conn.autocommit = True
        self._vector_registered = False

    def _ensure_vector_registered(self):
        if not self._vector_registered:
            register_vector(self._conn)
            self._vector_registered = True

    def close(self):
        self._conn.close()

    def create_tables(self):
        cur = self._conn.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        self._ensure_vector_registered()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id              SERIAL PRIMARY KEY,
                state_id        TEXT NOT NULL,
                path_signature  TEXT NOT NULL UNIQUE,
                branch_key      JSONB,
                parent_id       INTEGER REFERENCES nodes(id),
                depth           INTEGER NOT NULL DEFAULT 0
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_nodes_path_sig ON nodes(path_signature)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_nodes_parent ON nodes(parent_id)")

        cur.execute(f"""
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
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sentences_node_id ON sentences(node_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sentences_bg_bitmask ON sentences(bg_bitmask_int)")
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_sentences_embedding ON sentences USING hnsw (embedding vector_cosine_ops)
            WITH (m = {_cfg("hnsw.m", 16)}, ef_construction = {_cfg("hnsw.ef_construction", 64)})
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sentences_tsv ON sentences USING gin (script_tsv)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sentences_script_text_trgm ON sentences USING gin (script_text gin_trgm_ops)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS taxonomy_keywords (
                id          SERIAL PRIMARY KEY,
                group_name  TEXT NOT NULL,
                category    TEXT NOT NULL,
                keyword     TEXT NOT NULL,
                frequency   INTEGER NOT NULL DEFAULT 0,
                tsv         tsvector GENERATED ALWAYS AS (to_tsvector('simple', keyword)) STORED
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_taxonomy_tsv ON taxonomy_keywords USING gin (tsv)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_taxonomy_group ON taxonomy_keywords(group_name, category)")
        cur.close()

    def upsert_nodes(self, nodes: list[dict]):
        if not nodes:
            return
        cur = self._conn.cursor()
        for n in nodes:
            cur.execute(
                """
                INSERT INTO nodes (state_id, path_signature, branch_key, parent_id, depth)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (path_signature) DO UPDATE SET
                    state_id = EXCLUDED.state_id,
                    branch_key = EXCLUDED.branch_key,
                    parent_id = EXCLUDED.parent_id,
                    depth = EXCLUDED.depth
                """,
                (n["state_id"], n["path_signature"], json.dumps(n.get("branch_key", {})), n.get("parent_id"), n.get("depth", 0)),
            )
        cur.close()

    def get_node_by_signature(self, path_signature: str) -> dict | None:
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM nodes WHERE path_signature = %s", (path_signature,))
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None

    def upsert_sentences(self, sentences: list[dict]):
        if not sentences:
            return
        self._ensure_vector_registered()
        cur = self._conn.cursor()
        for s in sentences:
            emb = np.array(s["embedding"], dtype=np.float32) if s.get("embedding") else None
            cur.execute(
                """
                INSERT INTO sentences (script_id, node_id, script_text, bg_bitmask_int, win_rate, sas, bg_background, conversation_context, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                (
                    s["script_id"],
                    s["node_id"],
                    s["script_text"],
                    s.get("bg_bitmask_int", 0),
                    s.get("win_rate", 0),
                    s.get("sas", 0),
                    json.dumps(s.get("bg_background")) if s.get("bg_background") else None,
                    s.get("conversation_context"),
                    emb,
                ),
            )
        cur.close()

    def get_sentences_by_node(self, node_id: int) -> list[dict]:
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT script_id, script_text, bg_bitmask_int, win_rate, sas, bg_background, conversation_context FROM sentences WHERE node_id = %s",
            (node_id,),
        )
        rows = cur.fetchall()
        cur.close()
        results = []
        for r in rows:
            d = {}
            for k, v in dict(r).items():
                if isinstance(v, (np.floating, np.integer)):
                    v = float(v)
                d[k] = v
            results.append(d)
        return results

    def search_similar(self, query_vec: list[float], node_id: int, query_bitmask: int, limit: int | None = None) -> list[dict]:
        if limit is None:
            limit = _cfg("search.vector_limit", 50)
        self._ensure_vector_registered()
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        qvec = np.array(query_vec, dtype=np.float32)
        cur.execute(
            """
            SELECT script_id, script_text, bg_bitmask_int, win_rate, sas, bg_background,
                   1 - (embedding <=> %s::vector) AS vec_score
            FROM sentences
            WHERE node_id = %s AND (bg_bitmask_int & %s) = bg_bitmask_int
            ORDER BY vec_score DESC
            LIMIT %s
            """,
            (qvec, node_id, query_bitmask, limit),
        )
        rows = cur.fetchall()
        cur.close()
        results = []
        for r in rows:
            d = {}
            for k, v in dict(r).items():
                if isinstance(v, (np.floating, np.integer)):
                    v = float(v)
                if k == "vec_score" and v != v:
                    v = 0.0
                d[k] = v
            results.append(d)
        return results

    def get_vectors(self, script_ids: list[str]) -> dict[str, list[float]]:
        if not script_ids:
            return {}
        self._ensure_vector_registered()
        cur = self._conn.cursor()
        placeholders = ",".join(["%s"] * len(script_ids))
        cur.execute(
            f"SELECT script_id, embedding FROM sentences WHERE script_id IN ({placeholders})",
            tuple(script_ids),
        )
        rows = cur.fetchall()
        cur.close()
        return {r[0]: list(r[1]) if r[1] is not None else [0.0] * EMBEDDING_DIM for r in rows}

    def keyword_search(self, query_text: str, limit: int | None = None) -> list[dict]:
        if limit is None:
            limit = _cfg("search.keyword_limit", 20)
        if not query_text.strip():
            return []
        tokens = " & ".join(query_text.split())
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT script_id, script_text, ts_rank(script_tsv, to_tsquery('simple', %s)) AS rank
            FROM sentences
            WHERE script_tsv @@ to_tsquery('simple', %s)
            ORDER BY rank DESC
            LIMIT %s
            """,
            (tokens, tokens, limit),
        )
        rows = cur.fetchall()
        if not rows:
            cur.execute(
                """
                SELECT script_id, script_text, similarity(script_text, %s) AS rank
                FROM sentences
                WHERE similarity(script_text, %s) > %s
                ORDER BY rank DESC
                LIMIT %s
                """,
                (query_text, query_text, _cfg("search.trigram_threshold", 0.01), limit),
            )
            rows = cur.fetchall()
        cur.close()
        results = []
        for r in rows:
            d = {}
            for k, v in dict(r).items():
                if isinstance(v, (np.floating, np.integer)):
                    v = float(v)
                d[k] = v
            results.append(d)
        return results

    def taxonomy_keyword_search(self, query_text: str, limit: int | None = None) -> list[dict]:
        if limit is None:
            limit = _cfg("search.taxonomy_limit", 20)
        if not query_text.strip():
            return []
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        tokens = " & ".join(query_text.split())
        if len(tokens) > 1:
            cur.execute(
                """
                SELECT group_name, category, keyword, ts_rank(tsv, to_tsquery('simple', %s)) AS rank
                FROM taxonomy_keywords
                WHERE tsv @@ to_tsquery('simple', %s)
                ORDER BY rank DESC
                LIMIT %s
                """,
                (tokens, tokens, limit),
            )
            rows = cur.fetchall()
            if rows:
                cur.close()
                return [dict(r) for r in rows]
        cur.execute(
            """
            SELECT group_name, category, keyword, similarity(keyword, %s) AS rank
            FROM taxonomy_keywords
            WHERE similarity(keyword, %s) > %s
            ORDER BY rank DESC
            LIMIT %s
            """,
            (query_text, query_text, _cfg("search.taxonomy_trigram_threshold", 0.1), limit),
        )
        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]
