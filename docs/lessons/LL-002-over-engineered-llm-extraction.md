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

Bypassed `id-allocate.py` and `write-durable.py` scripts to write ADR-009 and LL-002 manually, causing id-allocator state drift and index path inconsistencies.

## Root Cause

The agent-memory scripts exist at `modules/agent-memory/scripts/` but require `--state-dir` pointing to the project root `.agent-memory/`. I didn't look for them (used shallow `glob` instead of `find`) and assumed they were missing, then improvised — violating `rules.md §1`: *"The agent reads and executes — it does not improvise."*

## Trigger Conditions

When memory scripts are not found via shallow search, or when `--state-dir` is not passed and the script defaults to a non-existent `src/.agent-memory/` path.

## Fix

Used `find` to locate scripts. Passed `--state-dir ../../.agent-memory` when running from `modules/agent-memory/`. Manually synced `id-allocator.json` state to match existing docs.

## Guard

Before writing ADR/LL docs, always: (1) locate scripts via `find modules/agent-memory/scripts/ -name "*.py"`, (2) run `id-allocate.py --kind <KIND> --state-dir <PROJECT_ROOT>/.agent-memory`, (3) run `write-durable.py` with the allocated ID. Never write memory docs manually.

## Source Anchors

- plan_feature_base.md F002 section (original spec)
- ADR-009 (decision to eliminate F002)
- F001 output: 493/805 turns already labeled in output_aligned.py
