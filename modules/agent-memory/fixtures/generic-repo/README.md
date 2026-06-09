# generic-repo fixture

A minimal repository with no structured durable memory documents.
Used to verify: cold-start behavior, graceful empty-index handling.

## Structure
- No `docs/decisions/`, `docs/lessons/`, or `docs/summaries/` directories.
- Just a `README.md` and a `src/` directory with code.

## Expected bootstrap outcome
- 0 docs discovered
- Index is empty but valid
- Report: "No structured durable docs found"

