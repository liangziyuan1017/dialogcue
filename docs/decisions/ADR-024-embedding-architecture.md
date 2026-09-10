---
REMOVED_FIELD_id: ADR-024
title: "Embedding architecture: bge-m3 via Ollama replaces char-ngram TF-IDF"
doc_kind: decision
feature_ids: [F007, F007b]
topics: [embeddings, vector-search, ollama, pgvector, sas]
status: accepted
created: 2026-06-24
updated: 2026-06-25
schema_version: 2
---

# Embedding Architecture: bge-m3 via Ollama

## What

Replace the char-ngram TF-IDF cosine similarity (ADR-020 SAS design) with dense vector embeddings for retrieval:

1. **Model**: `bge-m3` (BAAI), served locally via Ollama on port 11434
2. **Dimensionality**: 1024 (bge-m3 default)
3. **Client**: OpenAI-compatible API (`http://localhost:11434/v1`) via `f007_infrastructure/embeddings.py`
4. **Storage**: PostgreSQL + pgvector `sentences` table with `embedding vector(1024)` column
5. **Ranking**: Unified weighted fusion replacing dual-strategy (`0.40*win_rate + 0.30*vec_score + 0.15*sas + 0.15*bg_boost`)

## Why

- **Semantic quality**: bge-m3 captures meaning beyond surface character overlap. Char-ngram TF-IDF treats "暂时无法还款" and "目前经济困难" as unrelated; bge-m3 recognizes semantic similarity.
- **Local operation**: Ollama serves the model locally — no external API dependency, no per-call cost, no latency from network round-trips. Consistent with ADR-014 (bundled JS libs for offline operation).
- **pgvector integration**: Embeddings stored alongside sentences in PostgreSQL. Hybrid search: vector similarity + bitmask AND + FTS keyword search in a single query.
- **Unified ranking**: The dual-strategy switch (`limited`/`full`) was a workaround for TF-IDF's weak signal. With meaningful vector similarity, a single weighted fusion is simpler and more robust.

## Tradeoff

| Alternative | Rejected Because |
|-------------|-----------------|
| Keep char-ngram TF-IDF | Weak semantic signal; "没钱" and "经济困难" have zero similarity despite same meaning |
| DeepSeek embeddings | DeepSeek API has no dedicated embedding endpoint (only chat models) |
| OpenAI text-embedding-3-small | External API dependency; per-call cost; latency; violates offline-first principle |
| Sentence-BERT locally | Requires GPU for reasonable latency; bge-m3 via Ollama is CPU-friendly |
| 768-dim model (e.g. bge-small) | Lower retrieval quality; bge-m3 at 1024-dim is the quality/performance sweet spot |
| Pure SQL ranking | `bg_boost` requires JSONB dict comparison not expressible in SQL; Python-side ranking needed |

## Impact on Prior Decisions

- **ADR-020** SAS design: The `sas` field remains but is now a secondary signal (weight 0.15) rather than primary. SAS still uses char-ngram TF-IDF for intra-node redundancy avoidance. Vector similarity (`vec_score`) is the primary semantic signal (weight 0.30).
- **F006 dual strategy**: Removed. `_rank_limited`, `_rank_full`, `RANKING_STRATEGY`, and `compute_context_similarity` are deleted. Replaced by unified `rank_sentences()` with `RANKING_WEIGHTS`.

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `EMBEDDING_MODEL` | `bge-m3` | Model name served by Ollama |
| `EMBEDDING_BASE_URL` | `http://localhost:11434/v1` | Ollama OpenAI-compatible endpoint |
| `EMBEDDING_API_KEY` | `ollama` | API key (unused by Ollama, required by OpenAI client) |
| `EMBEDDING_DIM` | `1024` | Vector dimensionality |
