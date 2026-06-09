# Reference-Only Module

This module (`clowder-dev`) is a reference-only module. The `scripts/` and `tests/` directories are intentionally empty.

The execution intelligence lives in `workflows/` as process descriptions, not executable code. All capabilities describe development workflow steps that guide agent behavior rather than produce deterministic data outputs.

See `router.md` → `skills/<name>/SKILL.md` → `workflows/<name>.md` for the full capability chain.
