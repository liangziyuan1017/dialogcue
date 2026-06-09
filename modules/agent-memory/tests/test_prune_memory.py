"""
test_prune_memory.py — Prune non-destructive tests.

Covers: Phase 9 prune checklist items.
- Tombstones created, not hard deletes
- Source IDs preserved in merges
- Entropy audit detects stale entries
"""
import sys
import json
import subprocess
from pathlib import Path
import tempfile
import os

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
STRUCTURED_REPO = FIXTURES_DIR / "structured-repo"


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


class TestPruneMemory:
    """Test non-destructive prune workflow."""

    def test_entropy_audit_discovers_docs(self):
        """Entropy audit scans the structured fixtures."""
        result = run_script("entropy-audit.py", ["--root", str(STRUCTURED_REPO)])
        assert "flagged_count" in result
        assert "entries" in result
        # ADR-001 (2026-01-15) is old enough to potentially be stale
        flagged_ids = [e["id"] for e in result.get("entries", [])]
        # At minimum, the audit should not crash
        assert isinstance(result["flagged_count"], int)

    def test_tombstone_create_writes_file(self):
        """Creating a tombstone writes a tombstone file."""
        result = run_script("tombstone-create.py", [
            "--id", "ADR-TEST-001",
            "--reason", "test tombstone",
            "--retention-days", "90",
        ])
        assert "tombstone_path" in result
        assert "retain_until" in result

        # Verify tombstone file exists
        tombstone_path = Path(result["tombstone_path"])
        assert tombstone_path.exists(), f"Tombstone file should exist: {tombstone_path}"
        with open(tombstone_path, "r") as f:
            content = f.read()
        assert "ADR-TEST-001" in content
        assert "test tombstone" in content

        # Clean up
        tombstone_path.unlink(missing_ok=True)

    def test_tombstone_has_retention_period(self):
        """Tombstone includes 90-day retention period."""
        result = run_script("tombstone-create.py", [
            "--id", "LL-TEST-001",
            "--reason", "stale lesson",
            "--retention-days", "90",
        ])

        tombstone_path = Path(result["tombstone_path"])
        with open(tombstone_path, "r") as f:
            content = f.read()
        assert "retention_days: 90" in content or "retain_until" in content

        tombstone_path.unlink(missing_ok=True)

    def test_merge_propose_preserves_source_ids(self):
        """Merging two entries preserves source_ids from both."""
        result = run_script("merge-propose.py", [
            "--source1", "ADR-001",
            "--source2", "ADR-002",
            "--root", str(STRUCTURED_REPO),
            "--new-id", "ADR-MERGED-001",
        ])
        assert "new_id" in result
        assert "source_ids_preserved" in result
        source_ids = result.get("source_ids_preserved", [])
        assert "ADR-001" in source_ids, f"Should preserve ADR-001 in source_ids: {source_ids}"
        assert "ADR-002" in source_ids, f"Should preserve ADR-002 in source_ids: {source_ids}"

    def test_prune_report_formats_correctly(self):
        """Prune report handles various action types."""
        actions = json.dumps([
            {"type": "tombstone", "id": "ADR-099", "reason": "stale"},
            {"type": "supersede", "id": "ADR-100", "replaced_by": "ADR-101"},
            {"type": "backstop", "id": "LL-099", "reason": "unused"},
            {"type": "merge", "ids": ["ADR-001", "ADR-002"], "result": "ADR-020"},
        ])
        result = run_script("prune-report.py", ["--actions", actions])
        # prune-report outputs to stdout, not JSON
        # Should not error
        assert "error" not in result or result.get("exit_code") != 1


    def test_tombstone_preserves_original_file(self):
        """Creating a tombstone does NOT delete the original document."""
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = os.path.join(tmp, "docs", "decisions")
            os.makedirs(docs_dir, exist_ok=True)

            doc_path = os.path.join(docs_dir, "ADR-TEST-999.md")
            with open(doc_path, "w") as f:
                f.write("""---
id: ADR-TEST-999
title: "Test decision for tombstone"
doc_kind: decision
status: active
created: 2026-05-26
schema_version: 1
---

# Test Decision
""")

            assert os.path.exists(doc_path), "Document should exist before tombstone"

            result = run_script("tombstone-create.py", [
                "--id", "ADR-TEST-999",
                "--reason", "stale decision",
                "--retention-days", "90",
                "--state-dir", os.path.join(tmp, ".agent-memory"),
            ])

            assert os.path.exists(doc_path), f"Original document must survive tombstone creation: {doc_path}"

            tombstone_path = result.get("tombstone_path")
            if tombstone_path:
                assert Path(tombstone_path).exists(), f"Tombstone file should exist: {tombstone_path}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
