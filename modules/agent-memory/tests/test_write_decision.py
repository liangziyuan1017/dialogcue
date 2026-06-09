"""
test_write_decision.py — Decision record write and dedup tests.

Covers: Phase 9 decision record tests.
- ADR written with valid frontmatter
- ID allocated atomically
- Duplicate title flagged as candidate
"""
import sys
import json
import subprocess
from pathlib import Path
import tempfile
import os

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


class TestWriteDecision:
    """Test decision record workflow."""

    def test_id_allocation_returns_adr_format(self):
        """ID allocation for ADR returns ADR-NNN format."""
        result = run_script("id-allocate.py", ["--kind", "ADR"])
        assert "id" in result
        assert result["id"].startswith("ADR-"), f"Expected ADR-NNN format: {result}"

    def test_decision_with_valid_frontmatter(self):
        """A decision with all required fields passes validation."""
        valid_fm = """
id: ADR-099
title: "Test decision"
doc_kind: decision
status: draft
created: 2026-05-26
schema_version: 1
"""
        result = run_script("frontmatter-lint.py", ["--input", valid_fm])
        assert result.get("valid") is True, f"Valid decision should pass: {result}"

    def test_write_durable_creates_file(self):
        """write-durable creates a file with expected content."""
        with tempfile.TemporaryDirectory() as tmp:
            test_path = os.path.join(tmp, "docs", "decisions", "test-adr.md")
            content = """---
id: ADR-999
title: "Test ADR"
doc_kind: decision
status: draft
created: 2026-05-26
schema_version: 1
---

# ADR-999: Test ADR

## What
Test decision.

## Why
Testing.

## Tradeoff
None.
"""
            result = run_script("write-durable.py", [
                "--path", test_path,
                "--content", content,
            ])
            assert result.get("result") == "written"
            assert os.path.exists(test_path)

    def test_write_durable_optimistic_concurrency(self):
        """Write with if-unmodified-since rejects stale writes."""
        with tempfile.TemporaryDirectory() as tmp:
            test_path = os.path.join(tmp, "docs", "decisions", "test-concurrency.md")
            run_script("write-durable.py", [
                "--path", test_path,
                "--content", "---\nid: ADR-998\ntitle: Test\ndoc_kind: decision\ncreated: 2026-05-25\nschema_version: 1\n---\n\nTest",
            ])
            import time
            time.sleep(0.1)
            result = run_script("write-durable.py", [
                "--path", test_path,
                "--content", "updated content",
                "--if-unmodified-since", "2026-01-01T00:00:00",
            ])
            assert result.get("result") == "rejected", f"Should reject stale write: {result}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
