---
id: F007b
name: Vector Retrieval Integration
status: review
depends_on: [F007]
created: 2026-06-24
updated: 2026-06-25
review_submitted: 2026-06-25
worktree: /Users/jiani/Desktop/icbc-f010-infra-layer
branch: feat/f010-infra-layer
---

# F007b: Vector Retrieval Integration — F005 Embedding Load + F006 Vector Ranking

## Goal

Wire the F007 infrastructure into the existing F005 and F006 modules:
1. **F005**: After scoring, embed all sentences and load into PostgreSQL
2. **F006**: Replace char-ngram TF-IDF with vector similarity, unify ranking into single weighted fusion

Covers **Steps 4-6** of [F007-F009-implementation-steps.md](F007-F009-implementation-steps.md).

## Passing Criteria

- `score_tree.py` produces `decision_tree_scored.json` with `context_vec_id` on each sentence
- PostgreSQL `nodes` table populated after scoring
- PostgreSQL `sentences` table populated with embeddings after scoring
- `compute_vec_similarity()` returns cosine similarity scores from PostgreSQL vectors
- `rank_sentences()` uses unified fusion: `0.40*win_rate + 0.30*vec_score + 0.15*sas + 0.15*bg_boost`
- No reference to `compute_context_similarity` or `_rank_limited` remains in `retrieval_ranking.py`
- `recommend()` returns `vec_score`, `final_score`, `conversation_state` keys
- No in-memory pool access in `recommend()` — candidates from PostgreSQL

## Scope

Modifies existing F005 and F006 modules. Does NOT create new modules (state extraction, API server are later features).

## Files

- MODIFY: `src/f005_context_scoring/score_tree.py`
- MODIFY: `src/f006_retrieval_engine/retrieval_ranking.py`
- MODIFY: `src/f006_retrieval_engine/retrieval_engine.py`
- MODIFY: `src/tests/f005_context_scoring/test_score_tree.py`
- MODIFY: `src/tests/f006_retrieval_engine/test_retrieval_ranking.py`
- MODIFY: `src/tests/f006_retrieval_engine/test_retrieval_engine.py`

## Implementation Plan

See [F007b-implementation-plan.md](F007b-implementation-plan.md)
