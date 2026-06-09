---
id: ADR-005
title: "De-cat naming for reusable module"
doc_kind: decision
feature_ids: [F200]
topics: [naming, portability]
status: accepted
created: 2026-04-01
updated: 2026-04-10
schema_version: 1
supersedes: []
---

# ADR-005: De-Cat Naming Convention

## What

Replace all Cat Cafe-specific terminology with neutral equivalents:
- cat → agent
- caretaker → human / project owner
- CVO → project owner
- Cat Cafe → host project
- star jar → halt signal

## Why

The module must be reusable by any agent system. Cat Cafe naming creates unnecessary
coupling and confusion for external adopters. Neutral names make the module's purpose
immediately clear.

## Tradeoff

| Alternative | Why Rejected |
|---|---|
| Keep Cat Cafe names | Creates onboarding friction for non-Clowder users |
| Dual naming (both) | Doubles maintenance burden; sources of confusion |
| Abstract all names | Loses semantic meaning; "Entity A" is worse than "agent" |
