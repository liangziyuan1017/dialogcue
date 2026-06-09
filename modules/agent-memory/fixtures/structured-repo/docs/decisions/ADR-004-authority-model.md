---
id: ADR-004
title: "Knowledge authority model with four trust levels"
doc_kind: decision
feature_ids: [F102]
topics: [memory, governance]
status: accepted
created: 2026-03-01
updated: 2026-03-15
schema_version: 1
---

# ADR-004: Knowledge Authority Model

## What

Every knowledge entry carries three orthogonal axes:
- `authority`: observed → candidate → validated → constitutional
- `activation`: query → scoped → always_on → backstop
- `status`: active → review → invalidated → archived

## Why

Flat knowledge lists become unwieldy. A multi-axis model allows:
- Trust-based loading (only validated+ knowledge loads proactively)
- Lifecycle management (stale entries tombstoned, not deleted)
- Backstop preservation (old knowledge kept but demoted)

## Tradeoff

| Alternative | Why Rejected |
|---|---|
| Single authority flag | Can't express both trust AND load behavior independently |
| Tag-only categorization | Tags don't encode lifecycle or trust level |
| Hard delete on staleness | Loses audit trail; violates non-destructive compression principle |
