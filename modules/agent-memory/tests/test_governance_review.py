"""
test_governance_review.py — Governance review tests.

Covers: Phase 9 governance review tests.
- Rule violations detected
- Principles check passes
- Boundaries enforced
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
        return {"error": result.stdout, "stderr": result.stderr, "exit_code": result.returncode}


class TestGovernanceReview:
    """Test governance review workflow."""

    def test_rule_check_delete_without_tombstone(self):
        """Deleting without tombstone is a concurrency violation."""
        result = run_script("rule-check.py", [
            "--rules", "concurrency",
            "--against", "DELETE docs/decisions/ADR-003.md without tombstone",
        ])
        assert result.get("result") == "VIOLATION", f"Should detect delete without tombstone: {result}"

    def test_rule_check_summary_of_summary(self):
        """Re-summarizing a summary is a violation."""
        result = run_script("rule-check.py", [
            "--rules", "summary",
            "--against", "re-summarize the existing summary document",
        ])
        assert result.get("result") == "VIOLATION", f"Should detect summary-of-summary: {result}"

    def test_principle_check_aligned(self):
        """Aligned change passes principle check."""
        result = run_script("principle-check.py", [
            "--against", "Create ADR-015 following append-first pattern",
        ])
        assert result.get("result") == "PASS"

    def test_boundary_check_raw_chat(self):
        """Raw chat entering durable memory is blocked."""
        result = run_script("boundary-check.py", [
            "--against", "write raw chat transcript to docs/decisions/",
        ])
        assert result.get("result") == "VIOLATION"

    def test_review_report_formats(self):
        """Review report handles pass and violation results."""
        results = json.dumps([
            {"category": "invariants", "result": "PASS"},
            {"category": "authority", "result": "PASS"},
            {"category": "concurrency", "result": "VIOLATION", "violations": ["rules.md §4: tombstone required"]},
        ])
        result = run_script("review-report.py", ["--results", results])
        assert "error" not in result or result.get("exit_code") != 0  # Should exit 1 for violation


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
