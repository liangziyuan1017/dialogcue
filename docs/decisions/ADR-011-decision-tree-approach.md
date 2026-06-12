---
id: ADR-011
title: Collector Decision Tree with Customer Response Branching
status: accepted
created: 2026-06-11
updated: 2026-06-11
decision_type: architecture
feature_ids: [F004]
---

# ADR-011: Collector Decision Tree with Customer Response Branching

## Context

F004 requires building a traversable decision tree from 31 annotated conversations. The tree must support exact state matching, fallback via progressive tag removal, and accumulate collector sentences at each node for script recommendation.

Initial implementation used composite state key (facts + emotions + willingness + action) as node identity, producing a chain structure (323/357 nodes had exactly 1 child) because each conversation's full state sequence is unique.

## Decision

**Nodes are collector action points. Branches are customer response profiles. Endpoints are consolidated.**

- **Node** = a point where the collector must decide what to say (keyed by `action`)
- **Branch** = customer response that led here (keyed by `facts + emotions` only)
- **Willingness** = label on each sentence in the pool, NOT a branching factor
- **Sentence pool** = collector scripts at this node, each tagged with `customer_willingness`
- **Opening node** = single root (`initial_contact`) with `gesture_type: "opening"` on greeting sentences
- **Normal end node** = single `normal_end` child of root, consolidating all properly-closed dialog ending sentences
- **Abrupt end node** = single `abrupt_end` child of root, for all dialogs without proper closings

A new decision point is created ONLY when the customer introduces new facts or new emotions. Willingness-only changes (e.g., conditional → negotiating) do NOT create new branches — the customer is warming up within the same state.

The tree has exactly 3 structural anchors: 1 opening node (root), 1 normal_end, 1 abrupt_end. Both end nodes are direct children of root. All intermediate decision branches flow between the opening and one of the two end nodes.

### Merge Rule

Two customer responses merge into the same branch if they have the same `(facts, emotions)`, regardless of willingness. This collapsed 93 unique customer states into 64 decision points.

### Merge List (7 groups merged)

| # | facts | emotions | Willingness levels merged |
|---|-------|----------|--------------------------|
| 1 | ∅ | ∅ | conditional(15) + weak(10) + negotiating(6) + strong(4) |
| 2 | financial_hardship | ∅ | weak(4) + none(4) + negotiating(1) |
| 3 | ∅ | pleading | none(1) + conditional(1) + negotiating(1) |
| 4 | financial_hardship, multiple_debts | ∅ | conditional(1) + weak(1) + none(1) |
| 5 | multiple_debts | ∅ | conditional(1) + none(1) |
| 6 | ∅ | skepticism | negotiating(1) + none(1) |
| 7 | financial_hardship | helplessness | none(1) + resistant(1) |

### Fallback

If exact (facts, emotions) branch not found, progressively remove the least-discriminative tags (emotions first, then facts) until a match is found.

## Why

The old model produced chains because willingness created spurious branches. In reality, willingness is a property of the customer at a given decision point, not a reason to diverge. The collector needs to see "under financial_hardship, when customer is weak I say X, when customer is negotiating I say Y" — both under the same branch.

## Consequences

- Tree now branches on genuinely different customer situations (64 decision points vs 93 before)
- Willingness is preserved as metadata on each sentence for ranking/filtering
- Rare facts are kept as separate branches (not bucketed) for future data expansion
- Fallback may return scripts from a broader state than ideal
- Tree has exactly 2 terminal nodes (normal_end + abrupt_end) regardless of data size
- All ending gesture sentences are consolidated into normal_end; all abrupt terminations into abrupt_end
- Tree renders vertically: opening at top → decision branches → two end nodes at bottom
