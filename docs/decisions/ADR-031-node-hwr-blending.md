# ADR-031: Node HWR Blending

**Date:** 2026-07-07
**Status:** Accepted

## Context

Sentence-level HWR (Historical Win Rate) is unreliable for sentences appearing in only 1-2 calls — a single win/loss swings the rate to 0 or 1. The guideline (Step 1.6) documents node-level aggregation as the solution, but it was never implemented. All 782 sentences lacked `win_rate_node`.

## Decision

Compute node-level HWR from the union of all `source_call_ids` across the node's entire sentence pool, then blend with sentence-level:

```
node_hwr = Laplace(wins_node, total_node)
sentence_hwr = Laplace(wins_sentence, total_sentence)
weight = n / (n + 2)  where n = len(sentence.source_call_ids)
win_rate = weight * sentence_hwr + (1 - weight) * node_hwr
win_rate_node = node_hwr
```

For low-n sentences (1-2 calls), `weight` is small → node baseline dominates. For high-n sentences (5+ calls), sentence-specific rate dominates.

## Consequences

- Every sentence now has `win_rate_node` for transparency
- `win_rate` is a blended score, more stable for low-frequency sentences
- Edge case: empty pool → skip (no scoring)
- Backward compat: `win_rate` field name unchanged; `win_rate_node` is additive
