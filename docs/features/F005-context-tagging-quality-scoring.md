---
id: F005
name: Context Tagging & Quality Scoring
status: merged
owner: agent
source: superseded (original spec plan_feature_base.md no longer in repo)
created: 2026-06-18
updated: 2026-07-15
merged: 2026-06-22
depends_on: F004
---

# F005: Context Tagging & Quality Scoring

## Why

The retrieval engine (F006) needs two capabilities that the current decision tree lacks: (1) **context filtering** — only recommend scripts compatible with the customer's profile (e.g. don't suggest a mortgage-related script to a customer without a mortgage), and (2) **quality ranking** — when multiple scripts match a state, prefer those with higher historical win rates and semantic similarity. Without these, the engine returns unfiltered, unranked results.

## What

### Context Tagging (Bitmask Encoding)

Tag each sentence in the decision tree with `bg_constraints` derived from the source conversation's `context` fields (from F001's `output_aligned.py`). Encode as a bitmask for O(1) filtering at retrieval time.

The 10 bitmask fields (from ADR-006's 18 custInfo-derived context fields — boolean-derivable fields suitable for binary encoding):

| Bit | Field | Source |
|-----|-------|--------|
| 0 | `has_business_loan` | context.has_business_loan |
| 1 | `has_mortgage` | context.has_mortgage |
| 2 | `has_other_loan` | context.has_other_loan |
| 3 | `recent_repayment` | context.recent_repayment |
| 4 | `is_high_risk_proxy_complaint` | context.is_high_risk_proxy_complaint |
| 5 | `is_proxy_intermediary_complaint` | context.is_proxy_intermediary_complaint |
| 6 | `has_social_insurance` | context.has_social_insurance |
| 7 | `has_risk_flag` | context.risk_level > 0 |
| 8 | `has_complaint` | context.complaint_score > 0 |
| 9 | `has_vehicle` | context.vehicle_count > 0 |

Numeric/categorical fields not bitmask-encoded — stored in `bg_background` dict (see below) for `bg_boost` range/categorical matching. Balance fields are stored as **digit counts** (e.g. `142870` → `6`, `0` → `0`) to normalize magnitude for similarity comparison.

### Quality Scoring

Compute three scores per sentence:

1. **HWR (Historical Win Rate)** — Node-level aggregation with sentence-level blending. Node HWR = Laplace-smoothed win rate across all conversations passing through the node. Sentence `win_rate = weight * sentence_hwr + (1 - weight) * node_hwr` where `weight = n / (n + 2)`. For low-n sentences (1-2 calls), the node baseline dominates; for high-n sentences (5+ calls), the sentence-specific rate dominates. `win_rate_node` stored for transparency.
2. **SAS (Script Alignment Score)** — Word bigram TF-IDF cosine similarity between the sentence and the most successful script (highest HWR) in the same node's pool. Uses jieba word segmentation (not character ngrams) to avoid vocabulary explosion on Chinese text. Vocabulary is restricted to ngrams present in the reference document only, making the TF-IDF matrix `(n_docs, |ref_ngrams|)` instead of `(n_docs, millions)`. No external API — deterministic, sufficient for intra-pool diversity.
3. **Conversation Context Embedding** — DeepSeek embedding of `conversation_context` → 768-dim float32 vector stored in `embedding` field. Used at retrieval time (F006) for pgvector cosine similarity (`vec_score`). Captures cross-conversation semantic matching beyond surface character overlap.

Deferred metrics:
- **UC (Uplift Contribution)** = 0 with `deferred: true`
- **CSI (Context Similarity Index)** = 0 with `deferred: true`

### Output

Augmented decision tree written to `/src/decision_tree_scored.json`. Structure is identical to `decision_tree.json` with additional fields on each sentence entry.

## Passing Criteria

- Every sentence has `bg_constraints` dict with all 10 bitmask fields
- Every sentence has `bg_bitmask` integer
- Every sentence has `win_rate` (blended HWR) ≥ 0
- Every sentence has `win_rate_node` (node-level HWR) ≥ 0
- Every sentence has `sas` ≥ 0
- Embeddings (1024-dim bge-m3) persisted to PostgreSQL only; `decision_tree_scored.json` strips vectors (per guideline). `conversation_context` field present in JSON.
- `uplift_score` = 0 and `csi` = 0 with `deferred: true`
- Bitmask AND filtering produces correct subset

## Acceptance Criteria

- [ ] Every sentence in decision_tree_scored.json has `bg_constraints` dict with 10 fields
- [ ] Every sentence has `bg_bitmask` integer (0–1023)
- [ ] `bg_bitmask` correctly encodes the 10 boolean fields
- [ ] Every sentence has `win_rate` ≥ 0 and ≤ 1
- [ ] `win_rate` blends sentence-level and node-level HWR: `weight * sentence_hwr + (1 - weight) * node_hwr` where `weight = n / (n + 2)`
- [ ] Every sentence has `win_rate_node` ≥ 0 and ≤ 1
- [ ] `win_rate` blends sentence-level and node-level HWR: `weight * sentence_hwr + (1 - weight) * node_hwr` where `weight = n / (n + 2)`
- [ ] Every sentence has `sas` ≥ 0 and ≤ 1
- [ ] `sas` computed via jieba word bigram TF-IDF cosine similarity (reference-vocabulary-restricted)
- [ ] Embeddings (1024-dim bge-m3) persisted to PostgreSQL only; `decision_tree_scored.json` has no `embedding` field; `conversation_context` present
- [ ] `uplift_score` = 0 and `csi` = 0 with `deferred: true` on every sentence
- [ ] Bitmask AND filtering: sentence with bitmask S is compatible with context bitmask C iff (S & C) == S
- [ ] All 103 conversations represented in scored tree
- [ ] Output file: `/src/decision_tree_scored.json`

### `bg_background` fields (for `bg_boost` matching)

Balance fields are stored as **digit counts** (`len(str(abs(value)))` for value > 0, else `0`) to normalize magnitude.

| Field | Source | Transform |
|-------|--------|-----------|
| `business_loan_digits` | context.business_loan_balance | digit count (0→0, 142870→6) |
| `mortgage_balance_digits` | context.mortgage_balance | digit count |
| `other_loan_digits` | context.other_loan_balance | digit count |
| `wealth_digits` | context.wealth_value | digit count |
| `current_balance_digits` | context.current_balance | digit count |
| `education` | context.education | categorical (passthrough) |
| `days_delinquent` | context.days_delinquent | int (passthrough) |
| `recent_contact_count` | context.recent_contact_count | int (passthrough) |
| `risk_level` | context.risk_level | int (passthrough) |
| `complaint_score` | context.complaint_score | int (passthrough) |

## Dependencies

- F004 (Decision Tree Construction) — `decision_tree.json` provides the tree structure and sentence pools
- F003 (Reward Labeling) — `output_rewarded.py` provides reward labels for HWR computation
- F001 (Data Schema Alignment) — `output_aligned.py` provides context fields for bitmask encoding

## Links

- ~~plan_feature_base.md~~ — original spec (no longer in repo; this doc is the authoritative source)
- [ADR-006](../../decisions/ADR-006-context-constraint-mapping.md) — Context constraint mapping (18 fields → 10 bitmask; pre-migration 21 fields)

## Implementation Plan

See [implementation-plan.md](implementation-plan.md)

## Design Decisions

- **10 bitmask fields from 18 custInfo-derived context fields**: Boolean-derivable fields are bitmask-encoded (has_business_loan, has_mortgage, has_other_loan, recent_repayment, is_high_risk_proxy_complaint, is_proxy_intermediary_complaint, has_social_insurance, has_risk_flag [risk_level>0], has_complaint [complaint_score>0], has_vehicle [vehicle_count>0]). Remaining numeric/categorical fields go into `bg_background` for `bg_boost` matching, with balance fields stored as digit counts (e.g. `142870` → `6`).
- **Intersection merge for multi-source sentences**: 28 sentences have multiple source_call_ids. Their bg_constraints use bitwise AND (intersection) of all source conversation constraints — only constraints present in ALL source conversations are set. This is conservative: intersection=0 means the sentence was used in diverse contexts and is broadly applicable.
- **Bitmask compatibility check**: `(sentence_bitmask & query_bitmask) == sentence_bitmask` — every constraint the sentence requires must be present in the query context. A sentence with bitmask 0 is universally compatible.
- **HWR with node-level aggregation**: Sentence-level HWR is unreliable for sentences appearing in only 1-2 calls. Instead, compute node HWR from all `source_call_ids` across the node's entire sentence pool, then blend: `win_rate = weight * sentence_hwr + (1 - weight) * node_hwr` where `weight = n / (n + 2)` (shrinks toward node baseline for low-n sentences). Node HWR stored as `win_rate_node` for transparency. Laplace smoothing `(wins + 1) / (total + 2)` prevents 0/0.
- **SAS via jieba word bigram TF-IDF cosine similarity (reference-vocabulary-restricted)**: Within each node's sentence pool, the sentence with highest HWR is the reference. SAS = cosine_similarity(embed(sentence), embed(reference)). If only 1 sentence in pool, SAS = 1.0. Uses jieba word segmentation + word-level bigrams (not character bigrams) to avoid vocabulary explosion on Chinese text (~millions of unique char bigrams → OOM). Vocabulary is restricted to ngrams appearing in the reference document only, so the TF-IDF matrix is `(n_docs, |ref_ngrams|)` — typically a few hundred columns instead of millions. Uses local TF-IDF + numpy cosine (no external API).
- **DeepSeek embedding for conversation context**: Each sentence's `conversation_context` (~100 words) is embedded via DeepSeek embedding API → 768-dim vector stored in `embedding` field. At retrieval time, pgvector cosine similarity provides `vec_score` for cross-conversation semantic matching. This captures meaning beyond surface word overlap that TF-IDF word-bigram misses.
- **UC and CSI deferred**: `uplift_score = 0` and `csi = 0` with `deferred: true`. These require causal analysis and additional data not available at 31-record scale.
- **Output preserves tree structure**: `decision_tree_scored.json` is identical to `decision_tree.json` with additional fields (`bg_constraints`, `bg_bitmask`, `bg_bitmask_int`, `bg_background`, `win_rate`, `win_rate_node`, `sas`, `uplift_score`, `csi`) on each sentence entry. No structural changes to nodes or edges.
- **Score display in UI**: `tree_explorer.html` loads `decision_tree_scored.json` and renders HWR/SAS as colored progress bars per sentence (green ≥60%/70%, amber 40-60%/40-70%, red <40%). Context bitmask shown as binary string. Bars use absolute-positioned fill inside track for unified appearance.

## Files

| File | Purpose |
|------|---------|
| `src/f005_context_scoring/score_tree.py` | Context tagging, HWR, SAS computation, scored tree output |
| `src/f005_context_scoring/scoring_metrics.py` | Bitmask encoding, HWR, SAS (jieba word bigram TF-IDF), cosine similarity |
| `src/tests/f005_context_scoring/test_score_tree_scoring.py` | Unit tests for scoring functions |
| `src/tests/f005_context_scoring/test_sas_jieba.py` | Standalone SAS smoke test with Chinese text samples |
| `src/decision_tree_scored.json` | Generated output (augmented decision tree) |
