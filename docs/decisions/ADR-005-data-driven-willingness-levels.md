---
REMOVED_FIELD_id: ADR-005
title: "Willingness level count is data-driven"
doc_kind: decision
feature_ids: [F000]
topics: [taxonomy, willingness, clustering]
status: accepted
created: 2026-06-09
updated: 2026-06-09
schema_version: 1
---

# ADR-005: Willingness level count is data-driven

## What

The number and boundaries of willingness levels are determined by natural clustering in the data, not preset. The LLM clusters observed willingness signals into ordered levels from most resistant to most cooperative.

## Why

Presetting 4 or 5 levels forces the data into an artificial structure. The actual distribution of willingness signals in debt collection may have 3 natural clusters or 6. Data-driven clustering lets the taxonomy reflect the actual decision boundaries customers exhibit. In the 31-record prototype, 5 levels emerged naturally: resistant → weak → conditional → negotiating → strong.

## Tradeoff

| Alternative | Pros | Cons |
|-------------|------|------|
| Preset 4 levels | Simple; consistent across runs | May not match data; forces artificial boundaries |
| Preset 5 levels | Matches common framework | Still artificial; may over/under-split |
| Data-driven clustering (chosen) | Matches actual data; natural boundaries | May vary across runs; harder to compare across datasets |
