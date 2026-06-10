---
id: ADR-003
title: "Include suggested domain keywords not observed in data"
doc_kind: decision
feature_ids: [F000]
topics: [taxonomy, domain-knowledge, coverage]
status: accepted
created: 2026-06-09
updated: 2026-06-09
schema_version: 1
---

# ADR-003: Include suggested domain keywords not observed in data

## What

The taxonomy includes keywords that are common in the debt collection domain but did not appear in the 31 records, marked with `source: "suggested"` and `frequency: 0`. Examples: `legal_threat` (被起诉/法院/律师函), `debt_evasion` (不认账/逃废债).

## Why

31 records may not cover all common debt collection scenarios. Domain knowledge fills coverage gaps so that when the system encounters these states at scale (10K records), the taxonomy already has the groups defined. Without suggested keywords, new states at scale would require re-running discovery.

## Tradeoff

| Alternative | Pros | Cons |
|-------------|------|------|
| Only observed keywords | Purely data-driven; no speculation | Coverage gaps at scale; taxonomy incomplete for rare but important states |
| Include suggested (chosen) | Forward-compatible; covers rare but critical states | Some suggested groups may never appear; adds noise to taxonomy |
