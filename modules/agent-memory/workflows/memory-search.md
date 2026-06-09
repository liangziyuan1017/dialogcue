# Memory Search Workflow

> **Skill**: `skills/memory-search/SKILL.md`
> **Purpose**: Search durable project memory for prior decisions, lessons, summaries, and validated knowledge.

## Scripts

| Script | Path | Purpose |
|---|---|---|
| `lexical-search` | `scripts/lexical-search.py` | Exact and fuzzy text search over indexed documents |
| `semantic-search` | `scripts/semantic-search.py` | Vector similarity search (**stub** — requires pre-computed embedding index and running embedding service; degrades gracefully) |
| `hybrid-fuse` | `scripts/hybrid-fuse.py` | Reciprocal-rank fusion of lexical and semantic results |
| `result-format` | `scripts/result-format.py` | Format ranked results with source anchors and metadata; `--apply-boost` applies authority/status ranking |

## Execution Order

1. **Parse query**: Accept a natural-language query string and optional filters.
   ```
   Supported filters: --doc-kind <kind>, --feature-id <id>, --topic <topic>, --authority <level>, --limit <n>
   ```

2. **Check embedding availability**:
   ```
   scripts/semantic-search.py --health
   ```
   → If embedding service is reachable: use hybrid mode.
   → If unreachable: degrade to lexical-only mode.
   → Rule: `rules.md §1` — source of truth is documents; semantic is an optimization, not a requirement.

3. **Lexical recall**:
   ```
   scripts/lexical-search.py --query "<QUERY>" [--filters <FILTERS>] --limit 50
   ```
   → Output: ranked list of `(doc_id, score, snippet)` tuples.
   → Exact ID lookup (e.g., `"ADR-008"`) must return top-1 = 100% if the document exists.

4. **Semantic recall** (skip if degraded):
   ```
   scripts/semantic-search.py --query "<QUERY>" [--filters <FILTERS>] --limit 50
   ```
   → Output: ranked list of `(doc_id, score)` tuples from vector index.

5. **Hybrid fusion**:
   ```
   scripts/hybrid-fuse.py --lexical <LEXICAL_RESULTS> --semantic <SEMANTIC_RESULTS> --k 60
   ```
   → Output: fused ranked list using reciprocal-rank fusion (RRF).
   → If semantic is unavailable: pass lexical results through unchanged.

6. **Metadata boost**:
   ```
   scripts/result-format.py --results <FUSED_RESULTS> --limit <LIMIT> --apply-boost
   ```
   → Authority boost: `constitutional` > `validated` > `candidate` > `observed`.
   → Status boost: `accepted` > `draft` > `review` > `superseded` > `archived`.
   → Demote `knowledge.activation: backstop` unless relevance score is high.
   → Rule: `rules.md §3` — backstop entries preserved but not prominent.
   → Boost order is defined in `scripts/result-format.py` (not in this workflow).

7. **Format results**:
   ```
   scripts/result-format.py --results <FUSED_RESULTS> --limit <LIMIT>
   ```
   → Output: top-N results with `(doc_id, title, doc_kind, authority, status, snippet, source_anchor)`.

## Success Conditions

- Query returns results in < 2s (lexical) or < 5s (hybrid).
- Exact ID lookup returns the document at rank 1 (if it exists).
- Degradation to lexical-only is transparent (no error, just lower recall quality).

## Failure Conditions

- Index is missing or corrupt → exit code 1, report `"index unavailable; run memory-index to rebuild"`.
- Both lexical and semantic search fail → exit code 1, report error.
- Malformed query (empty string, only whitespace) → exit code 1, report `"invalid query"`.

## Degradation Path

| Condition | Behavior |
|---|---|
| Embedding service unreachable | Degrade to lexical-only; results include note `"semantic unavailable"` |
| Missing vector index | Degrade to lexical-only; no error |
| Malformed metadata in index | Exclude from metadata boost, not from raw recall |
| Index stale (docs mutated during search) | Include warning in results: `"index may be stale; run memory-index --incremental"` |

## Next Step

Memory search is a terminal capability — it returns results and does not chain to another skill. If the search reveals that a document needs updating, route to the appropriate write skill:

| Finding | Route To |
|---|---|
| Decision needs status update | `decision-record` |
| Lesson needs correction | `lesson-capture` |
| Stale or duplicate knowledge found | `memory-prune` |
| Metadata violations found | `metadata-enforce` |

## Document Sync Rule

Memory search is read-only. No documents are created or modified. The index is consumed, not updated.

## Iron Laws

- Search must never modify the index or any durable document.
- Degradation to lexical-only is transparent — the caller must receive results, never an empty response due to embedding unavailability.
- Exact ID lookup must return the document at rank 1 if it exists, regardless of ranking algorithm.

## Anti-patterns

- **Searching instead of writing**: If the task is to record a new decision or lesson, do not use memory-search. Route to `decision-record` or `lesson-capture` instead.
- **Rebuilding index on every search**: Index rebuilds are expensive. Use `memory-index` only when documents have changed, not before every search.

## Test References

| Test | Path |
|---|---|
| search_memory | `tests/test_search_memory.py` |
| search_degradation | `tests/test_search_memory.py` |

## Reproducible Example

```bash
# Hybrid search with embedding available
scripts/semantic-search.py --health
# Expected: "healthy" or "unreachable"

scripts/lexical-search.py --query "port allocation strategy" --limit 50
# Expected: returns ranked doc list including ADR-008

scripts/semantic-search.py --query "port allocation strategy" --limit 50
# Expected: returns ranked doc list from vector index

scripts/hybrid-fuse.py --lexical <...> --semantic <...> --k 60
# Expected: fused list with RRF

scripts/result-format.py --results <...> --limit 5
# Expected: top-5 results with doc_id, title, snippet

# Exact ID lookup
scripts/lexical-search.py --query "ADR-008" --limit 1
# Expected: ADR-008 at rank 1 (100% precision)

# Degraded: no embedding service
scripts/semantic-search.py --health
# Expected: "unreachable"
scripts/lexical-search.py --query "stale lock handling" --limit 5
scripts/result-format.py --results <...> --limit 5
# Expected: results returned with note "semantic unavailable; lexical-only results"
```
