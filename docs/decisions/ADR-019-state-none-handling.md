---
id: ADR-019
title: Capture state=None Collector Turns Without Synthetic Action Label
status: accepted
created: 2026-06-17
updated: 2026-06-17
decision_type: design
feature_ids: [F004]
---

# ADR-019: Capture state=None Collector Turns Without Synthetic Action Label

## Context

Some collector turns in the dialog records have `state=None` (no annotation). The original `_extract_segments` skipped these turns entirely, losing 58 collector utterances (14.5% of all collector turns). A previous fix labeled them `collector_action=other`, but `other` is not a real action category from the data — it's synthetic. This created `a:other` nodes in the tree that don't correspond to any actual collector behavior in the source data.

## Decision

Collector turns with `state=None` or no action label are captured without a `collector_action` key. In `_split_by_action`, sentences without `collector_action` remain in the parent node's sentence pool instead of being split into action child nodes. No synthetic `other` category is created.

Additionally, customer turns with empty facts and emotions (`state=None`) no longer break the current segment — collector sentences continue accumulating under the current branch key.

## Why

- `other` was not a real action label from the data — it was invented
- 14.5% of collector speech is preserved without fabricating categories
- Sentences without action labels naturally belong in the parent context pool
- No `a:other` or `a:none` nodes clutter the tree

## Consequences

- Only 7 real action categories appear as action nodes: greeting, information, plan_proposal, pressure, empathy, legal_threat, closure
- 58 no-action turns appear in parent pools without `collector_action` key
- Customer turns with no facts/emotions don't create new segments
- Multiple greeting turns per record are all captured (no early `break`)
