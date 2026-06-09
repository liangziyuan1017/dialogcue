# concurrency-cases fixture

Concurrent write and conflict-handling scenarios for deterministic testing.

## Cases

| ID | Scenario | Expected Outcome |
|---|---|---|
| CC-001 | Two agents allocate ADR IDs simultaneously | Both get unique IDs; no duplicates |
| CC-002 | Two agents write the same ADR title | First wins; second stored as candidate |
| CC-003 | Index rebuild during concurrent document writes | Index marked stale; incremental rebuild catches up |
| CC-004 | Two agents capture the same lesson (different wording) | Second stored as candidate with possible_duplicate_of |
| CC-005 | Optimistic concurrency: update ADR changed since read | REJECTED; agent must re-read and retry |

See `cases.json` for machine-readable scenarios.

