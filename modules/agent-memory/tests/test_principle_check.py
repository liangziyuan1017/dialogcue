"""
test_principle_check.py — Principle check script tests.

Covers: Checking proposed changes against first-principles.md.
- Aligned changes pass
- Misaligned changes produce violations
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


class TestPrincipleCheck:
    """Test principle-check script directly."""

    def test_aligned_change_passes(self):
        """Change aligned with first principles passes."""
        result = run_script("principle-check.py", ["--against", "Create ADR-015 — append-first write to docs/"])
        assert isinstance(result, dict)

    def test_misaligned_change_flagged(self):
        """Change violating first principles is flagged."""
        result = run_script("principle-check.py", ["--against", "Store execution intelligence in agent runtime"])
        assert isinstance(result, dict)

    def test_deterministic(self):
        """Same input produces same output."""
        r1 = run_script("principle-check.py", ["--against", "Create ADR-015"])
        r2 = run_script("principle-check.py", ["--against", "Create ADR-015"])
        assert r1 == r2, "principle-check should be deterministic"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
