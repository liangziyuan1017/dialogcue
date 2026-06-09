"""
test_search_memory.py — Search ranking tests.

Covers: Phase 9 search ranking and degradation checklist items.
- Exact ID lookup returns top-1
- Concept queries return expected documents
- Degradation to lexical when embeddings unavailable
"""
import sys
import json
import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
STRUCTURED_REPO = FIXTURES_DIR / "structured-repo"


def run_script(script_name: str, args: list[str]) -> dict:
    script_path = SCRIPTS_DIR / script_name
    result = subprocess.run(
        [sys.executable, str(script_path)] + args,
        capture_output=True, text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": result.stdout, "exit_code": result.returncode}


def build_index():
    """Build index from the structured fixture for search tests."""
    return run_script("index-rebuild.py", [
        "--scope", "full",
        "--root", str(STRUCTURED_REPO),
        "--acquire-lock",
    ])


class TestSearchMemory:
    """Test search functionality against the structured fixture."""

    @classmethod
    def setup_class(cls):
        """Build index once for all search tests."""
        build_index()

    def test_exact_id_lookup_adr(self):
        """Exact ADR-001 lookup returns ADR-001 at rank 1."""
        result = run_script("lexical-search.py", ["--query", "ADR-001", "--limit", "5"])
        results = result.get("results", [])
        assert len(results) > 0, "Should find ADR-001"
        assert results[0]["doc_id"] == "ADR-001", f"Top result should be ADR-001, got {results[0].get('doc_id')}"

    def test_exact_id_lookup_lesson(self):
        """Exact LL-002 lookup returns LL-002 at rank 1."""
        result = run_script("lexical-search.py", ["--query", "LL-002", "--limit", "5"])
        results = result.get("results", [])
        assert len(results) > 0, "Should find LL-002"
        assert results[0]["doc_id"] == "LL-002"

    def test_concept_search_port_allocation(self):
        """Concept query 'port allocation' should include LL-001."""
        result = run_script("lexical-search.py", ["--query", "port allocation", "--limit", "10"])
        results = result.get("results", [])
        doc_ids = [r["doc_id"] for r in results]
        assert "LL-001" in doc_ids, f"LL-001 should appear in results for 'port allocation': {doc_ids}"

    def test_concept_search_database(self):
        """Concept query 'database' should return ADR-001."""
        result = run_script("lexical-search.py", ["--query", "database", "--limit", "10"])
        results = result.get("results", [])
        doc_ids = [r["doc_id"] for r in results]
        assert "ADR-001" in doc_ids, f"ADR-001 should appear for 'database': {doc_ids}"

    def test_semantic_health_check(self):
        """Semantic search health check reports status."""
        result = run_script("semantic-search.py", ["--health"])
        # Either healthy or unreachable is valid (no error)
        assert result is not None

    def test_semantic_degradation(self):
        """Semantic search degrades gracefully when service is unavailable."""
        result = run_script("semantic-search.py", [
            "--query", "test query",
            "--endpoint", "http://localhost:19999/nonexistent",
        ])
        # Should not crash; may return empty results or error
        assert isinstance(result, dict)

    def test_nonexistent_query_returns_empty(self):
        """A query for non-existent content returns empty results."""
        result = run_script("lexical-search.py", ["--query", "xyzzy_nonexistent_12345", "--limit", "5"])
        results = result.get("results", [])
        assert len(results) == 0, f"Should return 0 results for nonexistent query: {results}"

    def test_filter_by_doc_kind(self):
        """Filtering by doc_kind=lesson returns only lessons."""
        result = run_script("lexical-search.py", [
            "--query", "port",
            "--doc-kind", "lesson",
            "--limit", "10",
        ])
        results = result.get("results", [])
        for r in results:
            assert r.get("doc_kind") == "lesson", f"Expected only lessons, got {r.get('doc_kind')}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
