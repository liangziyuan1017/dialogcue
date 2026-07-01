import os

import pytest

from f007_infrastructure.db import SentenceDB
from f007_infrastructure.embeddings import EMBEDDING_DIM

DSN = os.environ.get("TEST_PG_DSN", "dbname=icbc_test user=postgres")


@pytest.fixture(scope="module")
def db():
    try:
        db = SentenceDB(DSN)
        db.create_tables()
        cur = db._conn.cursor()
        cur.execute("DELETE FROM sentences")
        cur.execute("DELETE FROM nodes")
        cur.execute("DELETE FROM taxonomy_keywords")
        cur.close()
        yield db
    except Exception:
        pytest.skip("PostgreSQL not available")
    finally:
        try:
            db.close()
        except Exception:
            pass


@pytest.mark.integration
class TestIntegration:
    def test_create_tables_idempotent(self, db):
        db.create_tables()

    def test_upsert_and_get_nodes(self, db):
        nodes = [
            {"state_id": "initial_contact", "path_signature": "", "branch_key": {}, "parent_id": None, "depth": 0},
            {"state_id": "f:financial_hardship", "path_signature": "f:financial_hardship", "branch_key": {"facts": ["financial_hardship"]}, "parent_id": None, "depth": 1},
        ]
        db.upsert_nodes(nodes)
        result = db.get_node_by_signature("")
        assert result is not None
        assert result["state_id"] == "initial_contact"

    def test_upsert_and_get_sentences(self, db):
        node = db.get_node_by_signature("")
        node_id = node["id"]
        sentences = [
            {"script_id": "test_s1", "node_id": node_id, "script_text": "你好请问是本人吗", "bg_bitmask_int": 3, "win_rate": 0.8, "sas": 0.7, "embedding": [0.1] * EMBEDDING_DIM},
            {"script_id": "test_s2", "node_id": node_id, "script_text": "建议您尽快还款", "bg_bitmask_int": 1, "win_rate": 0.6, "sas": 0.5, "embedding": [0.2] * EMBEDDING_DIM},
        ]
        db.upsert_sentences(sentences)
        result = db.get_sentences_by_node(node_id)
        ids = {s["script_id"] for s in result}
        assert "test_s1" in ids
        assert "test_s2" in ids

    def test_search_similar(self, db):
        node = db.get_node_by_signature("")
        node_id = node["id"]
        query_vec = [0.1] * EMBEDDING_DIM
        results = db.search_similar(query_vec, node_id=node_id, query_bitmask=31, limit=10)
        assert len(results) > 0
        assert "vec_score" in results[0]
        assert results[0]["script_id"] == "test_s1"

    def test_search_similar_bitmask_filter(self, db):
        node = db.get_node_by_signature("")
        node_id = node["id"]
        query_vec = [0.1] * EMBEDDING_DIM
        results = db.search_similar(query_vec, node_id=node_id, query_bitmask=1, limit=10)
        ids = {r["script_id"] for r in results}
        assert "test_s1" not in ids or results[0]["bg_bitmask_int"] & 1 == results[0]["bg_bitmask_int"]

    def test_keyword_search(self, db):
        results = db.keyword_search("还款")
        assert isinstance(results, list)

    def test_keyword_search_empty(self, db):
        results = db.keyword_search("")
        assert results == []
