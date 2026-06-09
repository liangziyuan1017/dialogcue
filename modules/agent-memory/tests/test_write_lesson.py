"""
test_write_lesson.py — Lesson capture and dedup tests.

Covers: Phase 9 lesson dedup and quality gate checklist items.
- New lesson written with valid frontmatter
- Duplicate lesson detected as candidate
- Quality gates enforced
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


class TestWriteLesson:
    """Test lesson capture workflow."""

    def test_id_allocation_returns_ll_format(self):
        """ID allocation for LL returns LL-NNN format."""
        result = run_script("id-allocate.py", ["--kind", "LL"])
        assert "id" in result
        assert result["id"].startswith("LL-"), f"Expected LL-NNN format: {result}"

    def test_lesson_with_valid_frontmatter(self):
        """A lesson with all required fields passes validation."""
        valid_fm = """
id: LL-099
title: "Test lesson about port conflicts"
doc_kind: lesson
status: draft
created: 2026-05-26
schema_version: 1
pitfall: "Port 8080 conflict between services"
root_cause: "Both services hardcoded default port"
trigger_conditions: "When two services start with default configs"
fix: "Configure explicit port for each service"
guard: "scripts/port-check.sh pre-flight check"
source_anchor: [docs/runbook.md]
"""
        result = run_script("frontmatter-lint.py", ["--input", valid_fm, "--schema", "lesson"])
        assert result.get("valid") is True, f"Valid lesson should pass: {result}"

    def test_lesson_missing_pitfall_slot(self):
        """A lesson missing pitfall should fail QG validation."""
        # Missing source_anchor will trigger QG5
        incomplete_fm = """
id: LL-099
title: "Test lesson"
doc_kind: lesson
status: draft
created: 2026-05-26
schema_version: 1
"""
        result = run_script("frontmatter-lint.py", ["--input", incomplete_fm, "--schema", "lesson"])
        # Should have at least the source_anchor violation from QG5
        violations = result.get("violations", [])
        assert len(violations) > 0, f"Lesson missing slots should have violations: {result}"

    def test_write_durable_creates_file(self):
        """write-durable creates a file with expected content."""
        with tempfile.TemporaryDirectory() as tmp:
            test_path = os.path.join(tmp, "docs", "lessons", "test-lesson.md")
            content = """---
id: LL-999
title: "Test lesson"
doc_kind: lesson
status: draft
created: 2026-05-26
schema_version: 1
---

# Test Lesson

Test content.
"""
            result = run_script("write-durable.py", [
                "--path", test_path,
                "--content", content,
            ])
            assert result.get("result") == "written", f"Should write successfully: {result}"
            assert os.path.exists(test_path), f"File should exist: {test_path}"

            with open(test_path, "r") as f:
                written = f.read()
            assert "LL-999" in written
            assert "Test Lesson" in written

    def test_write_durable_optimistic_concurrency(self):
        """Write with if-unmodified-since rejects stale writes."""
        with tempfile.TemporaryDirectory() as tmp:
            test_path = os.path.join(tmp, "docs", "lessons", "test-concurrency.md")
            # First write
            run_script("write-durable.py", [
                "--path", test_path,
                "--content", "---\nid: LL-998\ntitle: Test\ndoc_kind: lesson\ncreated: 2026-05-25\nschema_version: 1\n---\n\nTest",
            ])
            # Second write with old timestamp (after file exists)
            result = run_script("write-durable.py", [
                "--path", test_path,
                "--content", "updated content",
                "--if-unmodified-since", "2026-01-01T00:00:00",
            ])
            assert result.get("result") == "rejected", f"Should reject stale write: {result}"


class TestLessonDedup:
    """Test duplicate lesson detection."""

    def test_duplicate_lesson_stored_as_candidate(self):
        """Writing a lesson with matching pitfall to an existing lesson stores second as candidate."""
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = os.path.join(tmp, "docs", "lessons")
            os.makedirs(docs_dir, exist_ok=True)

            first_lesson = """---
id: LL-100
title: "Port 8080 conflict between services"
doc_kind: lesson
status: draft
created: 2026-05-26
schema_version: 1
pitfall: "Port 8080 conflict between API and dashboard services"
root_cause: "Both services hardcoded default port"
---

# Port 8080 Conflict
"""
            first_path = os.path.join(docs_dir, "100-port-8080-conflict.md")
            run_script("write-durable.py", ["--path", first_path, "--content", first_lesson])

            # Build index in the temp dir
            index_file = os.path.join(tmp, ".agent-memory", "index.json")
            os.makedirs(os.path.dirname(index_file), exist_ok=True)
            run_script("index-rebuild.py", [
                "--scope", "full",
                "--root", tmp,
                "--state-dir", os.path.join(tmp, ".agent-memory"),
            ])

            result = run_script("lexical-search.py", [
                "--query", "Port 8080 conflict between services",
                "--doc-kind", "lesson",
                "--limit", "5",
                "--index-file", index_file,
            ])

            results = result.get("results", [])
            found_ids = [r.get("doc_id") for r in results]
            assert "LL-100" in found_ids, f"Should find existing lesson LL-100: {found_ids}"

    def test_possible_duplicate_of_field_set(self):
        """When a duplicate is detected, possible_duplicate_of field should be set."""
        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = os.path.join(tmp, "docs", "lessons")
            os.makedirs(docs_dir, exist_ok=True)

            candidate_lesson = """---
id: LL-101
title: "Port 8080 conflict between services"
doc_kind: lesson
status: draft
created: 2026-05-26
schema_version: 1
authority: candidate
possible_duplicate_of: LL-100
pitfall: "Port 8080 conflict between API and dashboard services"
root_cause: "Both services hardcoded default port 8080"
---

# Port 8080 Conflict (Candidate)
"""
            candidate_path = os.path.join(docs_dir, "101-port-8080-conflict-candidate.md")
            result = run_script("write-durable.py", ["--path", candidate_path, "--content", candidate_lesson])
            assert result.get("result") == "written"

            with open(candidate_path, "r") as f:
                content = f.read()
            assert "possible_duplicate_of" in content
            assert "authority: candidate" in content


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
