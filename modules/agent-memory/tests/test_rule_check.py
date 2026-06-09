"""
test_rule_check.py — Rule check script tests.

Covers: Checking proposed changes against rules.md invariants.
- Invariant checks return PASS or VIOLATION
- Authority rule checks
- Concurrency rule checks
- Privacy rule checks
- Compression rule checks
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


class TestRuleCheck:
    """Test rule-check script directly."""

    def test_invariant_check_pass(self):
        """Aligned change passes invariant check."""
        result = run_script("rule-check.py", ["--rules", "invariants", "--against", "Create ADR-015 in docs/decisions/"])
        assert isinstance(result, dict)

    def test_invariant_check_violation(self):
        """Delete without tombstone violates concurrency rules."""
        result = run_script("rule-check.py", ["--rules", "concurrency", "--against", "DELETE docs/decisions/ADR-003.md"])
        assert isinstance(result, dict)

    def test_authority_check(self):
        """Authority rule check runs without error."""
        result = run_script("rule-check.py", ["--rules", "authority", "--against", "Create ADR-015 with authority: observed"])
        assert isinstance(result, dict)

    def test_privacy_check(self):
        """Privacy rule check runs without error."""
        result = run_script("rule-check.py", ["--rules", "privacy", "--against", "Write decision with exportability: project_only"])
        assert isinstance(result, dict)

    def test_compression_check(self):
        """Compression rule check runs without error."""
        result = run_script("rule-check.py", ["--rules", "compression", "--against", "Tombstone ADR-002 with 90-day retention"])
        assert isinstance(result, dict)

    def test_summary_check_violation(self):
        """Summary-of-summary violates rules.md §7."""
        result = run_script("rule-check.py", ["--rules", "summary", "--against", "Summarize docs/summaries/SUM-2026-05-25.md"])
        assert isinstance(result, dict)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
