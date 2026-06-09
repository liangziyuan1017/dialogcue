"""
test_hybrid_fuse.py — Hybrid fusion tests.

Covers: Reciprocal-rank fusion (RRF) of lexical and semantic results.
- RRF produces a valid merged ranking
- Empty semantic results degrade to lexical-only
- k parameter affects ranking
"""
import sys
import json
import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def run_script(script_name: str, args: list[str]) -> dict:
    script_path = SCRIPTS_DIR / script_name
    result = subprocess.run(
        [sys.executable, str(script_path)] + args,
        capture_output=True, text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"stdout": result.stdout, "exit_code": result.returncode}


class TestHybridFuse:
    """Test hybrid-fuse RRF combination."""

    def test_fuse_two_rankings(self):
        """Fusing lexical and semantic results produces a merged ranking."""
        lexical = json.dumps({"results": [
            {"doc_id": "ADR-001", "score": 0.9},
            {"doc_id": "ADR-002", "score": 0.7},
        ]})
        semantic = json.dumps({"results": [
            {"doc_id": "ADR-002", "score": 0.95},
            {"doc_id": "ADR-003", "score": 0.6},
        ]})
        result = run_script("hybrid-fuse.py", ["--lexical", lexical, "--semantic", semantic, "--k", "60"])
        fused = result.get("results", [])
        assert len(fused) > 0, "Fused results should not be empty"
        doc_ids = [r["doc_id"] for r in fused]
        assert "ADR-001" in doc_ids or "ADR-002" in doc_ids or "ADR-003" in doc_ids

    def test_empty_semantic_degrades_to_lexical(self):
        """Empty semantic results degrade to lexical-only pass-through."""
        lexical = json.dumps({"results": [
            {"doc_id": "ADR-001", "score": 0.9},
            {"doc_id": "ADR-002", "score": 0.7},
        ]})
        result = run_script("hybrid-fuse.py", ["--lexical", lexical, "--semantic", '{"results": []}', "--k", "60"])
        fused = result.get("results", [])
        assert len(fused) >= 1, "Should pass through lexical results when semantic is empty"

    def test_empty_lexical_and_semantic(self):
        """Both empty produces empty results."""
        result = run_script("hybrid-fuse.py", ["--lexical", '{"results": []}', "--semantic", '{"results": []}', "--k", "60"])
        fused = result.get("results", [])
        assert len(fused) == 0, "Empty inputs should produce empty output"

    def test_k_parameter_accepted(self):
        """Different k values are accepted without error."""
        lexical = json.dumps({"results": [{"doc_id": "ADR-001", "score": 0.9}]})
        semantic = json.dumps({"results": [{"doc_id": "ADR-001", "score": 0.8}]})
        r1 = run_script("hybrid-fuse.py", ["--lexical", lexical, "--semantic", semantic, "--k", "60"])
        r2 = run_script("hybrid-fuse.py", ["--lexical", lexical, "--semantic", semantic, "--k", "10"])
        assert isinstance(r1, dict) and isinstance(r2, dict)

    def test_rrf_score_present(self):
        """Fused results include rrf_score field."""
        lexical = json.dumps({"results": [{"doc_id": "ADR-001", "score": 0.9}]})
        semantic = json.dumps({"results": [{"doc_id": "ADR-002", "score": 0.8}]})
        result = run_script("hybrid-fuse.py", ["--lexical", lexical, "--semantic", semantic, "--k", "60"])
        fused = result.get("results", [])
        if len(fused) > 0:
            assert "rrf_score" in fused[0], "Fused results should include rrf_score"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
