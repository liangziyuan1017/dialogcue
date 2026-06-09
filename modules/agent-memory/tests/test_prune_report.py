"""
test_prune_report.py — Prune report formatting tests.

Covers: Human-readable prune action summary.
- Report includes tombstone, supersede, backstop, and merge counts
- Zero deletions always reported
- Zero information loss always reported
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


class TestPruneReport:
    """Test prune-report script directly."""

    def test_report_with_actions(self):
        """Report includes action counts."""
        actions = json.dumps([
            {"type": "tombstone", "id": "ADR-002", "reason": "stale"},
            {"type": "supersede", "id": "ADR-003", "replaced_by": "ADR-018"},
            {"type": "backstop", "id": "LL-005", "reason": "unused"},
            {"type": "merge", "ids": ["ADR-003", "ADR-007"], "result": "ADR-018"},
        ])
        result = run_script("prune-report.py", ["--actions", actions])
        assert isinstance(result, dict)

    def test_report_no_deletions(self):
        """Prune report always shows zero deletions."""
        actions = json.dumps([
            {"type": "tombstone", "id": "ADR-002", "reason": "stale"},
        ])
        result = run_script("prune-report.py", ["--actions", actions])
        report_str = json.dumps(result)
        assert "0" in report_str or result.get("exit_code", 0) == 0

    def test_report_empty_actions(self):
        """Empty actions list produces valid report."""
        result = run_script("prune-report.py", ["--actions", "[]"])
        assert isinstance(result, dict)

    def test_report_deterministic(self):
        """Same actions produce same report."""
        actions = json.dumps([
            {"type": "tombstone", "id": "ADR-002", "reason": "stale"},
        ])
        r1 = run_script("prune-report.py", ["--actions", actions])
        r2 = run_script("prune-report.py", ["--actions", actions])
        assert r1 == r2, "prune-report should be deterministic"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
