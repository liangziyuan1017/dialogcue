---
REMOVED_FIELD_id: ADR-004
title: "Discover collector action types from data too"
doc_kind: decision
feature_ids: [F000]
topics: [taxonomy, collector-actions, data-driven]
status: accepted
created: 2026-06-09
updated: 2026-06-09
schema_version: 1
---

# ADR-004: Discover collector action types from data too

## What

Collector action type taxonomy is discovered from actual collector turns via LLM, rather than using a fixed 7-type enum (greeting, information, proposal, pressure, empathy, threat, closure).

## Why

The fixed 7-type enum was assumed from English-language debt collection literature. Chinese collectors may use different behavioral patterns, and the granularity may not match. Data discovery revealed 7 observed groups plus 3 suggested, with `information` (110 occurrences) being far more granular than a single "information" label — it includes告知欠款, 解释息费, 确认意愿, etc.

## Tradeoff

| Alternative | Pros | Cons |
|-------------|------|------|
| Fixed 7-type enum | Deterministic; no LLM cost | May not match Chinese collector behavior; too coarse |
| Data-driven discovery (chosen) | Matches actual behavior; right granularity | LLM cost; groups may shift with new data |
