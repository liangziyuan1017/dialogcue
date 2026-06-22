---
id: F005
name: Context Tagging & Quality Scoring
status: in-progress
owner: agent
source: plan_feature_base.md
created: 2026-06-18
updated: 2026-06-22
merged: 2026-06-18
depends_on: F004
---

# F005: Context Tagging & Quality Scoring

## Why

The retrieval engine (F006) needs two capabilities that the current decision tree lacks: (1) **context filtering** — only recommend scripts compatible with the customer's profile (e.g. don't suggest a mortgage-related script to a customer without a mortgage), and (2) **quality ranking** — when multiple scripts match a state, prefer those with higher historical win rates and semantic similarity. Without these, the engine returns unfiltered, unranked results.

## What

### Context Tagging (Bitmask Encoding)

Tag each sentence in the decision tree with `bg_constraints` derived from the source conversation's `context` fields (from F001's `output_aligned.py`). Encode as a bitmask for O(1) filtering at retrieval time.

The 10 bitmask fields (boolean/categorical fields suitable for binary encoding):

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

Additional context fields (numeric/categorical, not bitmask-encoded, available in `bg_constraints` dict for range/list filtering):

| Field | Type | Source |
|-------|------|--------|
| `total_debt` | int | customer_info.总欠款 |
| `external_debt` | int | customer_info.外部欠款金额 |
| `days_delinquent` | int | mob_typ → M1=30, M2=60, ... |
| `available_plans` | list[str] | customer_info.当前可使用的协商方案 |
| `external_debt_institutions` | int | customer_info.外部共债机构数 (parse "共N家") |
| `interest_ratio` | float | customer_info.利息占欠款比例 (parse "N%") |
| `installment_ratio` | float | customer_info.分期金额占欠款比例 (parse "N%") |
| `age` | int | customer_info.年龄 |
| `gender` | str | customer_info.性别 |
| `education` | str | customer_info.学历 → mapped enum |
| `industry` | str | customer_info.行业 |

### Quality Scoring

Compute two scores per sentence:

1. **HWR (Historical Win Rate)** — Laplace-smoothed ratio of R=1 conversations using this sentence to total conversations using this sentence. `HWR_smoothed = (wins + 1) / (total + 2)`.
2. **SAS (Script Alignment Score)** — DeepSeek embedding cosine similarity between the sentence and the most successful script (highest HWR) in the same node's pool.

Deferred metrics:
- **UC (Uplift Contribution)** = 0 with `deferred: true`
- **CSI (Context Similarity Index)** = 0 with `deferred: true`

### Output

Augmented decision tree written to `/src/decision_tree_scored.json`. Structure is identical to `decision_tree.json` with additional fields on each sentence entry.

## Passing Criteria

- Every sentence has `bg_constraints` dict with all 10 bitmask fields
- Every sentence has `bg_bitmask` integer (0–1023)
- Every sentence has `win_rate` (HWR_smoothed) ≥ 0
- Every sentence has `sas` ≥ 0
- `uplift_score` = 0 and `csi` = 0 with `deferred: true`
- Bitmask AND filtering produces correct subset

## Acceptance Criteria

- [ ] Every sentence in decision_tree_scored.json has `bg_constraints` dict with 10 fields
- [ ] Every sentence has `bg_bitmask` integer (0–1023)
- [ ] `bg_bitmask` correctly encodes the 10 boolean fields
- [ ] Every sentence has `win_rate` ≥ 0 and ≤ 1
- [ ] `win_rate` uses Laplace smoothing: (wins + 1) / (total + 2)
- [ ] Every sentence has `sas` ≥ 0 and ≤ 1
- [ ] `sas` computed via DeepSeek embedding cosine similarity
- [ ] `uplift_score` = 0 and `csi` = 0 with `deferred: true` on every sentence
- [ ] Bitmask AND filtering: sentence with bitmask S is compatible with context bitmask C iff (S & C) == S
- [ ] All 31 conversations represented in scored tree
- [ ] Output file: `/src/decision_tree_scored.json`

## Dependencies

- F004 (Decision Tree Construction) — `decision_tree.json` provides the tree structure and sentence pools
- F003 (Reward Labeling) — `output_rewarded.py` provides reward labels for HWR computation
- F001 (Data Schema Alignment) — `output_aligned.py` provides context fields for bitmask encoding

## Links

- [plan_feature_base.md](../../plan_feature_base.md) — F005 spec
- [ADR-006](../../decisions/ADR-006-context-constraint-mapping.md) — Context constraint mapping (9 fields → 5 bitmask)

## Implementation Plan

See [F005-implementation-plan.md](F005-implementation-plan.md)

## Design Decisions

- **10 bitmask fields from 21 context fields**: Boolean-derivable fields are bitmask-encoded (has_auto_loan, has_mortgage, has_negotiation_history, social_insurance_stable, credit_rating_good, card_restricted, is_cash_out_customer, has_complaint_history, has_legal_tools, is_negotiation_brain_customer). Numeric fields (total_debt, external_debt, days_delinquent, external_debt_institutions, interest_ratio, installment_ratio, age) and categorical/list fields (available_plans, gender, education, industry) remain in bg_constraints dict for potential range/list filtering in F006.
- **Intersection merge for multi-source sentences**: 28 sentences have multiple source_call_ids. Their bg_constraints use bitwise AND (intersection) of all source conversation constraints — only constraints present in ALL source conversations are set. This is conservative: intersection=0 means the sentence was used in diverse contexts and is broadly applicable.
- **Bitmask compatibility check**: `(sentence_bitmask & query_bitmask) == sentence_bitmask` — every constraint the sentence requires must be present in the query context. A sentence with bitmask 0 is universally compatible.
- **HWR with Laplace smoothing**: `(wins + 1) / (total + 2)`. With 6 R=1 / 25 R=0 across 31 records, Laplace smoothing prevents 0/0 and provides reasonable priors. A sentence used in 1 R=1 conversation gets HWR = 2/3 ≈ 0.67; a sentence used in 1 R=0 conversation gets HWR = 1/3 ≈ 0.33.
- **SAS via DeepSeek embedding cosine similarity**: Within each node's sentence pool, the sentence with highest HWR is the reference. SAS = cosine_similarity(embed(sentence), embed(reference)). If only 1 sentence in pool, SAS = 1.0. Uses existing `llm_client.py` DeepSeek API.
- **UC and CSI deferred**: `uplift_score = 0` and `csi = 0` with `deferred: true`. These require causal analysis and additional data not available at 31-record scale.
- **Output preserves tree structure**: `decision_tree_scored.json` is identical to `decision_tree.json` with additional fields (`bg_constraints`, `bg_bitmask`, `win_rate`, `sas`, `uplift_score`, `csi`) on each sentence entry. No structural changes to nodes or edges.

## Files

| File | Purpose |
|------|---------|
| `src/score_tree.py` | Context tagging, HWR, SAS computation, scored tree output |
| `src/test_score_tree.py` | Unit tests for scoring functions |
| `src/test_score_tree_integration.py` | Integration tests on real scored tree |
| `src/decision_tree_scored.json` | Generated output (augmented decision tree) |
