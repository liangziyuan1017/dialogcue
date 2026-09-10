---
REMOVED_FIELD_id: ADR-039
title: Single Winner Per Utterance in merge_state
status: accepted
created: 2026-07-10
updated: 2026-07-10
decision_type: architecture
feature_ids: [F008]
---

# ADR-039: Single Winner Per Utterance in merge_state

## Context

`merge_state` in `state_extraction.py` added **all** new facts and emotions from the current extraction to `inherited_facts` / `inherited_emotions`, then removed the winner (last fact/emotion/action) from inherited and set it as `branch_key`. This meant that on the **first** customer utterance, `inherited_facts` and `inherited_emotions` were already populated with non-winner labels from the same extraction — even though there were zero prior turns to "inherit" from.

Example: first utterance extracts 3 facts `["situational_hardship", "repayment_inability", "willing_to_pay"]` and 4 emotions. Result was:
```
branch_key: {facts: [willing_to_pay]}
inherited_facts: [situational_hardship, repayment_inability]  ← wrong, no prior turns
inherited_emotions: [defensive, anxiety, complaint, despair]   ← wrong, no prior turns
```

The docstring said "every other new label is absorbed into inherited" — this was the intended design, but it violated the semantic meaning of `inherited_*` (labels from **prior** branching decisions, not from the same utterance).

## Decision

**Only the previous `branch_key` is pushed to `inherited_*`. Non-winner labels from the same extraction are dropped.**

Removed lines 403-408 in `merge_state`:
```python
# REMOVED — these added ALL new facts/emotions to inherited
for f in new_facts:
    if f not in inh_facts:
        inh_facts.append(f)
for e in new_emotions:
    if e not in inh_emotions:
        inh_emotions.append(e)
```

The remaining logic (lines 394-401) that pushes the **previous** `branch_key` to `inherited_*` is unchanged and correct.

After fix:
- **First utterance** (3 facts + 4 emotions): `branch_key = {facts: [willing_to_pay]}`, `inherited_facts = []`, `inherited_emotions = []`
- **Second utterance** (new fact `billing_dispute`): previous `willing_to_pay` pushed to `inherited_facts`, `branch_key = {facts: [billing_dispute]}`, `inherited_facts = [willing_to_pay]`

## Why

- `inherited_*` means "from ancestors/prior turns" — populating it on the first turn is semantically wrong
- A single utterance should set one `branch_key` (the primary label), not simulate a deep tree path
- The retrieval engine (`_find_matching_nodes_subset`) uses `path_state_to_flat(inherited_* + branch_key)` to find matching tree nodes — fewer labels means shallower, more general node matching instead of over-specifying the path
- Non-winner labels from the same utterance are lower-priority signals that shouldn't drive tree navigation

## Consequences

- `inherited_facts` and `inherited_emotions` are empty on the first utterance regardless of how many labels the LLM extracts
- Non-winner facts/emotions from the same utterance are dropped (not accumulated)
- Prior `inherited_*` labels are preserved (we only stopped adding *new* same-turn labels)
- Idempotency preserved: second application of same extraction finds winner already in `seen_facts` → no change
- All 24 existing tests pass without modification
- Downstream: `recommend()` receives fewer facts per turn → matches shallower tree nodes → broader candidate pools
