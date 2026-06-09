"""
test_adapters.py — Adapter integration tests.

Covers: Phase 9 adapter checklist items.
- Trigger mapping resolves all 9 skills
- Adapter config is self-contained
- Adapter does not leak into core module
"""
import sys
import json
import subprocess
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent.parent
ADAPTERS_DIR = MODULE_DIR / "adapters"


class TestAdapters:
    """Test adapter integrity."""

    def test_trigger_mapping_has_all_skills(self):
        """Trigger mapping covers all 9 skills."""
        trigger_yaml = ADAPTERS_DIR / "agent-tool" / "trigger-mapping.yaml"
        assert trigger_yaml.exists(), "trigger-mapping.yaml should exist"

        with open(trigger_yaml, "r") as f:
            content = f.read()

        expected_skills = [
            "memory-search",
            "decision-record",
            "lesson-capture",
            "metadata-enforce",
            "memory-index",
            "memory-summarize",
            "governance-review",
            "memory-bootstrap",
            "memory-prune",
        ]
        for skill in expected_skills:
            assert skill in content, f"trigger-mapping.yaml should contain {skill}"

    def test_adapter_readme_exists(self):
        """Each adapter has a README."""
        for adapter_dir in ADAPTERS_DIR.iterdir():
            if adapter_dir.is_dir() and not adapter_dir.name.startswith("."):
                readme = adapter_dir / "README.md"
                assert readme.exists(), f"Missing README in adapter: {adapter_dir.name}"

    def test_core_module_no_adapter_leakage(self):
        """Core module files should not reference adapter internals."""
        core_files = [
            MODULE_DIR / "rules.md",
            MODULE_DIR / "router.md",
        ]
        for core_file in core_files:
            with open(core_file, "r") as f:
                content = f.read()
            assert "adapters/" not in content, \
                f"{core_file.name} should not reference adapters/ (core must be host-agnostic)"

    def test_workflows_no_adapter_leakage(self):
        """Workflow files should not reference adapter internals."""
        workflows_dir = MODULE_DIR / "workflows"
        for wf in workflows_dir.glob("*.md"):
            if wf.name == "README.md":
                continue
            with open(wf, "r") as f:
                content = f.read()
            assert "adapters/" not in content, \
                f"{wf.name} should not reference adapters/ (workflows must be host-agnostic)"

    def test_skills_no_adapter_leakage(self):
        """Skill files should not reference adapters (router handles that)."""
        skills_dir = MODULE_DIR / "skills"
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            with open(skill_file, "r") as f:
                content = f.read()
            assert "adapters/" not in content, \
                f"{skill_file.relative_to(MODULE_DIR)} should not reference adapters/"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
