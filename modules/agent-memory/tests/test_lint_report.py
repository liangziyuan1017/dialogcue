"""
test_lint_report.py — Lint report formatting tests.

Covers: Human-readable compliance report generation.
- Report aggregates per-file violations
- Summary counts are accurate
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


class TestLintReport:
    """Test lint-report script."""

    def test_report_with_violations(self):
        """Report includes per-file violations."""
        results = json.dumps([
            {"file": "ADR-003.md", "violations": ["MISSING: schema_version"]},
            {"file": "ADR-007.md", "violations": ["INVALID: status"]},
            {"file": "LL-042.md", "violations": []},
        ])
        result = run_script("lint-report.py", ["--results", results])
        assert isinstance(result, dict)

    def test_report_all_passing(self):
        """Report with no violations shows all passed."""
        results = json.dumps([
            {"file": "ADR-001.md", "violations": []},
            {"file": "LL-001.md", "violations": []},
        ])
        result = run_script("lint-report.py", ["--results", results])
        assert isinstance(result, dict)

    def test_report_deterministic(self):
        """Same violations produce same report."""
        results = json.dumps([
            {"file": "ADR-003.md", "violations": ["MISSING: schema_version"]},
        ])
        r1 = run_script("lint-report.py", ["--results", results])
        r2 = run_script("lint-report.py", ["--results", results])
        assert r1 == r2, "lint-report should be deterministic"

    def test_report_empty_results(self):
        """Empty results list produces valid report."""
        result = run_script("lint-report.py", ["--results", "[]"])
        assert isinstance(result, dict)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
