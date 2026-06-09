---
id: ADR-003
title: "Append-first write policy for all durable documents"
doc_kind: decision
feature_ids: [F102]
topics: [memory, concurrency]
status: accepted
created: 2026-02-20
updated: 2026-03-05
schema_version: 1
---

# ADR-003: Append-First Write Policy

## What

All durable document writes are append-first. Updates use optimistic concurrency with
`updated` timestamp and content hash. Deletes are tombstones, never immediate hard deletes.

## Why

Multiple agents may write memory concurrently. Append-first prevents silent overwrites.
Optimistic concurrency detects conflicts deterministically. Tombstones preserve audit
trail and enable 90-day recovery window.

## Tradeoff

| Alternative | Why Rejected |
|---|---|
| Last-write-wins | Silent data loss in concurrent agent scenarios |
| Pessimistic locking | Too coarse; blocks unrelated writes |
| CRDT-based merge | Over-engineered for mostly-independent document writes |
