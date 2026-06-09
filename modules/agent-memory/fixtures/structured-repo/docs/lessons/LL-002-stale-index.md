---
id: LL-002
title: "Stale index entries after concurrent writes during rebuild"
doc_kind: lesson
feature_ids: [F102]
topics: [memory, concurrency, indexing]
status: accepted
created: 2026-03-10
schema_version: 1
authority: validated
---

# LL-002: Stale Index After Concurrent Writes

## 1. Pitfall

An index rebuild was running while two agents wrote new decision records. The resulting
index was stale — it missed both new documents.

## 2. Root Cause

Index rebuild did not detect concurrent mutations. It built from a snapshot taken at
the start, without checking for changes during the rebuild window.

## 3. Trigger Conditions

Any time an index rebuild runs concurrently with durable document writes. Especially
likely in multi-agent workflows where writes and rebuilds overlap.

## 4. Fix

Rebuild now records `last_mutation_seen` timestamp at start. After rebuild completes,
it checks if any documents changed since that timestamp. If so, it marks the index as
`stale_since: <TIMESTAMP>` and recommends an incremental rebuild.

## 5. Guard (Executable)

`scripts/index-rebuild.py` — built-in stale detection: after rebuild, scans for mutations
during the rebuild window and self-reports staleness.

## 6. Source Anchors

- commit:def456abc — "Add stale detection to index rebuild"
- `rules.md §4` — "rebuild marks itself stale and reruns once writes settle"
