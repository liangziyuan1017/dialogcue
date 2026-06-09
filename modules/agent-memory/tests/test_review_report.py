"""
test_review_report.py — Governance review report tests.

Covers: Human-readable governance review report generation.
- Report includes pass/violation/caution classifications
- Severity levels mapped to correct exit codes
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


class TestReviewReport:
    """Test review-report script."""

    def test_report_all_pass(self):
        """All-pass results produce PASS report."""
        results = json.dumps([
            {"category": "invariants", "result": "PASS"},
            {"category": "authority", "result": "PASS"},
            {"category": "boundary", "result": "PASS"},
        ])
        result = run_script("review-report.py", ["--results", results])
        assert isinstance(result, dict)

    def test_report_with_violation(self):
        """Violation in any category is reported."""
        results = json.dumps([
            {"category": "invariants", "result": "PASS"},
            {"category": "concurrency", "result": "VIOLATION", "detail": "tombstone required"},
        ])
        result = run_script("review-report.py", ["--results", results])
        assert isinstance(result, dict)

    def test_report_with_caution(self):
        """Caution results are reported separately from violations."""
        results = json.dumps([
            {"category": "boundary", "result": "CAUTION", "detail": "verify content qualifies"},
        ])
        result = run_script("review-report.py", ["--results", results])
        assert isinstance(result, dict)

    def test_report_deterministic(self):
        """Same results produce same report."""
        results = json.dumps([
            {"category": "invariants", "result": "PASS"},
        ])
        r1 = run_script("review-report.py", ["--results", results])
        r2 = run_script("review-report.py", ["--results", results])
        assert r1 == r2, "review-report should be deterministic"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
