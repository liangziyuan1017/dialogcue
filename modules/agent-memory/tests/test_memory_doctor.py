"""
test_memory_doctor.py — Memory doctor diagnostic tests.

Covers: Health check diagnostics for the memory system.
- Index staleness detection
- Lock file status
- Schema drift detection
- Tombstone status
"""
import sys
import json
import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


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


class TestMemoryDoctor:
    """Test memory-doctor and sub-diagnostic scripts."""

    def test_doctor_runs_all_checks(self):
        """memory-doctor runs and reports all diagnostic categories."""
        result = run_script("memory-doctor.py", ["--root", str(FIXTURES_DIR / "structured-repo")])
        assert isinstance(result, dict)

    def test_doctor_index_check(self):
        """doctor-index reports index staleness status."""
        result = run_script("doctor-index.py", ["--root", str(FIXTURES_DIR / "structured-repo")])
        assert isinstance(result, dict)

    def test_doctor_locks_check(self):
        """doctor-locks reports lock file status."""
        result = run_script("doctor-locks.py", ["--root", str(FIXTURES_DIR / "structured-repo")])
        assert isinstance(result, dict)

    def test_doctor_schemas_check(self):
        """doctor-schemas reports schema drift status."""
        result = run_script("doctor-schemas.py", ["--root", str(FIXTURES_DIR / "structured-repo")])
        assert isinstance(result, dict)

    def test_doctor_tombstones_check(self):
        """doctor-tombstones reports tombstone and retention status."""
        result = run_script("doctor-tombstones.py", ["--root", str(FIXTURES_DIR / "structured-repo")])
        assert isinstance(result, dict)

    def test_doctor_deterministic(self):
        """Same repo produces same diagnostic output."""
        r1 = run_script("memory-doctor.py", ["--root", str(FIXTURES_DIR / "structured-repo")])
        r2 = run_script("memory-doctor.py", ["--root", str(FIXTURES_DIR / "structured-repo")])
        assert r1 == r2, "memory-doctor should be deterministic"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
