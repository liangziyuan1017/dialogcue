"""
test_migration.py — Migration tests.

Covers: Phase 9 migration checklist items.
- Source-to-target migration matrix is complete
- Refs link back to their sources
- Schema version compatibility
"""
import sys
import json
import subprocess
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent.parent
REFS_DIR = MODULE_DIR / "refs"
TEMP_DIR = Path(__file__).resolve().parent.parent.parent.parent / "temp"


class TestMigration:
    """Test migration completeness and correctness."""

    def test_migration_matrix_exists(self):
        """refs/README.md contains a source-to-target migration matrix."""
        refs_readme = REFS_DIR / "README.md"
        assert refs_readme.exists(), "refs/README.md should exist"
        with open(refs_readme, "r") as f:
            content = f.read()
        assert "Source-to-Target Migration Matrix" in content, "Should have migration matrix"
        assert "decisions-first-principles.md" in content, "Should reference source file"
        assert "refs/first-principles.md" in content, "Should reference target file"

    def test_all_refs_have_sources(self):
        """Each ref file should be traceable to a source or have a reason."""
        refs_readme = REFS_DIR / "README.md"
        with open(refs_readme, "r") as f:
            content = f.read()

        # Check expected refs are mentioned
        expected_refs = [
            "first-principles.md",
            "governance-structure.md",
            "shared-rules.md",
            "collaboration-protocol.md",
            "metadata-contract.md",
            "knowledge-objects.md",
            "lessons-template.md",
            "memory-architecture.md",
            "memory-entropy-reduction.md",
            "expedition-memory.md",
            "memory-lessons.md",
            "anti-drift-protocol.md",
            "sop.md",
        ]
        for ref in expected_refs:
            assert ref in content, f"refs/README.md should mention {ref}"
            assert (REFS_DIR / ref).exists(), f"Missing ref file: {ref}"

    def test_no_cat_cafe_terms_in_ref_bodies(self):
        """Ref body content should not contain Cat Cafe terms (provenance notes OK)."""
        cat_terms = ["cat cafe", "caretaker", "铲屎官", "猫猫", "star jar"]
        for ref_file in REFS_DIR.glob("*.md"):
            if ref_file.name == "README.md":
                continue  # Migration matrix references are OK
            with open(ref_file, "r", encoding="utf-8") as f:
                content = f.read().lower()
            for term in cat_terms:
                # Allow in provenance lines only
                lines = content.split("\n")
                violating_lines = [
                    l for l in lines
                    if term in l.lower()
                    and not l.strip().startswith(">")
                    and "clowder" not in l.lower()
                ]
                assert len(violating_lines) == 0, \
                    f"{ref_file.name} contains '{term}' outside provenance: {violating_lines[:3]}"

    def test_schema_version_consistency(self):
        """All schemas have consistent schema_version."""
        schemas_dir = MODULE_DIR / "schemas"
        versions = set()
        for schema_file in schemas_dir.glob("*.yaml"):
            with open(schema_file, "r") as f:
                content = f.read()
            for line in content.split("\n"):
                if "schema_version:" in line and not line.strip().startswith("#") and not line.startswith("  "):
                    v = line.split(":", 1)[1].strip()
                    if v:
                        versions.add(v)
        # All should be version 1
        assert len(versions) <= 1, f"Multiple schema versions found: {versions}"

    def test_all_workflows_reference_scripts(self):
        """Every workflow should reference scripts/."""
        workflows_dir = MODULE_DIR / "workflows"
        for wf in workflows_dir.glob("*.md"):
            if wf.name == "README.md":
                continue
            with open(wf, "r") as f:
                content = f.read()
            assert "scripts/" in content, f"{wf.name} should reference scripts/"

    def test_all_skills_point_to_workflows(self):
        """Every skill should point to its workflow."""
        skills_dir = MODULE_DIR / "skills"
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            with open(skill_file, "r") as f:
                content = f.read()
            assert "workflows/" in content, \
                f"{skill_file.relative_to(MODULE_DIR)} should reference its workflow"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
