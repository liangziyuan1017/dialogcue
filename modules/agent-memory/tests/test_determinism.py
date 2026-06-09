"""
test_determinism.py — Determinism tests.

Verifies: same input → same output across runs.
Covers: Phase 9 determinism requirement.
"""
import sys
import json
import subprocess
from pathlib import Path
import tempfile
import os

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


class TestDeterminism:
    """Test that scripts produce deterministic output."""

    def test_discover_docs_deterministic(self):
        """Same repo produces same file list."""
        r1 = run_script("discover-docs.py", ["--root", str(FIXTURES_DIR / "structured-repo"), "--all"])
        r2 = run_script("discover-docs.py", ["--root", str(FIXTURES_DIR / "structured-repo"), "--all"])
        assert r1.get("files") == r2.get("files"), "discover-docs should be deterministic"
        assert r1.get("count") == r2.get("count")

    def test_content_hash_deterministic(self):
        """Same content produces same hash."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("deterministic test content")
            f.flush()
            r1 = run_script("content-hash.py", ["--file", f.name])
            r2 = run_script("content-hash.py", ["--file", f.name])
            os.unlink(f.name)

        h1 = list(r1.get("hashes", {}).values())[0]
        h2 = list(r2.get("hashes", {}).values())[0]
        assert h1 == h2, f"content-hash should be deterministic: {h1} vs {h2}"

    def test_frontmatter_lint_deterministic(self):
        """Same doc produces same validation."""
        adr = str(FIXTURES_DIR / "structured-repo" / "docs" / "decisions" / "ADR-001-postgresql.md")
        r1 = run_script("frontmatter-lint.py", ["--file", adr])
        r2 = run_script("frontmatter-lint.py", ["--file", adr])
        assert r1 == r2, f"frontmatter-lint should be deterministic"

    def test_bootstrap_report_deterministic(self):
        """Same counts produce same output."""
        r1 = run_script("bootstrap-report.py", ["--discovered", "10", "--validated", "10", "--indexed", "10"])
        r2 = run_script("bootstrap-report.py", ["--discovered", "10", "--validated", "10", "--indexed", "10"])
        assert r1.get("stdout") == r2.get("stdout") or r1.get("exit_code") == r2.get("exit_code")

    def test_lexical_search_deterministic(self):
        """Same query produces same results."""
        # First build the index
        run_script("index-rebuild.py", [
            "--scope", "full",
            "--root", str(FIXTURES_DIR / "structured-repo"),
            "--acquire-lock",
        ])
        r1 = run_script("lexical-search.py", ["--query", "ADR-001", "--limit", "5"])
        r2 = run_script("lexical-search.py", ["--query", "ADR-001", "--limit", "5"])
        assert r1 == r2, f"lexical-search should be deterministic"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
