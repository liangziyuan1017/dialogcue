---
id: ADR-011
title: State-Transition Decision Tree with Sentence Pool Accumulation
status: accepted
created: 2026-06-11
decision_type: architecture
feature_ids: [F004]
---

# ADR-011: State-Transition Decision Tree with Sentence Pool Accumulation

## Context

F004 requires building a traversable decision tree from 31 annotated conversations. The tree must support exact state matching, fallback via progressive tag removal, and accumulate collector sentences at each node for script recommendation.

## Decision

Build a tree where each node represents a composite state (facts + emotions + willingness + action). Edges are state transitions from conversation paths. Collector turns at each node accumulate into a `sentence_pool` with provenance (`source_call_ids`). Near-identical states merge by comparing sorted state keys.

Fallback: if exact state not found, progressively remove the least-discriminative tags (emotions first, then facts) until a match is found.

## Why

A tree structure enables O(depth) traversal for real-time recommendation. Sentence pools at nodes provide multiple script options per state. Progressive tag removal is a simple, deterministic fallback that degrades gracefully.

## Consequences

- Tree depth is bounded by max conversation length (~40 turns)
- Near-identical state merging may collapse distinct paths — acceptable for 31 records
- Fallback may return scripts from a broader state than ideal
