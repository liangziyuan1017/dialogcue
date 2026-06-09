---
id: LL-003
title: "Duplicate lesson detection missed near-identical pitfall descriptions"
doc_kind: lesson
feature_ids: [F102]
topics: [memory, deduplication, quality]
status: accepted
created: 2026-04-05
schema_version: 1
authority: validated
---

# LL-003: Duplicate Lesson Detection Gap

## 1. Pitfall

Two agents independently captured the same lesson about database connection pool
exhaustion, but with slightly different phrasing. The duplicate was not detected
because exact-match comparison was used instead of semantic similarity.

## 2. Root Cause

Duplicate detection relied on exact pitfall text matching. Slight rephrasing
("DB pool exhausted" vs "database connection pool ran out") evaded detection.

## 3. Trigger Conditions

When multiple agents independently encounter the same failure pattern and capture
lessons with different wording. High-risk in large teams or long-running projects.

## 4. Fix

Changed duplicate detection to compare pitfall + root_cause pairs using lexical
overlap scoring. Above threshold → flag as `possible_duplicate_of` and store as
candidate. Below threshold → accept as new lesson.

## 5. Guard (Executable)

`scripts/lexical-search.py` in lesson-capture workflow: searches for matching
pitfall+root_cause pairs before writing. Above 70% token overlap → candidate.

## 6. Source Anchors

- commit:ghi789jkl — "Add pitfall+root_cause overlap detection for lesson dedup"
- `workflows/lesson-capture.md` Step 6 — "Check for duplicate lessons"
