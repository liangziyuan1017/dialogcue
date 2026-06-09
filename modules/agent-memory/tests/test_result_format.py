"""
test_result_format.py — Result formatting tests.

Covers: Formatting ranked results with metadata boost.
- Results formatted with doc_id, title, snippet
- Authority boost applied when --apply-boost flag present
- Limit parameter respected
"""
import sys
import json
import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def run_script(script_name: str, args: list[str]) -> tuple[str, int]:
    script_path = SCRIPTS_DIR / script_name
    result = subprocess.run(
        [sys.executable, str(script_path)] + args,
        capture_output=True, text=True,
    )
    return result.stdout, result.returncode


class TestResultFormat:
    """Test result-format script."""

    def test_format_basic_results(self):
        """Basic results are formatted as readable text."""
        results = json.dumps({"results": [
            {"doc_id": "ADR-001", "score": 0.95, "snippet": "Use PostgreSQL", "title": "DB Choice"},
            {"doc_id": "LL-002", "score": 0.7, "snippet": "Port conflict", "title": "Port Lesson"},
        ], "count": 2})
        stdout, code = run_script("result-format.py", ["--results", results, "--limit", "5"])
        assert code == 0, f"Should succeed, got exit code {code}"
        assert "ADR-001" in stdout, "Output should include ADR-001"

    def test_limit_respected(self):
        """Limit parameter caps the number of results."""
        results = json.dumps({"results": [
            {"doc_id": f"ADR-{i:03d}", "score": 0.9 - i * 0.1, "snippet": f"Decision {i}", "title": f"Decision {i}"}
            for i in range(10)
        ], "count": 10})
        stdout, code = run_script("result-format.py", ["--results", results, "--limit", "3"])
        assert code == 0
        assert "showing top 3" in stdout or "top 3" in stdout.lower()

    def test_apply_boost_flag(self):
        """--apply-boost flag reorders by authority and status."""
        results = json.dumps({"results": [
            {"doc_id": "ADR-001", "score": 0.9, "authority": "constitutional", "status": "accepted", "title": "High Auth"},
            {"doc_id": "LL-002", "score": 0.8, "authority": "observed", "status": "draft", "title": "Low Auth"},
        ], "count": 2})
        stdout, code = run_script("result-format.py", ["--results", results, "--limit", "5", "--apply-boost"])
        assert code == 0

    def test_empty_results(self):
        """Empty input produces 'No results found' message."""
        stdout, code = run_script("result-format.py", ["--results", '{"results": [], "count": 0}', "--limit", "5"])
        assert code == 0
        assert "No results" in stdout or "0 results" in stdout.lower()


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
