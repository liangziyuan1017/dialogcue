---
REMOVED_FIELD_id: ADR-001
title: "Discover state keywords from data rather than prescribe"
doc_kind: decision
feature_ids: [F000]
topics: [taxonomy, state-extraction, data-driven]
status: accepted
created: 2026-06-09
updated: 2026-06-09
schema_version: 1
---

# ADR-001: Discover state keywords from data rather than prescribe

## What

State keyword taxonomy (facts, emotions, willingness levels) is discovered by LLM analysis of actual conversation data, not prescribed from assumptions.

## Why

The original plan prescribed a fixed taxonomy (8 emotions, 10 facts, 5 willingness levels) based on English-language assumptions. Debt collection conversations in Chinese have domain-specific patterns — the actual frequent facts, emotions, and willingness signals may differ significantly from assumptions. Grounding the taxonomy in real data ensures the extraction targets match what actually appears in conversations.

## Tradeoff

| Alternative | Pros | Cons |
|-------------|------|------|
| Prescribed taxonomy | Deterministic, no LLM cost for discovery | May miss domain-specific patterns; English tags may not map to Chinese expressions |
| Data-driven discovery (chosen) | Grounded in actual data; captures domain-specific Chinese expressions | LLM cost for discovery pass; taxonomy may shift with new data |
