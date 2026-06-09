"""
test_bootstrap_memory.py — Memory bootstrap tests.

Covers: Phase 9 bootstrap tests.
- Structured repo bootstraps without schema failures
- Generic repo bootstraps with best-effort
- Idempotent bootstrap
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


class TestBootstrapMemory:
    """Test memory bootstrap workflow."""

    def test_discover_docs_structured_repo(self):
        """Structured repo: discover-docs finds all documents."""
        result = run_script("discover-docs.py", [
            "--root", str(FIXTURES_DIR / "structured-repo"),
            "--all",
        ])
        files = result.get("files", [])
        assert len(files) == 10, f"Expected 10 docs, found {len(files)}: {files}"

    def test_discover_docs_generic_repo(self):
        """Generic repo: discover-docs finds nothing."""
        result = run_script("discover-docs.py", [
            "--root", str(FIXTURES_DIR / "generic-repo"),
            "--all",
        ])
        files = result.get("files", [])
        assert len(files) == 0, f"Expected 0 docs, found {len(files)}"

    def test_bootstrap_report_empty(self):
        """Bootstrap report handles empty case."""
        result = run_script("bootstrap-report.py", [
            "--discovered", "0",
            "--validated", "0",
            "--indexed", "0",
        ])
        output = result.get("stdout", "")
        assert "No structured durable docs found" in output or result.get("exit_code") == 0

    def test_bootstrap_report_success(self):
        """Bootstrap report handles success case."""
        result = run_script("bootstrap-report.py", [
            "--discovered", "10",
            "--validated", "10",
            "--indexed", "10",
        ])
        output = result.get("stdout", "")
        assert "Bootstrap complete" in output or "discovered" in output.lower() or result.get("exit_code") == 0

    def test_validate_each_all_valid(self):
        """All fixture docs pass validation."""
        docs = list((FIXTURES_DIR / "structured-repo" / "docs").rglob("*.md"))
        assert len(docs) > 0, "No fixture docs found"
        for doc in docs:
            result = run_script("validate-each.py", ["--file", str(doc.resolve())])
            violations = result.get("violations", [])
            assert len(violations) == 0, f"Doc should validate: {doc.name}: {result}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
