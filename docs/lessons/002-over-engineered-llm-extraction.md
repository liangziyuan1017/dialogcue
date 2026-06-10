---
id: LL-002
title: "Over-engineered per-turn LLM extraction when partial manual annotations suffice"
doc_kind: lesson
feature_ids: [F002]
topics: [cost, over-engineering, yagni]
status: draft
created: 2026-06-10
updated: 2026-06-10
schema_version: 1
---

# Over-engineered per-turn LLM extraction

## Pitfall

Built a full LLM pipeline (F002) to extract state keywords on every turn, when existing manual annotations from F001 already covered the important turns.

## Root Cause

Planned the feature spec (plan_feature_base.md) before understanding the data. The spec assumed all 805 turns needed labels, but didn't analyze how many turns were filler ("嗯", "对") vs. information-carrying. The 493 labeled turns from F001 were sufficient for downstream use.

## Trigger Conditions

When a feature spec requires "all N items processed" without first checking whether partial coverage is adequate for downstream consumers.

## Fix

Removed F002 entirely. Downstream features (F003, F004) will handle missing `state` on unlabeled turns gracefully.

## Guard

Before implementing a "process all N items" feature, first quantify: (1) how many items already have the needed data, (2) what fraction of unlabeled items are information-carrying vs. filler, (3) whether downstream can tolerate gaps. If existing coverage is sufficient, don't build the extraction step.

## Source Anchors

- plan_feature_base.md F002 section (original spec)
- ADR-009 (decision to eliminate F002)
- F001 output: 493/805 turns already labeled in output_aligned.py
