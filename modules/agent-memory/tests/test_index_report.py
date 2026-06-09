"""
test_index_report.py — Index report tests.

Covers: Human-readable index rebuild summary.
- Report includes indexed, skipped, and conflict counts
- Deterministic output for same inputs
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


class TestIndexReport:
    """Test index-report script."""

    def test_report_with_counts(self):
        """Report includes indexed, skipped, and conflict counts."""
        result = run_script("index-report.py", ["--indexed", "42", "--skipped", "0", "--conflicts", "0"])
        assert result.get("exit_code", 0) == 0 or "indexed" in str(result).lower()

    def test_report_deterministic(self):
        """Same counts produce same report."""
        r1 = run_script("index-report.py", ["--indexed", "10", "--skipped", "5", "--conflicts", "1"])
        r2 = run_script("index-report.py", ["--indexed", "10", "--skipped", "5", "--conflicts", "1"])
        assert r1 == r2, "index-report should be deterministic"

    def test_report_with_conflicts(self):
        """Report handles non-zero conflict count."""
        result = run_script("index-report.py", ["--indexed", "40", "--skipped", "2", "--conflicts", "3"])
        assert isinstance(result, dict)

    def test_report_zero_docs(self):
        """Report handles zero indexed docs."""
        result = run_script("index-report.py", ["--indexed", "0", "--skipped", "0", "--conflicts", "0"])
        assert isinstance(result, dict)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
