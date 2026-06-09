---
id: ADR-006
title: "Phase-gated implementation with deterministic verification"
doc_kind: decision
feature_ids: [F300]
topics: [process, quality]
status: draft
created: 2026-05-01
updated: 2026-05-15
schema_version: 1
---

# ADR-006: Phase-Gated Implementation

## What

Module implementation proceeds through 13 gated phases (0–12), each with explicit pass
criteria. No phase is marked passed until all criteria are met with evidence.

## Why

Complex modules need structured rollout to avoid entropy. Phase gating ensures:
- Contracts (schemas, templates) are frozen before behavior is built on them
- Each layer is independently verifiable
- Regression surface is bounded by phase boundary

## Tradeoff

| Alternative | Why Rejected |
|---|---|
| Big-bang delivery | High risk; hard to verify incrementally |
| Agile without gates | Risk of building on unstable foundations |
| Waterfall spec-then-build | Too rigid for evolving requirements discovery |
