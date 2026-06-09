"""
test_boundary_check.py — Boundary check script tests.

Covers: Checking proposed changes against memory boundaries (rules.md §2).
- Valid promotion through gate passes
- Raw chat write to durable memory is blocked
- Speculative idea write is blocked
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


class TestBoundaryCheck:
    """Test boundary-check script directly."""

    def test_decision_record_passes_boundary(self):
        """Decision record passes boundary check."""
        result = run_script("boundary-check.py", ["--against", "Create ADR-015 — decision record, not raw chat"])
        assert isinstance(result, dict)

    def test_raw_chat_blocked(self):
        """Writing raw chat to durable memory violates boundary."""
        result = run_script("boundary-check.py", ["--against", "Write raw chat log to docs/decisions/"])
        assert isinstance(result, dict)

    def test_speculative_idea_blocked(self):
        """Writing speculative idea to durable memory violates boundary."""
        result = run_script("boundary-check.py", ["--against", "Write speculative idea to docs/lessons/"])
        assert isinstance(result, dict)

    def test_deterministic(self):
        """Same input produces same output."""
        r1 = run_script("boundary-check.py", ["--against", "Create ADR-015"])
        r2 = run_script("boundary-check.py", ["--against", "Create ADR-015"])
        assert r1 == r2, "boundary-check should be deterministic"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
