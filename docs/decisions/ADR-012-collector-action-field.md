---
id: ADR-012
title: collector_action Field on Sentence Entries
status: accepted
created: 2026-06-16
updated: 2026-06-16
decision_type: design
feature_ids: [F004]
---

# ADR-012: collector_action Field on Sentence Entries

## Context

The decision tree's sentence_pool entries originally had `script_text`, `script_id`, `source_call_ids`, and `customer_willingness`. The UI tree explorer needed to display what type of collector action each sentence represents (greeting, information, plan_proposal, etc.), but this information was only available implicitly from the node's position in the tree.

## Decision

Add `collector_action` as an explicit field on every sentence entry in the tree. The field carries the action type string (e.g. "greeting", "information", "plan_proposal", "pressure", "empathy", "legal_threat", "closure") directly from the source turn's action label.

## Why

- UI can display action type without traversing back to the parent node
- Filtering and sorting by action type becomes O(1) per sentence
- The action type is already known at tree construction time — no additional LLM calls needed
- Consistent with `customer_willingness` being a per-sentence label rather than a structural property

## Consequences

- Every sentence entry now has 5 required fields: `script_text`, `script_id`, `source_call_ids`, `customer_willingness`, `collector_action`
- Slight increase in JSON size (~5% due to repeated action strings)
- No change to tree structure or branching logic
