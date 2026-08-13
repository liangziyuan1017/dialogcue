from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from f007_infrastructure.async_db import AsyncSentenceDB, _row_to_dict
from f007_infrastructure.embeddings import EMBEDDING_DIM


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


def _patch_create_pool(pool):
    mock_create = AsyncMock(return_value=pool)
    return patch("f007_infrastructure.async_db.asyncpg.create_pool", mock_create)


class TestInstantiation:
    def test_creates_with_dsn(self):
        db = AsyncSentenceDB("postgresql://localhost/test")
        assert db._dsn == "postgresql://localhost/test"

    def test_default_pool_max(self):
        with patch("f007_infrastructure.async_db._cfg", return_value=10):
            db = AsyncSentenceDB("postgresql://localhost/test")
            assert db._pool_max == 10

    def test_custom_pool_max(self):
        db = AsyncSentenceDB("postgresql://localhost/test", pool_max=5)
        assert db._pool_max == 5

    def test_pool_initially_none(self):
        db = AsyncSentenceDB("postgresql://localhost/test")
        assert db._pool is None


class TestConnect:
    @pytest.mark.asyncio
    async def test_connect_creates_pool(self):
        pool, _ = _make_mock_pool()
        with _patch_create_pool(pool) as mock_create:
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            mock_create.assert_awaited_once()
            assert mock_create.call_args[0][0] == "postgresql://localhost/test"
            assert mock_create.call_args[1]["min_size"] == 1
            assert mock_create.call_args[1]["max_size"] == 10
            assert db._pool is pool

    @pytest.mark.asyncio
    async def test_connect_custom_pool_max(self):
        pool, _ = _make_mock_pool()
        with _patch_create_pool(pool) as mock_create:
            db = AsyncSentenceDB("postgresql://localhost/test", pool_max=5)
            await db.connect()
            assert mock_create.call_args[1]["max_size"] == 5

    @pytest.mark.asyncio
    async def test_connect_no_init_callback(self):
        pool, _ = _make_mock_pool()
        with _patch_create_pool(pool) as mock_create:
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            assert "init" not in mock_create.call_args[1]

    @pytest.mark.asyncio
    async def test_connect_closes_old_pool(self):
        pool1, _ = _make_mock_pool()
        pool2, _ = _make_mock_pool()
        with _patch_create_pool(pool1):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
        with _patch_create_pool(pool2):
            await db.connect()
            pool1.close.assert_awaited_once()
            assert db._pool is pool2


class TestClose:
    @pytest.mark.asyncio
    async def test_close_pool(self):
        pool, _ = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            await db.close()
            pool.close.assert_awaited_once()
            assert db._pool is None

    @pytest.mark.asyncio
    async def test_close_noop_when_not_connected(self):
        db = AsyncSentenceDB("postgresql://localhost/test")
        await db.close()
        assert db._pool is None


class TestAcquireGuard:
    def test_operations_before_connect_raise(self):
        db = AsyncSentenceDB("postgresql://localhost/test")
        with pytest.raises(RuntimeError, match="not connected"):
            db._acquire()


class TestEnsureVectorRegistered:
    @pytest.mark.asyncio
    async def test_registers_on_first_call(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            await db._ensure_vector_registered(conn)
            assert len(db._vector_registered_conns) == 1

    @pytest.mark.asyncio
    async def test_skips_on_subsequent_calls(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            await db._ensure_vector_registered(conn)
            call_count = conn.set_type_codec.call_count
            await db._ensure_vector_registered(conn)
            assert conn.set_type_codec.call_count == call_count


class TestVectorCastInSql:
    @pytest.mark.asyncio
    async def test_search_by_nodes_uses_vector_cast(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            conn.fetch.return_value = []
            await db.search_by_nodes([0.1] * EMBEDDING_DIM, [1])
            calls = [str(c) for c in conn.fetch.call_args_list]
            assert any("::vector" in c for c in calls)

    @pytest.mark.asyncio
    async def test_search_similar_uses_vector_cast(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            conn.fetch.return_value = []
            await db.search_similar([0.1] * EMBEDDING_DIM, node_id=1, query_bitmask=3)
            calls = [str(c) for c in conn.fetch.call_args_list]
            assert any("::vector" in c for c in calls)

    @pytest.mark.asyncio
    async def test_upsert_sentences_uses_vector_cast(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            sentences = [{"script_id": "s1", "node_id": 1, "script_text": "hello", "embedding": [0.1] * EMBEDDING_DIM}]
            await db.upsert_sentences(sentences)
            calls = [str(c) for c in conn.executemany.call_args_list]
            assert any("::vector" in c for c in calls)


class TestCreateTables:
    @pytest.mark.asyncio
    async def test_creates_vector_extension(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            await db.create_tables()
            calls = [str(c) for c in conn.execute.call_args_list]
            assert any("vector" in c for c in calls)

    @pytest.mark.asyncio
    async def test_creates_pg_trgm_extension(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            await db.create_tables()
            calls = [str(c) for c in conn.execute.call_args_list]
            assert any("pg_trgm" in c for c in calls)

    @pytest.mark.asyncio
    async def test_creates_nodes_table(self):
        pool, conn = _make_mock_pool()
        conn.fetchval = AsyncMock(return_value=None)
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            await db.create_tables()
            calls = [str(c) for c in conn.execute.call_args_list]
            assert any("nodes" in c and "CREATE" in c.upper() for c in calls)

    @pytest.mark.asyncio
    async def test_creates_sentences_table(self):
        pool, conn = _make_mock_pool()
        conn.fetchval = AsyncMock(return_value=None)
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            await db.create_tables()
            calls = [str(c) for c in conn.execute.call_args_list]
            assert any("sentences" in c and "CREATE" in c.upper() for c in calls)

    @pytest.mark.asyncio
    async def test_creates_hnsw_index(self):
        pool, conn = _make_mock_pool()
        conn.fetchval = AsyncMock(return_value=None)
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            await db.create_tables()
            calls = [str(c) for c in conn.execute.call_args_list]
            assert any("hnsw" in c.lower() for c in calls)

    @pytest.mark.asyncio
    async def test_creates_trgm_index(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            await db.create_tables()
            calls = [str(c) for c in conn.execute.call_args_list]
            assert any("trgm" in c.lower() for c in calls)

    @pytest.mark.asyncio
    async def test_registers_vector_codec(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            await db.create_tables()
            assert len(db._vector_registered_conns) > 0


class TestUpsertNodes:
    @pytest.mark.asyncio
    async def test_inserts_node(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            nodes = [{"state_id": "initial_contact", "path_signature": "", "branch_key": {}, "parent_id": None, "depth": 0}]
            await db.upsert_nodes(nodes)
            assert conn.executemany.call_count > 0

    @pytest.mark.asyncio
    async def test_uses_on_conflict(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            nodes = [{"state_id": "s1", "path_signature": "p1", "branch_key": {}, "parent_id": None, "depth": 0}]
            await db.upsert_nodes(nodes)
            calls = [str(c) for c in conn.executemany.call_args_list]
            assert any("ON CONFLICT" in c.upper() for c in calls)

    @pytest.mark.asyncio
    async def test_empty_list_noop(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            await db.upsert_nodes([])
            assert conn.executemany.call_count == 0

    @pytest.mark.asyncio
    async def test_passes_node_params(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            nodes = [{"state_id": "s1", "path_signature": "p1", "branch_key": {"k": 1}, "parent_id": 5, "depth": 2}]
            await db.upsert_nodes(nodes)
            args = conn.executemany.call_args_list[0]
            row = args[0][1][0]
            assert row[0] == "s1"
            assert row[1] == "p1"
            assert row[2] == {"k": 1}
            assert row[3] == 5
            assert row[4] == 2


class TestGetNodeBySignature:
    @pytest.mark.asyncio
    async def test_returns_dict_when_found(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            conn.fetchrow.return_value = _FakeRecord(id=1, state_id="s1", path_signature="p1")
            result = await db.get_node_by_signature("p1")
            assert result is not None
            assert result["state_id"] == "s1"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            conn.fetchrow.return_value = None
            result = await db.get_node_by_signature("nonexistent")
            assert result is None


class TestSentenceSources:
    @pytest.mark.asyncio
    async def test_add_source_uses_idempotent_insert(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            await db.add_sentence_source("s1", "c1")
            query = conn.execute.call_args.args[0]
            assert "sentence_sources" in query
            assert "ON CONFLICT" in query

    @pytest.mark.asyncio
    async def test_get_source_ids(self):
        pool, conn = _make_mock_pool()
        conn.fetch.return_value = [_FakeRecord(call_id="c2"), _FakeRecord(call_id="c1")]
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            result = await db.get_sentence_sources("s1")
            assert result == ["c2", "c1"]

    @pytest.mark.asyncio
    async def test_passes_path_signature_param(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            conn.fetchrow.return_value = None
            await db.get_node_by_signature("my_sig")
            args = conn.fetchrow.call_args_list[0]
            assert args[0][1] == "my_sig"


class TestGetNodeIdsBySignatures:
    @pytest.mark.asyncio
    async def test_returns_mapping(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            conn.fetch.return_value = [_FakeRecord(path_signature="p1", id=1), _FakeRecord(path_signature="p2", id=2)]
            result = await db.get_node_ids_by_signatures(["p1", "p2"])
            assert result == {"p1": 1, "p2": 2}

    @pytest.mark.asyncio
    async def test_empty_list_returns_empty(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            result = await db.get_node_ids_by_signatures([])
            assert result == {}
            assert conn.fetch.call_count == 0


class TestSearchByNodes:
    @pytest.mark.asyncio
    async def test_empty_node_ids_returns_empty(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            result = await db.search_by_nodes([0.1] * EMBEDDING_DIM, [])
            assert result == []

    @pytest.mark.asyncio
    async def test_uses_cosine_distance(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            conn.fetch.return_value = []
            await db.search_by_nodes([0.1] * EMBEDDING_DIM, [1])
            calls = [str(c) for c in conn.fetch.call_args_list]
            assert any("<=>" in c for c in calls)

    @pytest.mark.asyncio
    async def test_passes_node_ids_and_limit(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            conn.fetch.return_value = []
            await db.search_by_nodes([0.1] * EMBEDDING_DIM, [1, 2], limit=5)
            args = conn.fetch.call_args_list[0]
            assert args[0][2] == [1, 2]
            assert args[0][3] == 5


class TestGetSentencesByNode:
    @pytest.mark.asyncio
    async def test_returns_list(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            conn.fetch.return_value = [_FakeRecord(script_id="s1", script_text="hello")]
            result = await db.get_sentences_by_node(1)
            assert isinstance(result, list)
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_passes_node_id(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            conn.fetch.return_value = []
            await db.get_sentences_by_node(42)
            args = conn.fetch.call_args_list[0]
            assert args[0][1] == 42


class TestSearchSimilar:
    @pytest.mark.asyncio
    async def test_uses_cosine_distance(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            conn.fetch.return_value = []
            await db.search_similar([0.1] * EMBEDDING_DIM, node_id=1, query_bitmask=3)
            calls = [str(c) for c in conn.fetch.call_args_list]
            assert any("<=>" in c for c in calls)

    @pytest.mark.asyncio
    async def test_applies_bitmask_filter(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            conn.fetch.return_value = []
            await db.search_similar([0.1] * EMBEDDING_DIM, node_id=1, query_bitmask=3)
            calls = [str(c) for c in conn.fetch.call_args_list]
            assert any("bg_bitmask_int" in c for c in calls)

    @pytest.mark.asyncio
    async def test_passes_node_id_bitmask_limit(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            conn.fetch.return_value = []
            await db.search_similar([0.1] * EMBEDDING_DIM, node_id=7, query_bitmask=15, limit=25)
            args = conn.fetch.call_args_list[0]
            assert args[0][2] == 7
            assert args[0][3] == 15
            assert args[0][4] == 25


class TestUpsertSentences:
    @pytest.mark.asyncio
    async def test_inserts_sentence(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            sentences = [{"script_id": "s1", "node_id": 1, "script_text": "你好", "embedding": [0.1] * EMBEDDING_DIM}]
            await db.upsert_sentences(sentences)
            assert conn.executemany.call_count > 0

    @pytest.mark.asyncio
    async def test_uses_on_conflict(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            sentences = [{"script_id": "s1", "node_id": 1, "script_text": "你好", "embedding": [0.0] * EMBEDDING_DIM}]
            await db.upsert_sentences(sentences)
            calls = [str(c) for c in conn.executemany.call_args_list]
            assert any("ON CONFLICT" in c.upper() for c in calls)

    @pytest.mark.asyncio
    async def test_empty_list_noop(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            await db.upsert_sentences([])
            assert conn.executemany.call_count == 0

    @pytest.mark.asyncio
    async def test_passes_sentence_params(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            sentences = [{"script_id": "s1", "node_id": 2, "script_text": "hello", "bg_bitmask_int": 7, "win_rate": 0.9, "sas": 0.8, "embedding": [0.1] * EMBEDDING_DIM}]
            await db.upsert_sentences(sentences)
            args = conn.executemany.call_args_list[0]
            row = args[0][1][0]
            assert row[0] == "s1"
            assert row[1] == 2
            assert row[2] == "hello"
            assert row[3] == 7
            assert row[4] == 0.9
            assert row[5] == 0.8

    @pytest.mark.asyncio
    async def test_no_embedding_passes_none(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            sentences = [{"script_id": "s1", "node_id": 1, "script_text": "hello"}]
            await db.upsert_sentences(sentences)
            args = conn.executemany.call_args_list[0]
            row = args[0][1][0]
            assert row[8] is None


class TestGetVectors:
    @pytest.mark.asyncio
    async def test_returns_mapping(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            conn.fetch.return_value = [_FakeRecord(script_id="s1", embedding=np.array([0.1] * EMBEDDING_DIM, dtype=np.float32))]
            result = await db.get_vectors(["s1"])
            assert "s1" in result
            assert isinstance(result["s1"], list)

    @pytest.mark.asyncio
    async def test_empty_list_returns_empty(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            result = await db.get_vectors([])
            assert result == {}
            assert conn.fetch.call_count == 0

    @pytest.mark.asyncio
    async def test_none_embedding_returns_zeros(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            conn.fetch.return_value = [_FakeRecord(script_id="s1", embedding=None)]
            result = await db.get_vectors(["s1"])
            assert result["s1"] == [0.0] * EMBEDDING_DIM


class TestKeywordSearch:
    @pytest.mark.asyncio
    async def test_empty_query_returns_empty(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            result = await db.keyword_search("")
            assert result == []
            assert conn.fetch.call_count == 0

    @pytest.mark.asyncio
    async def test_uses_tsvector(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            conn.fetch.return_value = []
            await db.keyword_search("financial hardship")
            calls = [str(c) for c in conn.fetch.call_args_list]
            assert any("tsv" in c.lower() or "tsquery" in c.lower() for c in calls)

    @pytest.mark.asyncio
    async def test_falls_back_to_trigram(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            conn.fetch.side_effect = [[], [_FakeRecord(script_id="s1", script_text="hello", rank=0.5)]]
            await db.keyword_search("financial hardship")
            assert conn.fetch.call_count == 2
            second_call = str(conn.fetch.call_args_list[1])
            assert "similarity" in second_call


class TestTaxonomyKeywordSearch:
    @pytest.mark.asyncio
    async def test_empty_query_returns_empty(self):
        pool, conn = _make_mock_pool()
        with _patch_create_pool(pool):
            db = AsyncSentenceDB("postgresql://localhost/test")
            await db.connect()
            result = await db.taxonomy_keyword_search("")
            assert result == []
            assert conn.fetch.call_count == 0


class TestRowToDict:
    def test_converts_nan_vec_score_to_zero(self):
        record = _FakeRecord(vec_score=float("nan"), script_id="s1")
        result = _row_to_dict(record)
        assert result["vec_score"] == 0.0

    def test_converts_ndarray_to_list(self):
        arr = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        record = _FakeRecord(embedding=arr, script_id="s1")
        result = _row_to_dict(record)
        assert isinstance(result["embedding"], list)
        assert len(result["embedding"]) == 3
        for a, b in zip(result["embedding"], [0.1, 0.2, 0.3], strict=True):
            assert abs(a - b) < 1e-5

    def test_converts_numpy_float_to_float(self):
        record = _FakeRecord(win_rate=np.float32(0.5), script_id="s1")
        result = _row_to_dict(record)
        assert isinstance(result["win_rate"], float)

    def test_converts_numpy_int_to_float(self):
        record = _FakeRecord(bg_bitmask_int=np.int64(7), script_id="s1")
        result = _row_to_dict(record)
        assert isinstance(result["bg_bitmask_int"], float)

    def test_preserves_normal_floats(self):
        record = _FakeRecord(vec_score=0.95, script_id="s1")
        result = _row_to_dict(record)
        assert result["vec_score"] == 0.95
