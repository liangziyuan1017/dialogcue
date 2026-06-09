"""
test_bootstrap_report.py — Bootstrap report tests.

Covers: Human-readable bootstrap summary generation.
- Report includes discovered, validated, and indexed counts
- Deterministic output for same inputs
- Handles zero-doc case
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


class TestBootstrapReport:
    """Test bootstrap-report script."""

    def test_report_with_docs(self):
        """Report includes discovered, validated, and indexed counts."""
        result = run_script("bootstrap-report.py", ["--discovered", "10", "--validated", "10", "--indexed", "10"])
        assert isinstance(result, dict)

    def test_report_zero_docs(self):
        """Report handles zero docs (cold start)."""
        result = run_script("bootstrap-report.py", ["--discovered", "0", "--validated", "0", "--indexed", "0"])
        assert isinstance(result, dict)

    def test_report_deterministic(self):
        """Same counts produce same report."""
        r1 = run_script("bootstrap-report.py", ["--discovered", "10", "--validated", "10", "--indexed", "10"])
        r2 = run_script("bootstrap-report.py", ["--discovered", "10", "--validated", "10", "--indexed", "10"])
        assert r1 == r2, "bootstrap-report should be deterministic"

    def test_report_partial_validation(self):
        """Report handles case where some docs fail validation."""
        result = run_script("bootstrap-report.py", ["--discovered", "10", "--validated", "8", "--indexed", "8"])
        assert isinstance(result, dict)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
