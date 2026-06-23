---
id: ADR-022
title: Redundant Emotion Collapse
status: accepted
created: 2026-06-23
updated: 2026-06-23
decision_type: architecture
feature_ids: [F004]
---

# ADR-022: Redundant Emotion Collapse

## Context

`_collapse_redundant_facts` (ADR-018) removes fact nodes whose facts are already inherited from the parent chain. But the same redundancy exists for emotions: a customer who is already on an `anger` branch and expresses anger again creates a nested `anger → anger` path. This is semantically identical to being angry once — the second anger node adds no information and appears as a duplicate in the UI.

Example: `salary_delay → anger → legal_threat → anger` — the second `anger` is redundant because `anger` is already in the inherited emotions.

## Decision

Extend `_collapse_redundant_facts` to also collapse emotion nodes whose emotions are already in the accumulated parent emotions. The function now tracks both `accumulated_facts` and `accumulated_emotions`.

A child node is redundant if:
- **Redundant fact**: `child_facts ⊆ (accumulated_facts | own_facts)` AND no emotions, no action
- **Redundant emotion**: `child_emotions ⊆ (accumulated_emotions | own_emotions)` AND no facts, no action

When a redundant node is found, its sentences are promoted to the parent's pool and its children become the parent's children (same logic as fact collapse).

## Why

- `anger → anger` is the same state as `anger` — nesting adds no information
- Symmetric with fact collapse — both facts and emotions can be redundantly restated
- Prevents the UI from showing duplicate emotion nodes
- Fixed-point iteration handles cascading collapses (e.g., `anger → anger → anger`)

## Consequences

- No nested emotion paths where the emotion is already inherited
- `_collapse_redundant_facts` renamed semantically to handle both facts and emotions (function name unchanged for backward compatibility)
- Function signature extended: `accumulated_emotions` parameter added
- Pipeline order unchanged: `_collapse_redundant_facts` runs after `_merge_sibling_facts` and before `_split_by_action`
- Tree node count reduced (309 vs 315 before this change)
