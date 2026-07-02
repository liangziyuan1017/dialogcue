# ROADMAP

| ID | Name | Status | Owner | Source | Link |
|----|------|--------|-------|--------|------|
| F000 | State Keyword Discovery | complete | agent | feature doc | [F000](features/F000-state-keyword-discovery.md) |
| F001 | Data Schema Alignment | complete | agent | feature doc | [F001](features/F001-data-schema-alignment.md) |
| F003 | Reward Labeling | complete | agent | feature doc | [F003](features/F003-reward-labeling.md) |
| F004 | Decision Tree Construction | complete | agent | feature doc | [F004](features/F004-decision-tree-construction.md) |
| F004-dedup | Sentence Pool Deduplication | complete | agent | F004 | [F004-dedup](features/F004-sentence-pool-dedup.md) |
| F005 | Context Tagging & Quality Scoring | complete | agent | feature doc | [F005](features/F005-context-tagging-quality-scoring.md) |
| F006 | Retrieval & Ranking Engine | complete | agent | feature doc | [F006](features/F006-retrieval-ranking-engine.md) |
| F007 | Infrastructure Layer | review | agent | [impl-steps](features/F007-F009-implementation-steps.md) | [F007](features/F007-infra-layer.md) |
| F007b | Vector Retrieval Integration | review | agent | [impl-steps](features/F007-F009-implementation-steps.md) | [F007b](features/F007b-vector-retrieval-integration.md) |
| F008 | State Extraction Module | review | agent | [impl-steps](features/F007-F009-implementation-steps.md) | [F008](features/F008-state-extraction.md) |
| F009 | REST API + Socket.IO Server | review | agent | [impl-steps](features/F007-F009-implementation-steps.md) | [F009](features/F009-api-server.md) |
| F010 | API Mock + System Status UI | complete | agent | feat-lifecycle | [F010](features/F010-api-mock-system-status-ui.md) |
| F011 | Config Externalization | complete | agent | feature doc | [F011](features/F011-config-externalization.md) |
| F012 | Runtime Robustness Hardening | in-progress | agent | feature doc | [F012](features/F012-runtime-robustness-hardening.md) |
| F013 | asyncpg Migration | merged | agent | [ADR-027](decisions/ADR-027-db-concurrency-threadpool-now-asyncpg-later.md) | [F013](features/F013-asyncpg-migration.md) |

> **F002 removed** (ADR-009): LLM State Extraction eliminated. F001's manual annotations (493/805 turns) provide sufficient state coverage. Downstream features handle unlabeled turns gracefully.

---

## Dependency Graph

```
F000 ──► F001 ──► F003 ──► F004 ──► F005 ──► F006
                                     │           │
                                     └────► F007 ◄┘
                                              │
                                              ▼
                                            F007b
                                              │
                                              ▼
                                            F008
                                              │
                                              ▼
                                            F009
```

---

## Architecture Decisions

Consolidated index of the system's architecture choices. Each row links to the authoritative ADR where one exists.

| Decision | Choice | Rationale | ADR |
|---|---|---|---|
| Database | **PostgreSQL + pgvector** | One database for metadata + vectors + FTS; ACID; mature; handles 50K+ records trivially | — |
| Embeddings | **bge-m3 via Ollama (OpenAI-compatible)** | Local, no per-call cost, offline-capable. 1024-dim. | [ADR-024](decisions/ADR-024-embedding-architecture.md) |
| SAS (Script Analogy Score) | **TF-IDF cosine** | Char bigram TF-IDF within sentence pool — unchanged | [ADR-020](decisions/ADR-020-f005-bitmask-scoring-design.md) |
| Conversation context similarity | **Vector cosine via pgvector** | Replaces char-ngram TF-IDF; captures semantic meaning ("没钱" ≈ "经济困难") | [ADR-024](decisions/ADR-024-embedding-architecture.md) |
| Full-text search | **PostgreSQL tsvector + GIN** | Keyword-based state extraction fallback; fuzzy matching on `script_text` | — |
| Ranking | **Weighted fusion (configurable)** | `0.35×win_rate + 0.25×vec_score + 0.10×sas + 0.10×bg_boost + 0.20×bitmask_score` — weights in `config.md` | — |
| State extraction | **LLM-first (DeepSeek)** | LLM is primary extraction; keyword scan via tsvector as fallback | [ADR-009](decisions/ADR-009-eliminate-f002-llm-state-extraction.md) |
| Conversation state | **Accumulated across turns** | Caller passes in previously extracted states; system appends new extractions; used for path matching | [ADR-006](decisions/ADR-006-context-constraint-mapping.md) |
| Candidate retrieval | **PostgreSQL** | Sentences stored in PG, retrieved by `node_id` with bitmask filter + vector rank in single query | — |
| Vector scoring | **SQL-side pgvector `<=>`** | `vec_score` computed in PostgreSQL, eliminating raw embedding transfer to Python | [ADR-028](decisions/ADR-028-sql-side-cosine-scoring.md) |
| DB concurrency | **asyncpg (runtime) + psycopg2 (build-time)** | Runtime uses `AsyncSentenceDB` with asyncpg (F013); build-time keeps `psycopg2` for batch ops | [ADR-027](decisions/ADR-027-db-concurrency-threadpool-now-asyncpg-later.md) |
| API | **FastAPI** | Already in `pyproject.toml` dependencies | — |
