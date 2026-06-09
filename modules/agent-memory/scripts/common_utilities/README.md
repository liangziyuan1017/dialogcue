# common_utilities

Shared utility library for agent-memory scripts. No host-specific dependencies.

## API Reference

### `load_yaml_frontmatter(filepath: Path) -> tuple[dict, str]`

Parse YAML frontmatter from a Markdown file. Returns `(frontmatter_dict, body_text)`.
Frontmatter is the content between the first and second `---` delimiters.
Uses a minimal YAML parser — no PyYAML dependency by design.

### `compute_content_hash(filepath: Path) -> str`

Compute SHA-256 hash of file content. Used for change detection in incremental index rebuilds and optimistic concurrency checks.

### `ensure_dir(path: Path) -> None`

Create directory (and parents) if it doesn't exist. Used by `write-durable`, `index-rebuild`, and `tombstone-create`.

### `write_json(data: dict, filepath: Path) -> None`

Write JSON to file with deterministic key ordering (`sort_keys=True`, `indent=2`). Used for index and lock file writes.

### `read_json(filepath: Path) -> dict`

Read JSON from file. Used for reading index, lock, and allocator state.

### `fail(msg: str, code: int = 1) -> None`

Print error message to stderr and exit with given code. Standard error exit for all scripts.

## Constants (`constants.py`)

| Constant | Value | Used By |
|---|---|---|
| `REQUIRED_FIELDS` | `["id", "title", "doc_kind", "created", "schema_version"]` | `frontmatter-lint`, `validate-each` |
| `DOC_KIND_ENUM` | `["decision", "lesson", "spec", "plan", "discussion", "research", "bug-report", "review", "note", "summary"]` | `frontmatter-lint`, `knowledge-validate` |
| `STATUS_ENUM` | `["draft", "review", "accepted", "deprecated", "superseded", "archived"]` | `frontmatter-lint` |
| `AUTHORITY_ENUM` | `["observed", "candidate", "validated", "constitutional"]` | `knowledge-validate` |
| `ACTIVATION_ENUM` | `["query", "scoped", "always_on", "backstop"]` | `knowledge-validate` |
| `KNOWLEDGE_STATUS_ENUM` | `["active", "review", "invalidated", "archived"]` | `knowledge-validate` |
| `EXPORTABILITY_ENUM` | `["private", "project_only", "generalized"]` | `knowledge-validate` |
| `LESSON_ID_PATTERN` | `r"^LL-\d{3}$"` | `id-allocate` |
| `ADR_ID_PATTERN` | `r"^ADR-\d{3}$"` | `id-allocate` |

## Design Constraints

- **No PyYAML dependency**: Frontmatter parsing uses a minimal built-in parser. This keeps the module self-contained with zero external dependencies.
- **No host-specific imports**: This library must not import any host-specific modules. It is shared across all adapter contexts.
- **Deterministic output**: `write_json` uses `sort_keys=True` to ensure reproducible file content.
