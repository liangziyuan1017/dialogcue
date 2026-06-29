import pytest
from unittest.mock import MagicMock, call, patch
from f007_infrastructure.db import SentenceDB
from f007_infrastructure.embeddings import EMBEDDING_DIM


@pytest.fixture
def mock_cursor():
    cursor = MagicMock()
    cursor.execute.return_value = None
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None
    return cursor


@pytest.fixture
def mock_conn(mock_cursor):
    conn = MagicMock()
    conn.cursor.return_value = mock_cursor
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    return conn


@pytest.fixture
def db(mock_conn):
    with patch("f007_infrastructure.db.psycopg2.connect", return_value=mock_conn), \
         patch("f007_infrastructure.db.register_vector"):
        db = SentenceDB("dbname=test")
        db._conn = mock_conn
        yield db


class TestCreateTables:
    def test_creates_vector_extension(self, db, mock_cursor):
        db.create_tables()
        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("vector" in c for c in calls)

    def test_creates_pg_trgm_extension(self, db, mock_cursor):
        db.create_tables()
        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("pg_trgm" in c for c in calls)

    def test_creates_nodes_table(self, db, mock_cursor):
        db.create_tables()
        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("nodes" in c and "CREATE" in c.upper() for c in calls)

    def test_creates_sentences_table(self, db, mock_cursor):
        db.create_tables()
        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("sentences" in c and "CREATE" in c.upper() for c in calls)

    def test_creates_taxonomy_keywords_table(self, db, mock_cursor):
        db.create_tables()
        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("taxonomy_keywords" in c and "CREATE" in c.upper() for c in calls)

    def test_creates_hnsw_index(self, db, mock_cursor):
        db.create_tables()
        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("hnsw" in c.lower() for c in calls)

    def test_creates_gin_tsv_index(self, db, mock_cursor):
        db.create_tables()
        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("gin" in c.lower() and "tsv" in c.lower() for c in calls)

    def test_creates_trgm_index(self, db, mock_cursor):
        db.create_tables()
        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("trgm" in c.lower() for c in calls)

    def test_idempotent(self, db, mock_cursor):
        db.create_tables()
        first_count = mock_cursor.execute.call_count
        mock_cursor.execute.reset_mock()
        db.create_tables()
        assert mock_cursor.execute.call_count == first_count


class TestUpsertNodes:
    def test_inserts_node(self, db, mock_cursor):
        nodes = [{"state_id": "initial_contact", "path_signature": "", "branch_key": {}, "parent_id": None, "depth": 0}]
        db.upsert_nodes(nodes)
        assert mock_cursor.execute.call_count > 0

    def test_uses_on_conflict(self, db, mock_cursor):
        nodes = [{"state_id": "s1", "path_signature": "p1", "branch_key": {}, "parent_id": None, "depth": 0}]
        db.upsert_nodes(nodes)
        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("ON CONFLICT" in c.upper() for c in calls)

    def test_empty_list_noop(self, db, mock_cursor):
        db.upsert_nodes([])
        assert mock_cursor.execute.call_count == 0


class TestGetNodeBySignature:
    def test_returns_dict_when_found(self, db, mock_cursor):
        mock_cursor.fetchone.return_value = {"id": 1, "state_id": "initial_contact", "path_signature": ""}
        result = db.get_node_by_signature("")
        assert result is not None
        assert result["state_id"] == "initial_contact"

    def test_returns_none_when_not_found(self, db, mock_cursor):
        mock_cursor.fetchone.return_value = None
        result = db.get_node_by_signature("nonexistent")
        assert result is None


class TestUpsertSentences:
    def test_inserts_sentence(self, db, mock_cursor):
        sentences = [{"script_id": "s1", "node_id": 1, "script_text": "你好", "bg_bitmask_int": 3, "win_rate": 0.5, "sas": 0.8, "embedding": [0.1] * EMBEDDING_DIM}]
        db.upsert_sentences(sentences)
        assert mock_cursor.execute.call_count > 0

    def test_uses_on_conflict(self, db, mock_cursor):
        sentences = [{"script_id": "s1", "node_id": 1, "script_text": "你好", "bg_bitmask_int": 0, "win_rate": 0.5, "sas": 0.8, "embedding": [0.0] * EMBEDDING_DIM}]
        db.upsert_sentences(sentences)
        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("ON CONFLICT" in c.upper() for c in calls)

    def test_empty_list_noop(self, db, mock_cursor):
        db.upsert_sentences([])
        assert mock_cursor.execute.call_count == 0


class TestGetSentencesByNode:
    def test_returns_list(self, db, mock_cursor):
        mock_cursor.fetchall.return_value = [
            {"script_id": "s1", "script_text": "hello", "bg_bitmask_int": 3, "win_rate": 0.5, "sas": 0.8}
        ]
        result = db.get_sentences_by_node(1)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_returns_empty_for_no_results(self, db, mock_cursor):
        mock_cursor.fetchall.return_value = []
        result = db.get_sentences_by_node(999)
        assert result == []


class TestSearchSimilar:
    def test_returns_list_with_vec_score(self, db, mock_cursor):
        mock_cursor.fetchall.return_value = [
            {"script_id": "s1", "script_text": "hello", "vec_score": 0.95, "win_rate": 0.8, "sas": 0.7}
        ]
        result = db.search_similar([0.1] * EMBEDDING_DIM, node_id=1, query_bitmask=3, limit=10)
        assert isinstance(result, list)
        assert "vec_score" in result[0]

    def test_uses_cosine_distance(self, db, mock_cursor):
        db.search_similar([0.1] * EMBEDDING_DIM, node_id=1, query_bitmask=3)
        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("<=>" in c for c in calls)

    def test_applies_bitmask_filter(self, db, mock_cursor):
        db.search_similar([0.1] * EMBEDDING_DIM, node_id=1, query_bitmask=3)
        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("bg_bitmask_int" in c for c in calls)

    def test_applies_limit(self, db, mock_cursor):
        db.search_similar([0.1] * EMBEDDING_DIM, node_id=1, query_bitmask=3, limit=5)
        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("LIMIT" in c.upper() or "5" in c for c in calls)


class TestKeywordSearch:
    def test_returns_list(self, db, mock_cursor):
        mock_cursor.fetchall.return_value = [
            {"script_id": "s1", "script_text": "financial hardship program", "rank": 0.5}
        ]
        result = db.keyword_search("financial hardship")
        assert isinstance(result, list)

    def test_empty_query_returns_empty(self, db, mock_cursor):
        result = db.keyword_search("")
        assert result == []
        assert mock_cursor.execute.call_count == 0

    def test_uses_tsvector(self, db, mock_cursor):
        mock_cursor.fetchall.return_value = []
        db.keyword_search("financial hardship")
        calls = [str(c) for c in mock_cursor.execute.call_args_list]
        assert any("tsv" in c.lower() or "tsquery" in c.lower() for c in calls)
