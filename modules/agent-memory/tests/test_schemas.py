"""
test_schemas.py — Schema validation tests.

Covers: Phase 9 schema validation checklist items.
- Required fields enforcement
- Enum value validation
- Lesson-specific quality gates
- Knowledge block validation
"""
import sys
import json
import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def run_script(script_name: str, args: list[str]) -> dict:
    """Run a script and return parsed JSON output."""
    script_path = SCRIPTS_DIR / script_name
    result = subprocess.run(
        [sys.executable, str(script_path)] + args,
        capture_output=True, text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": result.stdout, "stderr": result.stderr, "exit_code": result.returncode}


class TestSchemaValidation:
    """Test frontmatter validation against schema definitions."""

    def test_required_fields_present(self):
        """ADR-001 has all required fields and passes validation."""
        adr_path = FIXTURES_DIR / "structured-repo" / "docs" / "decisions" / "ADR-001-postgresql.md"
        result = run_script("frontmatter-lint.py", ["--file", str(adr_path)])
        assert result.get("valid") is True, f"ADR-001 should be valid: {result}"
        assert len(result.get("violations", [])) == 0

    def test_missing_required_field(self):
        """A doc missing 'id' should fail validation."""
        incomplete = """
---
title: "Missing ID"
doc_kind: decision
created: 2026-01-01
schema_version: 1
---
"""
        result = run_script("frontmatter-lint.py", ["--input", incomplete])
        assert result.get("valid") is False
        assert any("MISSING: id" in v for v in result.get("violations", []))

    def test_invalid_doc_kind(self):
        """An invalid doc_kind should be caught."""
        invalid = """
---
id: ADR-099
title: "Test"
doc_kind: invalid_kind
created: 2026-01-01
schema_version: 1
---
"""
        result = run_script("frontmatter-lint.py", ["--input", invalid])
        assert result.get("valid") is False
        assert any("INVALID: doc_kind" in v for v in result.get("violations", []))

    def test_invalid_status_enum(self):
        """An invalid status should be caught."""
        invalid = """
---
id: ADR-099
title: "Test"
doc_kind: decision
status: proposed
created: 2026-01-01
schema_version: 1
---
"""
        result = run_script("frontmatter-lint.py", ["--input", invalid])
        assert result.get("valid") is False
        assert any("INVALID: status" in v for v in result.get("violations", []))

    def test_lesson_id_pattern(self):
        """Lesson IDs must match LL-NNN pattern."""
        invalid = """
---
id: lesson-1
title: "Test"
doc_kind: lesson
created: 2026-01-01
schema_version: 1
---
"""
        result = run_script("frontmatter-lint.py", ["--input", invalid])
        violations = result.get("violations", [])
        assert any("LL-" in v for v in violations), f"Expected LL- pattern violation: {violations}"

    def test_all_fixture_ads_valid(self):
        """All 6 fixture ADRs should pass validation."""
        adrs_dir = FIXTURES_DIR / "structured-repo" / "docs" / "decisions"
        for f in sorted(adrs_dir.glob("ADR-*.md")):
            result = run_script("frontmatter-lint.py", ["--file", str(f)])
            assert result.get("valid") is True, f"{f.name} should be valid: {result}"

    def test_all_fixture_lessons_valid(self):
        """All 3 fixture lessons should pass validation."""
        lessons_dir = FIXTURES_DIR / "structured-repo" / "docs" / "lessons"
        for f in sorted(lessons_dir.glob("LL-*.md")):
            result = run_script("frontmatter-lint.py", ["--file", str(f)])
            assert result.get("valid") is True, f"{f.name} should be valid: {result}"

    def test_all_fixture_summaries_valid(self):
        """All fixture summaries should pass validation."""
        summaries_dir = FIXTURES_DIR / "structured-repo" / "docs" / "summaries"
        for f in sorted(summaries_dir.glob("SUM-*.md")):
            result = run_script("frontmatter-lint.py", ["--file", str(f)])
            assert result.get("valid") is True, f"{f.name} should be valid: {result}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
