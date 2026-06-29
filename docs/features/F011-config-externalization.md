---
id: F011
name: Config Externalization
status: complete
owner: agent
related_features: [F006, F007, F007b, F008, F009, F010]
topics: [configuration, ranking, validation]
doc_kind: spec
created: 2026-06-29
updated: 2026-06-29
---

# F011: Config Externalization via `config.md`

## Why

99 hardcoded parameters were scattered across 25 source files. Changing ranking weights, confidence penalties, LLM settings, or batch sizes required code edits. Operators could not tune the system without developer involvement.

## What

### `config.md` — YAML Frontmatter Config

A single `config.md` file at project root with YAML frontmatter containing all configurable parameters. Freeform markdown below for human notes.

### `src/f007_infrastructure/config.py` — Loader

- `load_config()` — parse frontmatter, cache result
- `reload_config()` — clear cache + re-parse (for runtime refresh or `CONFIG_PATH` change)
- `get(key, default)` — dot-notation access (e.g., `get("ranking_weights.win_rate", 0.40)`)
- `CONFIG_PATH` env var override for deployment flexibility

### Schema Validation

At load time, `_validate()` checks:
1. **Range constraints** — 47 keys have `[lo, hi]` bounds (e.g., weights in `[0, 1]`, `pool_cap` in `[1, 1000]`)
2. **Ranking weights sum** — `win_rate + vec_score + sas + bg_boost` must equal `1.0` (±0.01 tolerance)
3. **Type check** — numeric keys must be parseable as `float`

Invalid config raises `ValueError` with all errors listed. No partial application — either the whole config is valid or the process fails.

### Parameter Categories

| Category | Keys | Example |
|----------|------|---------|
| Ranking weights | 4 | `win_rate`, `vec_score`, `sas`, `bg_boost` |
| BG boost values | 7 + 1 threshold | `industry_match`, `age_proximity_threshold` |
| Confidence decay | 6 | `subset_drop_penalty`, `descend_penalty` |
| Keyword confidence | 4 | `base`, `per_match`, `ceiling`, `no_match` |
| LLM | 5 | `model`, `api_base`, `temperature`, `max_tokens` |
| Embedding | 4 | `model`, `api_base`, `dimension` |
| Retry | 3 | `max_retries`, `min_sleep`, `max_sleep` |
| Batch sizes | 3 | `data_cleaning`, `analysis`, `keyword_discovery` |
| Context windows | 4 | `conversation_turns`, `reward_last_n_turns` |
| Search limits | 5 | `vector_limit`, `trigram_threshold` |
| HNSW index | 2 | `m`, `ef_construction` |
| SAS/TF-IDF | 1 | `ngram_size` |
| Decision tree | 3 | `max_merged_words`, `find_node_max_levels` |
| Reward | 1 | `explanation_max_words` |
| Server | 2 | `tree_explorer_port` |
| Pipeline | 2 | `default_data_file`, `scheduler_interval` |
| HWR | 3 | `default`, `laplace_alpha`, `laplace_beta` |

**Total: 99 parameters** (domain mappings intentionally excluded — they are code-level schema contracts)

## Acceptance Criteria

- [x] AC-1: All 99 parameters readable from `config.md` via `get()`
- [x] AC-2: Defaults match previous hardcoded values (zero behavior change)
- [x] AC-3: `CONFIG_PATH` env var overrides default path
- [x] AC-4: `reload_config()` clears cache and re-validates
- [x] AC-5: Invalid config (out-of-range, bad sum, non-numeric) raises `ValueError`
- [x] AC-6: Missing config file returns empty dict (no crash)
- [x] AC-7: 345 tests pass with config externalization active
- [x] AC-8: Domain mappings (credit_rating, education, delinquency, risk_level) remain hardcoded

## Design Decisions

| # | Decision | Rationale | Date |
|---|----------|-----------|------|
| KD-1 | YAML frontmatter in `.md` file | Human-readable + machine-parseable; markdown notes below frontmatter | 2026-06-29 |
| KD-2 | Dot-notation `get()` accessor | Simple, no schema class overhead; matches nested YAML structure | 2026-06-29 |
| KD-3 | Validation at load time, not access time | Fail-fast; operator sees all errors before any code runs | 2026-06-29 |
| KD-4 | Domain mappings excluded | These are schema contracts (align_schema.py), not runtime tuning knobs | 2026-06-29 |
| KD-5 | `pyyaml` as core dependency (not dev-only) | Config loads at startup before any module runs | 2026-06-29 |
| KD-6 | Ranking weights sum validated to 1.0 | Prevents accidental misweighting that silently degrades recommendations | 2026-06-29 |

## Files

### New
- `config.md` — all 99 parameters with defaults
- `src/f007_infrastructure/config.py` — loader + validator
- `src/tests/f007_infrastructure/test_config.py` — 11 tests

### Modified (25 files)
- `src/f006_retrieval_engine/retrieval_ranking.py`
- `src/f006_retrieval_engine/retrieval_engine.py`
- `src/f009_api_server/server.py`
- `src/f008_state_extraction/state_extraction.py`
- `src/f007_infrastructure/llm_client.py`
- `src/f007_infrastructure/embeddings.py`
- `src/f007_infrastructure/retry.py`
- `src/f007_infrastructure/db.py`
- `src/f005_context_scoring/scoring_metrics.py`
- `src/f005_context_scoring/score_tree.py`
- `src/f003_reward_labeling/reward_label.py`
- `src/f003_reward_labeling/analyze_collector_turns.py`
- `src/f003_reward_labeling/analyze_customer_turns.py`
- `src/f003_reward_labeling/define_willingness_levels.py`
- `src/f004_decision_tree/merge_collector.py`
- `src/f004_decision_tree/build_decision_tree.py`
- `src/f004_decision_tree/serve_tree.py`
- `src/f000_keyword_discovery/keyword_prompts.py`
- `src/f000_keyword_discovery/discover_keywords.py`
- `src/whole_pipeline.py`
- `data/data_cleaning/data_clean_2.py`
- `data/data_cleaning/data_logic.py`
- `data/data_cleaning/data_complete.py`
- `pyproject.toml`
- `config_plan.md` (plan document)

## Test Evidence

```
pytest → 345 passed, 8 skipped ✅
config tests → 11 passed ✅
  - test_get_returns_config_value
  - test_get_returns_default_for_missing_key
  - test_get_nested_dot_notation
  - test_load_config_returns_dict
  - test_reload_config
  - test_custom_config_path
  - test_frontmatter_without_delimiters
  - test_validation_rejects_weights_not_summing_to_one
  - test_validation_rejects_out_of_range
  - test_validation_rejects_non_numeric
  - test_validation_passes_for_valid_config
```
