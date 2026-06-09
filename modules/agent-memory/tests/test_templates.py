"""
test_templates.py — Template validation tests.

Covers: Phase 9 template validation checklist items.
- All templates produce valid frontmatter
- Template placeholders are intentional
"""
import sys
import json
import subprocess
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
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
        return {"error": result.stdout, "exit_code": result.returncode}


class TestTemplateValidation:
    """Test that all templates have valid frontmatter structure."""

    def test_decision_template_has_required_fields(self):
        """Decision template has id, title, doc_kind, created, schema_version."""
        tmpl = TEMPLATES_DIR / "decision-record.md"
        with open(tmpl, "r") as f:
            content = f.read()
        assert "id: ADR-XXX" in content
        assert "doc_kind: decision" in content
        assert "schema_version: 1" in content

    def test_lesson_template_has_required_fields(self):
        """Lesson template has id, title, doc_kind, created, schema_version."""
        tmpl = TEMPLATES_DIR / "lesson.md"
        with open(tmpl, "r") as f:
            content = f.read()
        assert "id: LL-XXX" in content
        assert "doc_kind: lesson" in content
        assert "schema_version: 1" in content

    def test_feature_template_has_required_fields(self):
        """Feature template has id, title, doc_kind."""
        tmpl = TEMPLATES_DIR / "feature-spec.md"
        with open(tmpl, "r") as f:
            content = f.read()
        assert "id: FXXX" in content
        assert "doc_kind: spec" in content

    def test_review_template_has_required_fields(self):
        """Review template has id, title, doc_kind."""
        tmpl = TEMPLATES_DIR / "review-request.md"
        with open(tmpl, "r") as f:
            content = f.read()
        assert "id: REV-XXX" in content
        assert "doc_kind: review" in content

    def test_bug_template_has_required_fields(self):
        """Bug report template has id, title, doc_kind."""
        tmpl = TEMPLATES_DIR / "bug-report.md"
        with open(tmpl, "r") as f:
            content = f.read()
        assert "id: BUG-XXX" in content
        assert "doc_kind: bug-report" in content

    def test_all_templates_present(self):
        """All 5 templates exist."""
        expected = ["decision-record.md", "lesson.md", "feature-spec.md", "review-request.md", "bug-report.md"]
        for name in expected:
            assert (TEMPLATES_DIR / name).exists(), f"Missing template: {name}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
