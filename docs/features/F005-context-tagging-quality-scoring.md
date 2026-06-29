---
id: F005
name: Context Tagging & Quality Scoring
status: complete
owner: agent
source: ROADMAP.md
created: 2026-06-18
updated: 2026-06-25
merged: 2026-06-22
depends_on: F004
---

# F005: Context Tagging & Quality Scoring

## Why

The retrieval engine (F006) needs two capabilities that the current decision tree lacks: (1) **context filtering** — only recommend scripts compatible with the customer's profile (e.g. don't suggest a mortgage-related script to a customer without a mortgage), and (2) **quality ranking** — when multiple scripts match a state, prefer those with higher historical win rates and semantic similarity. Without these, the engine returns unfiltered, unranked results.

## What

### Context Tagging (Bitmask Encoding)

Tag each sentence in the decision tree with `bg_constraints` derived from the source conversation's `context` fields (from F001's `output_aligned.py`). Encode as a bitmask for O(1) filtering at retrieval time.

The 10 bitmask fields (from ADR-020):

| Bit | Field | Source |
|-----|-------|--------|
| 0 | `has_auto_loan` | context.has_auto_loan |
| 1 | `has_mortgage` | context.has_mortgage |
| 2 | `has_negotiation_history` | context.has_negotiation_history |
| 3 | `social_insurance_stable` | context.social_insurance_stable |
| 4 | `credit_rating_good` | context.credit_rating == "good" |
| 5 | `card_restricted` | context.card_restricted |
| 6 | `is_cash_out_customer` | context.is_cash_out_customer |
| 7 | `has_complaint_history` | context.has_complaint_history |
| 8 | `has_legal_tools` | context.has_legal_tools |
| 9 | `is_negotiation_brain_customer` | context.is_negotiation_brain_customer |

Numeric fields (total_debt, external_debt, days_delinquent) and list fields (available_plans) are not bitmask-encoded — they are available as `bg_constraints` dict for range/list filtering if needed later.

### Quality Scoring

Compute two scores per sentence:

1. **HWR (Historical Win Rate)** — Node-level aggregation with sentence-level blending. Node HWR = Laplace-smoothed win rate across all conversations passing through the node. Sentence `win_rate = weight * sentence_hwr + (1 - weight) * node_hwr` where `weight = n / (n + 2)`. For low-n sentences (1-2 calls), the node baseline dominates; for high-n sentences (5+ calls), the sentence-specific rate dominates. `win_rate_node` stored for transparency.
2. **SAS (Script Alignment Score)** — Char bigram TF-IDF cosine similarity between the sentence and the most successful script (highest HWR) in the same node's pool (ADR-020: numpy-only, no external API).

Deferred metrics:
- **UC (Uplift Contribution)** = 0 with `deferred: true`
- **CSI (Context Similarity Index)** = 0 with `deferred: true`

### Output

Augmented decision tree written to `/src/decision_tree_scored.json`. Structure is identical to `decision_tree.json` with additional fields on each sentence entry.

## Passing Criteria

- Every sentence has `bg_constraints` dict with all 10 bitmask fields
- Every sentence has `bg_bitmask` integer
- Every sentence has `bg_bitmask_int` integer (0–1023)
- Every sentence has `win_rate` (blended HWR) ≥ 0
- Every sentence has `win_rate_node` (node-level HWR) ≥ 0
- Every sentence has `sas` ≥ 0
- `uplift_score` = 0 and `csi` = 0 with `deferred: true`
- Bitmask AND filtering produces correct subset

## Acceptance Criteria

- [x] Every sentence in decision_tree_scored.json has `bg_constraints` dict with 10 fields
- [x] Every sentence has `bg_bitmask` integer (0–1023)
- [x] `bg_bitmask_int` correctly encodes the 10 boolean fields
- [x] Every sentence has `win_rate` ≥ 0 and ≤ 1
- [x] `win_rate` blends sentence-level and node-level HWR: `weight * sentence_hwr + (1 - weight) * node_hwr` where `weight = n / (n + 2)`
- [x] Every sentence has `win_rate_node` ≥ 0 and ≤ 1
- [x] Every sentence has `sas` ≥ 0 and ≤ 1
- [x] `sas` computed via char bigram TF-IDF cosine similarity (ADR-020)
- [x] `uplift_score` = 0 and `csi` = 0 with `deferred: true` on every sentence
- [x] Bitmask AND filtering: sentence with bitmask S is compatible with context bitmask C iff (S & C) == S
- [x] All 31 conversations represented in scored tree
- [x] Output file: `/src/decision_tree_scored.json`

## Dependencies

- F004 (Decision Tree Construction) — `decision_tree.json` provides the tree structure and sentence pools
- F003 (Reward Labeling) — `output_rewarded.py` provides reward labels for HWR computation
- F001 (Data Schema Alignment) — `output_aligned.py` provides context fields for bitmask encoding

## Links

- [ROADMAP.md](../ROADMAP.md) — dependency graph + architecture decisions
- [ADR-006](../decisions/ADR-006-context-constraint-mapping.md) — Context constraint mapping (9 fields → 5 bitmask)
- [ADR-020](../decisions/ADR-020-f005-bitmask-scoring-design.md) — Bitmask encoding, HWR, SAS design
- [ADR-024](../decisions/ADR-024-embedding-architecture.md) — Embedding architecture (bge-m3 replaces TF-IDF for vector similarity)

## Implementation Plan

See [implementation-plan.md](F005-implementation-plan.md)

## Design Decisions

- **10 bitmask fields**: All boolean-derivable fields are bitmask-encoded (has_auto_loan, has_mortgage, has_negotiation_history, social_insurance_stable, credit_rating_good, card_restricted, is_cash_out_customer, has_complaint_history, has_legal_tools, is_negotiation_brain_customer). Numeric fields (total_debt, external_debt, days_delinquent) and list fields (available_plans) remain in bg_constraints dict for potential range/list filtering in F006.
- **Intersection merge for multi-source sentences**: 28 sentences have multiple source_call_ids. Their bg_constraints use bitwise AND (intersection) of all source conversation constraints — only constraints present in ALL source conversations are set. This is conservative: intersection=0 means the sentence was used in diverse contexts and is broadly applicable.
- **Bitmask compatibility check**: `(sentence_bitmask & query_bitmask) == sentence_bitmask` — every constraint the sentence requires must be present in the query context. A sentence with bitmask 0 is universally compatible.
- **HWR with node-level aggregation**: Sentence-level HWR is unreliable for sentences appearing in only 1-2 calls. Instead, compute node HWR from all `source_call_ids` across the node's entire sentence pool, then blend: `win_rate = weight * sentence_hwr + (1 - weight) * node_hwr` where `weight = n / (n + 2)` (shrinks toward node baseline for low-n sentences). Node HWR stored as `win_rate_node` for transparency. Laplace smoothing `(wins + 1) / (total + 2)` prevents 0/0.
- **SAS via char bigram TF-IDF cosine similarity**: Within each node's sentence pool, the sentence with highest HWR is the reference. SAS = cosine_similarity(tfidf(sentence), tfidf(reference)). Char bigram TF-IDF computed with numpy only (no external API, per ADR-020). If only 1 sentence in pool, SAS = 1.0.
- **UC and CSI deferred**: `uplift_score = 0` and `csi = 0` with `deferred: true`. These require causal analysis and additional data not available at 31-record scale.
- **Output preserves tree structure**: `decision_tree_scored.json` is identical to `decision_tree.json` with additional fields (`bg_constraints`, `bg_bitmask`, `bg_bitmask_int`, `bg_background`, `win_rate`, `win_rate_node`, `sas`, `uplift_score`, `csi`, `conversation_context`, `context_vec_id`) on each sentence entry. No structural changes to nodes or edges.
- **Score display in UI**: `tree_explorer.html` loads `decision_tree_scored.json` and renders HWR/SAS as colored progress bars per sentence (green ≥60%/70%, amber 40-60%/40-70%, red <40%). Context bitmask shown as binary string. Bars use absolute-positioned fill inside track for unified appearance.

## Files

| File | Purpose |
|------|---------|
| `src/f005_context_scoring/score_tree.py` | Context tagging, HWR, SAS computation, scored tree output |
| `src/test_score_tree.py` | Unit tests for scoring functions |
| `src/test_score_tree_integration.py` | Integration tests on real scored tree |
| `src/f005_context_scoring/decision_tree_scored.json` | Generated output (augmented decision tree) |
