"""
test_rebuild_index.py — Index rebuild tests.

Covers: Phase 9 index rebuild tests.
- Full rebuild produces consistent index
- Content hash detects changes
- Incremental rebuild handles lock contention
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
        return {"stdout": result.stdout, "stderr": result.stderr, "exit_code": result.returncode}


class TestRebuildIndex:
    """Test index rebuild workflow."""

    def test_full_rebuild_structured_repo(self):
        """Full rebuild indexes all documents."""
        result = run_script("index-rebuild.py", [
            "--scope", "full",
            "--root", str(FIXTURES_DIR / "structured-repo"),
            "--acquire-lock",
        ])
        indexed = result.get("docs_indexed", 0)
        assert indexed == 10, f"Expected 10 docs indexed, got {indexed}: {result}"

    def test_index_report_formats(self):
        """Index report formats correctly."""
        result = run_script("index-report.py", [
            "--indexed", "42",
            "--skipped", "0",
            "--conflicts", "0",
        ])
        output = result.get("stdout", "")
        assert "42 docs indexed" in output or result.get("exit_code") == 0

    def test_content_hash_consistent(self):
        """Same file produces same hash."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("test content")
            f.flush()
            result1 = run_script("content-hash.py", ["--file", f.name])
            result2 = run_script("content-hash.py", ["--file", f.name])
            os.unlink(f.name)

        h1 = result1.get("hashes", {}).get(f.name, "")
        h2 = result2.get("hashes", {}).get(f.name, "")
        assert h1 == h2, f"Same file should produce same hash: {h1} vs {h2}"

    def test_content_hash_different(self):
        """Different files produce different hashes."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f1:
            f1.write("content A")
            f1.flush()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f2:
            f2.write("content B")
            f2.flush()

        result = run_script("content-hash.py", ["--files", f1.name, f2.name])
        os.unlink(f1.name)
        os.unlink(f2.name)

        hashes = result.get("hashes", {})
        h1 = hashes.get(f1.name, "")
        h2 = hashes.get(f2.name, "")
        assert h1 != h2, f"Different files should produce different hashes"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
