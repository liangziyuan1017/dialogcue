import json
from contextlib import contextmanager

import numpy as np
import psycopg2
import psycopg2.extras
import psycopg2.pool
from pgvector.psycopg2 import register_vector

from f007_infrastructure.config import get as _cfg
from f007_infrastructure.embeddings import EMBEDDING_DIM
from f007_infrastructure.logging import get_logger as _get_logger

_log = _get_logger(__name__)


def _node_labels(node: dict) -> list[str]:
    labels = list(node.get("inherited_facts", [])) + list(node.get("inherited_emotions", []))
    for value in (node.get("branch_key", {}) or {}).values():
        labels.extend(value if isinstance(value, list) else [value])
    return sorted({label for label in labels if label})


class SentenceDB:
    def __init__(self, dsn: str, pool_max: int | None = None):
        self._dsn = dsn
        if pool_max is None:
            pool_max = _cfg("db.pool_max", 10)
        self._pool = psycopg2.pool.ThreadedConnectionPool(1, pool_max, dsn=dsn)
        self._vector_registered_conns: set[int] = set()

    @contextmanager
    def connection(self):
        conn = self._pool.getconn()
        returned = False
        try:
            if conn.closed:
                self._pool.putconn(conn, close=True)
                conn = self._pool.getconn()
            conn.autocommit = True
            yield conn
        except psycopg2.OperationalError as e:
            _log.warning("DB operational error, closing connection: %s", e)
            returned = True
            try:
                self._pool.putconn(conn, close=True)
            except Exception:
                pass
            raise
        finally:
            if not returned:
                self._pool.putconn(conn)

    def _ensure_vector_registered(self, conn):
        conn_id = id(conn)
        if conn_id not in self._vector_registered_conns:
            register_vector(conn)
            self._vector_registered_conns.add(conn_id)

    def close(self):
        self._pool.closeall()

    def create_tables(self):
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
            self._ensure_vector_registered(conn)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id              SERIAL PRIMARY KEY,
                    state_id        TEXT NOT NULL,
                    path_signature  TEXT NOT NULL UNIQUE,
                    branch_key      JSONB,
                    parent_id       INTEGER REFERENCES nodes(id),
                    depth           INTEGER NOT NULL DEFAULT 0,
                    inherited_facts JSONB NOT NULL DEFAULT '[]'::jsonb,
                    inherited_emotions JSONB NOT NULL DEFAULT '[]'::jsonb,
                    labels          JSONB NOT NULL DEFAULT '[]'::jsonb
                )
            """)
            # Migrate older nodes tables that predate label columns
            for col, ddl in (
                ("inherited_facts", "JSONB NOT NULL DEFAULT '[]'::jsonb"),
                ("inherited_emotions", "JSONB NOT NULL DEFAULT '[]'::jsonb"),
                ("labels", "JSONB NOT NULL DEFAULT '[]'::jsonb"),
            ):
                cur.execute(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = 'nodes' AND column_name = %s",
                    (col,),
                )
                if cur.fetchone() is None:
                    cur.execute(f"ALTER TABLE nodes ADD COLUMN {col} {ddl}")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_nodes_path_sig ON nodes(path_signature)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_nodes_parent ON nodes(parent_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_nodes_labels ON nodes USING gin (labels)")

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

            cur.execute("""
                CREATE TABLE IF NOT EXISTS sentence_sources (
                    script_id   TEXT NOT NULL,
                    call_id     TEXT NOT NULL,
                    PRIMARY KEY (script_id, call_id)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_sentence_sources_call_id ON sentence_sources(call_id)")
            cur.close()

    def create_taxonomy_unique_index(self):
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                ALTER TABLE taxonomy_keywords
                ADD COLUMN IF NOT EXISTS natural_key_hash TEXT
                GENERATED ALWAYS AS (md5(group_name || '|' || category || '|' || keyword)) STORED
            """)
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_taxonomy_keyword
                ON taxonomy_keywords (natural_key_hash)
            """)
            cur.close()

    def dedup_taxonomy_keywords(self):
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                DELETE FROM taxonomy_keywords a USING taxonomy_keywords b
                WHERE a.group_name = b.group_name
                  AND a.category = b.category
                  AND a.keyword = b.keyword
                  AND a.id > b.id
            """)
            deleted = cur.rowcount
            cur.close()
            _log.info("dedup_taxonomy_keywords: removed %d duplicate rows", deleted)
            return deleted

    def upsert_taxonomy_keywords(self, rows: list[dict]):
        if not rows:
            return
        with self.connection() as conn:
            cur = conn.cursor()
            cur.executemany(
                """
                INSERT INTO taxonomy_keywords (group_name, category, keyword, frequency)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (natural_key_hash) DO UPDATE SET frequency = EXCLUDED.frequency
                """,
                [(kr["group_name"], kr["category"], kr["keyword"], kr.get("frequency", 0)) for kr in rows],
            )
            cur.close()

    def get_existing_path_signatures(self) -> set[str]:
        with self.connection() as conn:
            cur = conn.cursor(name="stream_sigs", withhold=True)
            cur.itersize = 1000
            cur.execute("SELECT path_signature FROM nodes")
            sigs = set()
            for batch in cur:
                sigs.add(batch[0])
            cur.close()
            return sigs

    def add_sentence_source(self, script_id: str, call_id: str):
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO sentence_sources (script_id, call_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (script_id, call_id),
            )
            cur.close()

    def get_sentence_sources(self, script_id: str) -> list[str]:
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT call_id FROM sentence_sources WHERE script_id = %s ORDER BY call_id", (script_id,))
            result = [r[0] for r in cur.fetchall()]
            cur.close()
            return result

    def has_sentence_source(self, script_id: str, call_id: str) -> bool:
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM sentence_sources WHERE script_id = %s AND call_id = %s", (script_id, call_id))
            result = cur.fetchone() is not None
            cur.close()
            return result

    def get_existing_script_ids(self) -> set[str]:
        with self.connection() as conn:
            cur = conn.cursor(name="stream_ids", withhold=True)
            cur.itersize = 1000
            cur.execute("SELECT script_id FROM sentences")
            ids = set()
            for batch in cur:
                ids.add(batch[0])
            cur.close()
            return ids

    def update_sentence_scores(self, rows: list[dict]):
        if not rows:
            return
        with self.connection() as conn:
            cur = conn.cursor()
            cur.executemany(
                """
                UPDATE sentences SET
                    win_rate = %s,
                    sas = %s,
                    bg_bitmask_int = %s,
                    bg_background = %s,
                    conversation_context = %s
                WHERE script_id = %s
                """,
                [
                    (
                        s.get("win_rate", 0),
                        s.get("sas", 0),
                        s.get("bg_bitmask_int", 0),
                        json.dumps(s.get("bg_background")) if s.get("bg_background") else None,
                        s.get("conversation_context"),
                        s["script_id"],
                    )
                    for s in rows
                ],
            )
            cur.close()

    def delete_sentences(self, script_ids: list[str]):
        if not script_ids:
            return
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM sentences WHERE script_id = ANY(%s)",
                (list(script_ids),),
            )
            deleted = cur.rowcount
            cur.close()
            _log.info("delete_sentences: removed %d orphaned rows", deleted)
            return deleted

    def upsert_nodes(self, nodes: list[dict]):
        if not nodes:
            return
        with self.connection() as conn:
            cur = conn.cursor()
            cur.executemany(
                """
                INSERT INTO nodes (state_id, path_signature, branch_key, parent_id, depth,
                                   inherited_facts, inherited_emotions, labels)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
                ON CONFLICT (path_signature) DO UPDATE SET
                    state_id = EXCLUDED.state_id,
                    branch_key = EXCLUDED.branch_key,
                    parent_id = EXCLUDED.parent_id,
                    depth = EXCLUDED.depth,
                    inherited_facts = EXCLUDED.inherited_facts,
                    inherited_emotions = EXCLUDED.inherited_emotions,
                    labels = EXCLUDED.labels
                """,
                [
                    (
                        n["state_id"], n["path_signature"], json.dumps(n.get("branch_key", {})),
                        n.get("parent_id"), n.get("depth", 0),
                        json.dumps(n.get("inherited_facts", [])),
                        json.dumps(n.get("inherited_emotions", [])),
                        json.dumps(_node_labels(n)),
                    )
                    for n in nodes
                ],
            )
            cur.close()

    def find_nodes_for_labels(self, labels: list[str], limit: int = 32) -> list[dict]:
        query_labels = json.dumps(sorted(set(labels)))
        with self.connection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute(
                """
                SELECT id, state_id, path_signature, branch_key,
                       inherited_facts, inherited_emotions, labels
                FROM nodes
                WHERE labels <@ %s::jsonb
                ORDER BY jsonb_array_length(labels) DESC, depth ASC
                LIMIT %s
                """,
                (query_labels, limit),
            )
            rows = [dict(row) for row in cur.fetchall()]
            cur.close()
        for node in rows:
            node["sentence_pool"] = self.get_sentences_by_node(node["id"])
        return rows

    def get_node_by_signature(self, path_signature: str) -> dict | None:
        with self.connection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM nodes WHERE path_signature = %s", (path_signature,))
            row = cur.fetchone()
            cur.close()
            return dict(row) if row else None

    def get_node_ids_by_signatures(self, path_signatures: list[str]) -> dict[str, int]:
        if not path_signatures:
            return {}
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT path_signature, id FROM nodes WHERE path_signature = ANY(%s)",
                (list(path_signatures),),
            )
            rows = cur.fetchall()
            cur.close()
            return {r[0]: r[1] for r in rows}

    def upsert_sentences(self, sentences: list[dict]):
        if not sentences:
            return
        with self.connection() as conn:
            self._ensure_vector_registered(conn)
            cur = conn.cursor()
            params = []
            for s in sentences:
                emb = np.asarray(s["embedding"], dtype=np.float32) if s.get("embedding") else None
                bg = s.get("bg_background")
                if isinstance(bg, dict):
                    bg = {
                        k: (v.item() if isinstance(v, np.generic) else v)
                        for k, v in bg.items()
                    }
                win_rate = s.get("win_rate", 0)
                sas = s.get("sas", 0)
                bitmask = s.get("bg_bitmask_int", 0)
                params.append((
                    s["script_id"],
                    int(s["node_id"]),
                    s["script_text"],
                    int(bitmask) if bitmask is not None else 0,
                    float(win_rate) if win_rate is not None else 0.0,
                    float(sas) if sas is not None else 0.0,
                    json.dumps(bg) if bg is not None else None,
                    s.get("conversation_context"),
                    emb,
                ))
            cur.executemany(
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
                params,
            )
            source_params = sorted({
                (s["script_id"], call_id)
                for s in sentences
                for call_id in s.get("source_call_ids", [])
            })
            if source_params:
                cur.executemany(
                    "INSERT INTO sentence_sources (script_id, call_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    source_params,
                )
            cur.close()

    def get_sentences_by_node(self, node_id: int) -> list[dict]:
        with self.connection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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
        with self.connection() as conn:
            self._ensure_vector_registered(conn)
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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

    def search_by_nodes(self, query_vec: list[float], node_ids: list[int], limit: int | None = None) -> list[dict]:
        if not node_ids:
            return []
        with self.connection() as conn:
            self._ensure_vector_registered(conn)
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            qvec = np.array(query_vec, dtype=np.float32)
            if limit is not None:
                cur.execute(
                    """
                    SELECT script_id, script_text, bg_bitmask_int, win_rate, sas,
                           bg_background, conversation_context, node_id,
                           1 - (embedding <=> %s::vector) AS vec_score
                    FROM sentences
                    WHERE node_id = ANY(%s)
                    ORDER BY vec_score DESC
                    LIMIT %s
                    """,
                    (qvec, list(node_ids), limit),
                )
            else:
                cur.execute(
                    """
                    SELECT script_id, script_text, bg_bitmask_int, win_rate, sas,
                           bg_background, conversation_context, node_id,
                           1 - (embedding <=> %s::vector) AS vec_score
                    FROM sentences
                    WHERE node_id = ANY(%s)
                    ORDER BY vec_score DESC
                    """,
                    (qvec, list(node_ids)),
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
        with self.connection() as conn:
            self._ensure_vector_registered(conn)
            cur = conn.cursor()
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
        with self.connection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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
        with self.connection() as conn:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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
