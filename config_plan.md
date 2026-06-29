# Plan: Externalize Hardcoded Parameters via `config.md`

## Overview

109 hardcoded values are scattered across the codebase. This plan externalizes them into a single `config.md` file that is parsed at startup, giving operators tuning control without code changes. Domain mapping dicts (credit_rating, education, days_delinquent, risk_level) are intentionally excluded — they are code-level schema contracts, not runtime tuning knobs.

---

## 1. `config.md` Format

Use YAML frontmatter inside markdown for machine-parseable config, with freeform prose below for human notes.

```markdown
---
# config.md — ICBC F010 Infra Layer Runtime Configuration

# ── Retrieval & Ranking ──
ranking_weights:
  win_rate: 0.40
  vec_score: 0.30
  sas: 0.15
  bg_boost: 0.15

bg_boost:
  industry_match: 0.05
  education_match: 0.02
  debt_interest_match: 0.03
  age_proximity_match: 0.02
  age_proximity_threshold: 10
  risk_level_match: 0.03
  recent_repayment_signal: 0.02

pool_cap: 50

# ── Confidence Decay ──
confidence:
  subset_drop_penalty: 0.1
  root_fallback: 0.2
  descend_penalty: 0.05
  context_missing_penalty: 0.1
  bitmask_relax_penalty: 0.05
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

embedding:
  model: "bge-m3"
  api_base: "http://localhost:11434/v1"
  api_key: "ollama"
  dimension: 1024

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
  conversation_turns: 20
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
  max_merged_words: 150
  ack_max_words: 15
  find_node_max_levels: 4

# ── Reward Labeling ──
reward:
  explanation_max_words: 100

# ── Server ──
server:
  tree_explorer_port: 8420
  session_id_length: 8

# ── Pipeline ──
pipeline:
  default_data_file: "matched_data.jsonl"
  scheduler_interval: 600

# ── HWR ──
hwr:
  default: 0.5
  laplace_alpha: 1
  laplace_beta: 2
---

## Notes

Edit values above to tune system behavior. Regenerate pipeline outputs after changing ranking/scoring params.
```

---

## 2. Config Loader: `src/f007_infrastructure/config.py` (NEW)

```python
import os
import yaml
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config.md"
_cache = None

def _parse_frontmatter(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if not text.startswith("---"):
        return {}
    end = text.index("---", 3)
    return yaml.safe_load(text[3:end]) or {}

def load_config():
    global _cache
    if _cache is not None:
        return _cache
    path = os.environ.get("CONFIG_PATH", str(_CONFIG_PATH))
    _cache = _parse_frontmatter(path)
    return _cache

def reload_config():
    global _cache
    _cache = None
    return load_config()

def get(key, default=None):
    cfg = load_config()
    parts = key.split(".")
    for p in parts:
        if isinstance(cfg, dict):
            cfg = cfg.get(p)
        else:
            return default
        if cfg is None:
            return default
    return cfg
```

Add `pyyaml` to project dependencies.

---

## 3. Code Modifications (Exact Changes)

### 3.1 `src/f006_retrieval_engine/retrieval_ranking.py`

**Before:**
```python
RANKING_WEIGHTS = {"win_rate": 0.40, "vec_score": 0.30, "sas": 0.15, "bg_boost": 0.15}
```

**After:**
```python
from f007_infrastructure.config import get as _cfg

def _load_ranking_weights():
    return {
        "win_rate": _cfg("ranking_weights.win_rate", 0.40),
        "vec_score": _cfg("ranking_weights.vec_score", 0.30),
        "sas": _cfg("ranking_weights.sas", 0.15),
        "bg_boost": _cfg("ranking_weights.bg_boost", 0.15),
    }

RANKING_WEIGHTS = _load_ranking_weights()
```

**`compute_bg_boost()` — replace hardcoded boost values:**
```python
def compute_bg_boost(sentence_bg, query_bg):
    boost = 0.0
    s_industry = _first_val(sentence_bg.get("industry", ""))
    q_industry = query_bg.get("industry", "")
    if s_industry and q_industry and s_industry == q_industry:
        boost += _cfg("bg_boost.industry_match", 0.05)
    s_edu = _first_val(sentence_bg.get("education", ""))
    q_edu = query_bg.get("education", "")
    if s_edu and q_edu and s_edu == q_edu:
        boost += _cfg("bg_boost.education_match", 0.02)
    q_debt = _safe_int(query_bg.get("total_debt", 0))
    s_interest = _safe_int(sentence_bg.get("interest_ratio", 0))
    s_installment = _safe_int(sentence_bg.get("installment_ratio", 0))
    if q_debt > 0 and (s_interest > 0 or s_installment > 0):
        boost += _cfg("bg_boost.debt_interest_match", 0.03)
    s_age = _safe_int(sentence_bg.get("age", 0))
    q_age = _safe_int(query_bg.get("age", 0))
    age_threshold = _cfg("bg_boost.age_proximity_threshold", 10)
    if s_age > 0 and q_age > 0 and abs(s_age - q_age) <= age_threshold:
        boost += _cfg("bg_boost.age_proximity_match", 0.02)
    s_risk = _first_val(sentence_bg.get("risk_level", ""))
    q_risk = query_bg.get("risk_level", "")
    if s_risk and q_risk and s_risk == q_risk:
        boost += _cfg("bg_boost.risk_level_match", 0.03)
    if query_bg.get("recent_7d_repayment", False):
        boost += _cfg("bg_boost.recent_repayment_signal", 0.02)
    return boost
```

---

### 3.2 `src/f006_retrieval_engine/retrieval_engine.py`

**Line 11 — `POOL_CAP`:**
```python
from f007_infrastructure.config import get as _cfg
POOL_CAP = _cfg("pool_cap", 50)
```

**Line 119 — subset drop penalty:**
```python
conf = max(0.0, 1.0 - n_dropped * _cfg("confidence.subset_drop_penalty", 0.1))
```

**Line 125 — root fallback:**
```python
return root_nodes, _cfg("confidence.root_fallback", 0.2), ["root_fallback"]
```

**Line 147 — descend penalty:**
```python
confidence -= _cfg("confidence.descend_penalty", 0.05)
```

**Line 239 — context missing penalty:**
```python
confidence -= _cfg("confidence.context_missing_penalty", 0.1)
```

**Line 278 — descend fallback penalty:**
```python
confidence -= fallbacks.count("descend") * _cfg("confidence.descend_penalty", 0.05)
```

**Line 279 — bitmask relax penalty:**
```python
confidence -= fallbacks.count("bitmask_relax") * _cfg("confidence.bitmask_relax_penalty", 0.05)
```

---

### 3.3 `src/f009_api_server/server.py`

**Line 122 — embed fallback penalty:**
```python
from f007_infrastructure.config import get as _cfg
result["confidence"] = max(result.get("confidence", 1.0) - _cfg("confidence.embed_fallback_penalty", 0.1), 0.0)
```

---

### 3.4 `src/f008_state_extraction/state_extraction.py`

**Line 228 — keyword confidence formula:**
```python
from f007_infrastructure.config import get as _cfg
kw_base = _cfg("keyword_confidence.base", 0.3)
kw_per = _cfg("keyword_confidence.per_match", 0.1)
kw_ceil = _cfg("keyword_confidence.ceiling", 0.8)
kw_no_match = _cfg("keyword_confidence.no_match", 0.1)
confidence = min(kw_base + kw_per * len(matches), kw_ceil) if matches else kw_no_match
```

---

### 3.5 `src/f007_infrastructure/llm_client.py`

**Lines 12, 18 — model name and API base:**
```python
from f007_infrastructure.config import get as _cfg

def _get_client():
    return OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url=_cfg("llm.api_base", "https://api.deepseek.com"),
    )

def call_deepseek(prompt: str, temperature: float = None) -> str:
    if temperature is None:
        temperature = _cfg("llm.temperature", 0.1)
    client = _get_client()
    resp = client.chat.completions.create(
        model=_cfg("llm.model", "deepseek-chat"),
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return resp.choices[0].message.content

def call_deepseek_json(prompt: str, temperature: float = None) -> dict:
    if temperature is None:
        temperature = _cfg("llm.temperature", 0.1)
    text = call_deepseek(prompt, temperature)
    return json.loads(_strip_json(text))
```

---

### 3.6 `src/f007_infrastructure/embeddings.py`

**Lines 5-8 — embedding defaults:**
```python
from f007_infrastructure.config import get as _cfg

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", _cfg("embedding.model", "bge-m3"))
EMBEDDING_API_BASE = os.environ.get("EMBEDDING_API_BASE", _cfg("embedding.api_base", "http://localhost:11434/v1"))
EMBEDDING_API_KEY = os.environ.get("EMBEDDING_API_KEY", _cfg("embedding.api_key", "ollama"))
EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", _cfg("embedding.dimension", 1024)))
```

---

### 3.7 `src/f007_infrastructure/retry.py`

**Line 5 — default retry params:**
```python
from f007_infrastructure.config import get as _cfg

def retry_call(fn, *args, max_retries=None, min_sleep=None, max_sleep=None, on_fail=None, **kwargs):
    if max_retries is None:
        max_retries = _cfg("retry.max_retries", 3)
    if min_sleep is None:
        min_sleep = _cfg("retry.min_sleep", 1)
    if max_sleep is None:
        max_sleep = _cfg("retry.max_sleep", 5)
    # ... rest unchanged
```

---

### 3.8 `src/f005_context_scoring/scoring_metrics.py`

**Line 103 — HWR default:**
```python
from f007_infrastructure.config import get as _cfg

def compute_hwr(call_ids, reward_lookup):
    if not call_ids:
        return _cfg("hwr.default", 0.5)
    alpha = _cfg("hwr.laplace_alpha", 1)
    beta = _cfg("hwr.laplace_beta", 2)
    wins = sum(1 for cid in call_ids if reward_lookup.get(cid) == 1)
    total = len(call_ids)
    return (wins + alpha) / (total + beta)
```

**`compute_sas_for_pool` — ngram size:**
```python
def compute_sas_for_pool(sentences, embeddings_map=None):
    ngram_n = _cfg("sas.ngram_size", 2)
    if len(sentences) <= 1:
        return [1.0] * len(sentences)
    texts = [s.get("script_text", "") for s in sentences]
    tfidf = _build_tfidf_matrix(texts, ngram_range=ngram_n)
    # ... rest unchanged
```

---

### 3.9 `src/f007_infrastructure/db.py`

**Line 64 — HNSW params:**
```python
from f007_infrastructure.config import get as _cfg
# In index creation:
m = _cfg("hnsw.m", 16)
ef_construction = _cfg("hnsw.ef_construction", 64)
```

**Line 226 — trigram threshold:**
```python
threshold = _cfg("search.trigram_threshold", 0.01)
```

**Line 268 — taxonomy trigram threshold:**
```python
threshold = _cfg("search.taxonomy_trigram_threshold", 0.1)
```

**Search limits (lines 162, 205, 244):**
```python
limit = _cfg("search.vector_limit", 50)
limit = _cfg("search.keyword_limit", 20)
limit = _cfg("search.taxonomy_limit", 20)
```

---

### 3.10 `data/data_cleaning/data_clean_2.py`

**Line 242 — model name, line 239 — max_tokens, line 247 — temperature:**
```python
from f007_infrastructure.config import get as _cfg
model = _cfg("llm.model", "deepseek-chat")
max_tokens = _cfg("llm.max_tokens", 16384)
temperature = _cfg("llm.temperature", 0.1)
```

Same pattern for `data_logic.py` (line 216, 213, 221) and `data_complete.py` (line 361, 358, 366).

---

### 3.11 `src/f003_reward_labeling/reward_label.py`

**Line 53 — last N turns:**
```python
from f007_infrastructure.config import get as _cfg
last_n = _cfg("context_window.reward_last_n_turns", 6)
```

**Line 139 — explanation max words:**
```python
max_words = _cfg("reward.explanation_max_words", 100)
```

---

### 3.12 `src/f005_context_scoring/score_tree.py`

**Line 71 — conversation context window:**
```python
from f007_infrastructure.config import get as _cfg
window = _cfg("context_window.conversation_turns", 20)
```

**Line 74 — script prefix length:**
```python
prefix_len = _cfg("context_window.script_prefix_length", 50)
```

---

### 3.13 `src/f004_decision_tree/merge_collector.py`

**Lines 7, 15:**
```python
from f007_infrastructure.config import get as _cfg
MAX_MERGED_WORDS = _cfg("decision_tree.max_merged_words", 150)
ACK_MAX_WORDS = _cfg("decision_tree.ack_max_words", 15)
```

---

### 3.14 `src/f004_decision_tree/build_decision_tree.py`

**Line 287 — max levels:**
```python
from f007_infrastructure.config import get as _cfg
max_levels = _cfg("decision_tree.find_node_max_levels", 4)
```

---

### 3.15 `src/f004_decision_tree/serve_tree.py`

**Line 7:**
```python
from f007_infrastructure.config import get as _cfg
port = _cfg("server.tree_explorer_port", 8420)
```

---

### 3.16 `src/whole_pipeline.py`

**Line 272 — default data file:**
```python
from f007_infrastructure.config import get as _cfg
default=str(INPUT_DIR / _cfg("pipeline.default_data_file", "matched_data.jsonl")),
```

**Line 293 — scheduler interval:**
```python
default=_cfg("pipeline.scheduler_interval", 600),
```

---

### 3.17 Batch sizes (6 files)

| File | Current | After |
|------|---------|-------|
| `data/data_cleaning/data_clean_2.py` | `BATCH_SIZE = 1` | `BATCH_SIZE = _cfg("batch_size.data_cleaning", 1)` |
| `data/data_cleaning/data_logic.py` | `BATCH_SIZE = 1` | `BATCH_SIZE = _cfg("batch_size.data_cleaning", 1)` |
| `data/data_cleaning/data_complete.py` | `BATCH_SIZE = 1` | `BATCH_SIZE = _cfg("batch_size.data_cleaning", 1)` |
| `src/f003_reward_labeling/analyze_collector_turns.py` | `BATCH_SIZE = 20` | `BATCH_SIZE = _cfg("batch_size.analysis", 20)` |
| `src/f003_reward_labeling/analyze_customer_turns.py` | `BATCH_SIZE = 20` | `BATCH_SIZE = _cfg("batch_size.analysis", 20)` |
| `src/f000_keyword_discovery/keyword_prompts.py` | `BATCH_SIZE = 20` | `BATCH_SIZE = _cfg("batch_size.keyword_discovery", 20)` |

---

### 3.18 Context window sizes (3 files)

| File | Current | After |
|------|---------|-------|
| `src/f003_reward_labeling/analyze_customer_turns.py:104` | `3` | `_cfg("context_window.analysis_turns_before", 3)` |
| `src/f003_reward_labeling/define_willingness_levels.py:71` | `3` | `_cfg("context_window.analysis_turns_before", 3)` |
| `src/f000_keyword_discovery/discover_keywords.py:28` | `3` | `_cfg("context_window.analysis_turns_before", 3)` |

---

## 4. Files Modified Summary

| # | File | Params Externalized |
|---|------|-------------------|
| 1 | `config.md` (NEW) | All 99 values (excl. domain mappings) |
| 2 | `src/f007_infrastructure/config.py` (NEW) | Config loader |
| 3 | `src/f006_retrieval_engine/retrieval_ranking.py` | 4 ranking weights + 7 boost values + age threshold |
| 4 | `src/f006_retrieval_engine/retrieval_engine.py` | pool_cap + 6 confidence penalties |
| 5 | `src/f009_api_server/server.py` | 1 confidence penalty |
| 6 | `src/f008_state_extraction/state_extraction.py` | 4 keyword confidence params |
| 7 | `src/f007_infrastructure/llm_client.py` | model, api_base, temperature |
| 8 | `src/f007_infrastructure/embeddings.py` | 4 embedding params |
| 9 | `src/f007_infrastructure/retry.py` | 3 retry params |
| 10 | `src/f007_infrastructure/db.py` | 2 HNSW + 4 search params |
| 11 | `src/f005_context_scoring/scoring_metrics.py` | 3 HWR params + ngram size |
| 12 | `src/f005_context_scoring/score_tree.py` | 2 context window params |
| 13 | `src/f003_reward_labeling/reward_label.py` | 2 reward params |
| 14 | `src/f004_decision_tree/merge_collector.py` | 2 merge params |
| 15 | `src/f004_decision_tree/build_decision_tree.py` | 1 search depth param |
| 16 | `src/f004_decision_tree/serve_tree.py` | 1 port |
| 17 | `src/whole_pipeline.py` | 2 pipeline params |
| 18 | `data/data_cleaning/data_clean_2.py` | model, max_tokens, temperature, batch_size |
| 19 | `data/data_cleaning/data_logic.py` | model, max_tokens, temperature, batch_size |
| 20 | `data/data_cleaning/data_complete.py` | model, max_tokens, temperature, batch_size |
| 21 | `src/f003_reward_labeling/analyze_collector_turns.py` | batch_size |
| 22 | `src/f003_reward_labeling/analyze_customer_turns.py` | batch_size, context window |
| 23 | `src/f003_reward_labeling/define_willingness_levels.py` | batch_size, context window |
| 24 | `src/f000_keyword_discovery/keyword_prompts.py` | batch_size |
| 25 | `src/f000_keyword_discovery/discover_keywords.py` | context window |

---

## 5. Implementation Order

1. Create `config.md` with all default values (matches current hardcoded values exactly — zero behavior change)
2. Create `src/f007_infrastructure/config.py` loader
3. Add `pyyaml` to `pyproject.toml` dependencies
4. Modify files in dependency order: `config.py` → `llm_client.py` → `retry.py` → `embeddings.py` → `db.py` → `scoring_metrics.py` → `retrieval_ranking.py` → `retrieval_engine.py` → `server.py` → `state_extraction.py` → remaining files
5. Run full test suite — all tests must pass with defaults (no behavior change)
6. Add test for `config.py` loader (frontmatter parsing, dot-notation get, reload, missing key fallback)
