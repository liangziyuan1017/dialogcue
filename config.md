---
# config.md — ICBC F010 Infra Layer Runtime Configuration

# ── Retrieval & Ranking ──
ranking_weights:
  win_rate: 0.35
  vec_score: 0.25
  sas: 0.10
  bg_boost: 0.10
  bitmask_score: 0.20

bg_boost:
  education_match: 0.02
  risk_level_match: 0.03
  complaint_proximity_match: 0.02
  complaint_proximity_threshold: 5
  delinquent_proximity_match: 0.02
  delinquent_proximity_threshold: 30
  recent_contact_signal: 0.02
  digits_proximity_match: 0.01
  digits_proximity_threshold: 1

pool_cap: 50

db:
  pool_max: 10

# ── Confidence Decay ──
confidence:
  subset_drop_penalty: 0.1
  root_fallback: 0.2
  descend_penalty: 0.05
  context_missing_penalty: 0.1
  bitmask_mismatch_penalty: 0.1
  embed_fallback_penalty: 0.1

keyword_confidence:
  base: 0.3
  per_match: 0.1
  ceiling: 0.8
  no_match: 0.1

# ── LLM ──
llm:
  model: "deepseek-chat"
  api_base: "https://api.deepseek.com"
  temperature: 0.1
  temperature_relabel: 0.0
  max_tokens: 16384
  timeout: 60

embedding:
  model: "bge-m3"
  api_base: "http://localhost:11434/v1"
  api_key: "ollama"
  dimension: 1024
  batch_size: 64

# ── Retry ──
retry:
  max_retries: 3
  min_sleep: 1
  max_sleep: 5

# ── Batch Sizes ──
batch_size:
  data_cleaning: 1
  analysis: 20
  keyword_discovery: 20

# ── Context Windows ──
context_window:
  conversation_turns: 5
  script_prefix_length: 50
  reward_last_n_turns: 6
  analysis_turns_before: 3

# ── Search Limits ──
search:
  vector_limit: 50
  keyword_limit: 20
  taxonomy_limit: 20
  trigram_threshold: 0.01
  taxonomy_trigram_threshold: 0.1

# ── HNSW Index ──
hnsw:
  m: 16
  ef_construction: 64

# ── SAS / TF-IDF ──
sas:
  ngram_size: 2

# ── Decision Tree ──
decision_tree:
  max_merged_words: 100
  ack_max_words: 15
  find_node_max_levels: 4

# ── Reward Labeling ──
reward:
  explanation_max_words: 100

# ── Server ──
server:
  tree_explorer_port: 8420
  session_id_length: 8
  request_max_chars: 8000
  rate_limit_rps: 20
  rate_limit_burst: 40
  session_ttl: 7200
  session_max: 10000
  allowed_origins: ["*"]

# ── Extraction ──
# provider: llm (default, DeepSeek) | bert (local model via bert_extractor.py)
# Override at runtime with EXTRACTION_PROVIDER=llm|bert
extraction:
  provider: llm
  cache_size: 512
  max_labels: 40
  bert:
    model_dir: ""          # path to your checkpoint; used once extract_state_bert is wired
    device: auto           # auto | cpu | cuda | mps

# ── Pipeline ──
pipeline:
  default_data_file: "input_data.jsonl"
  scheduler_interval: 600

# ── HWR ──
hwr:
  default: 0.5
  laplace_alpha: 1
  laplace_beta: 2
---

## Notes

Edit values above to tune system behavior. Regenerate pipeline outputs after changing ranking/scoring params.

State extraction defaults to DeepSeek (`extraction.provider: llm`). To use a local BERT model, implement `extract_state_bert` in `src/f008_state_extraction/bert_extractor.py`, then set `extraction.provider: bert` (or `EXTRACTION_PROVIDER=bert`). Until that function is wired, leave provider as `llm` — the placeholder raises and online falls back to keyword-only if bert is selected by mistake.
