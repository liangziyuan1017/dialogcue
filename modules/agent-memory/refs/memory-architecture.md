# Memory Architecture — Retrieval, Indexing, and Summarization

> Normalized from clowder-ai ADR-020 (F102 Memory System Architecture).
> Patterns only — implementation is backend-agnostic via the MemoryStore interface.

## Retrieval Architecture — Three Independent Paths

| Mode | Method | Use Case |
|------|--------|----------|
| **Lexical** | Full-text search on document content + frontmatter | Exact terms: feature IDs (F001), command names, error codes |
| **Semantic** | Vector nearest-neighbor on embeddings | Cross-language queries, synonym matching, conceptual search |
| **Hybrid** | Lexical + Semantic → RRF (Reciprocal Rank Fusion) | Recommended daily use — combines precision of lexical with recall of semantic |

**Key properties:**
- Semantic does NOT depend on lexical recall (pure NN).
- Hybrid's lexical candidate pool is capped at 100.
- Depth mode forces lexical-only for passage-level queries.
- **Fail-open**: if embeddings are unavailable, degrade to lexical instead of failing.

## RRF Fusion Formula

```
RRF_score(d) = Σ 1/(k + rank_i(d))
```
Where `k=60` (default), and `rank_i(d)` is the rank of document `d` in result list `i`.

## LSM Compaction — Three-Layer Summarization

```
L0: Real-time stitching
    Messages → concatenation → 30s debounce
    Cost: zero. Latency: <100ms.

L1: Periodic summaries
    Scheduler (30min tick) → eligibility check → LLM summary
    Cost: 1 LLM call per conversation thread.
    Output: summary segment + re-index + re-embed.

L2: Rollup (deferred)
    Segment ledger already structured.
    Upgrading only changes the read path.
```

**Eligibility Rule (L1):**
```
quietWindow ≥ 10min
AND (messages ≥ 20 OR tokens ≥ 1500 OR high-signal activity)
AND (cooldown ≥ 2h OR carry_over)
```

## Storage Pattern

```
Source of Truth: docs/*.md (human-readable, git-tracked)
       │
       ▼
Compiled Index: rebuildable artifact (gitignored)
       │
       ├── Document metadata + full-text (FTS5)
       ├── Vector embeddings (optional, GPU-accelerated)
       ├── Summary segments (append-only ledger)
       ├── Edges between documents (evolved_from, blocked_by, related)
       └── Schema version + embedding metadata
```

## Key Design Rules

1. **Documents are truth; index is cache.** If they disagree, documents win. Rebuild the index.
2. **No summary-of-summary.** Summaries are generated from original source material only. Re-summarizing compounds drift.
3. **Append-only summary ledger.** Each summary segment is immutable. New summaries append; old ones are never overwritten.
4. **Single-writer index.** Index rebuilds are serialized per project. Two rebuilds cannot run concurrently.
5. **Feature-flagged.** All advanced features (semantic search, summarization) are off by default.
