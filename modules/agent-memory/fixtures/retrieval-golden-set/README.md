# retrieval-golden-set fixture

Fixed retrieval queries with expected top-3 ranking outcomes.

Format: Each query has:
- `query`: the search string
- `expected_top3`: expected top-3 doc IDs in order
- `must_include`: doc ID that must appear in results
- `must_not_rank_above`: doc ID that must not outrank another

## Queries (10 queries covering 5 categories)

See `queries.json` for the machine-readable golden set.

