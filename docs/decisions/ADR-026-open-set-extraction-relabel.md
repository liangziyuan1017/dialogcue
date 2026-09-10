---
REMOVED_FIELD_id: ADR-026
title: Open-set state extraction with synchronous relabel pipeline
status: accepted
date: 2026-06-29
supersedes: partial reversal of closed-set assumption in F008 prompt
related:
  - ADR-009
  - ADR-001
  - ADR-002
---

# ADR-026: Open-set state extraction with synchronous relabel pipeline

## Context

F008's online state extraction (`extract_state_llm`) previously used a **closed-set**
prompt: it enumerated all known fact/emotion labels from the taxonomy and asked
DeepSeek to pick from that list. This had two failure modes:

1. **Forced misclassification**: when the customer expresses something the
   taxonomy doesn't cover, the LLM maps it to the nearest existing label or
   drops the signal entirely.
2. **No self-improvement**: novel expressions never enter the taxonomy because
   the LLM is constrained to existing labels.

The relabel infrastructure already exists offline (`data/data_labels/`):
- `facts_descriptions.py` / `emotions_descriptions.py` — canonical label sets
- `facts_relabeled.csv` / `emotions_relabeled.csv` — existing free-form → canonical mappings
- `llm_relabel_facts.py` / `llm_relabel_emotions.py` — LLM scripts that generate new mappings

## Decision

Switch F008 to **open-set extraction** for facts and emotions, with a
**synchronous relabel pipeline** in the hot path:

1. DeepSeek extracts facts and emotions **freely** (any snake_case English label).
   Willingness remains **closed-set** (6 ordered levels per ADR-005).
2. For each extracted label, check `*_descriptions` (canonical set). If already
   canonical → use directly.
3. If not canonical, check `*_relabeled` CSV (existing mapping). If a mapping
   exists → use the mapped canonical label.
4. If no mapping exists → **synchronously** call `llm_relabel` to generate a
   mapping, **append** the new mapping to the `*_relabeled` CSV, then use the
   mapped label.

The relabel LLM call is synchronous (blocks the response). Worst-case latency
doubles (~1600-2400ms) when a novel label appears. In steady state, novel labels
become rare as the relabel cache grows, so amortized cost is low.

## Rationale

- **Robustness**: novel expressions surface as real labels instead of being
  forced into wrong buckets or dropped.
- **Self-extending taxonomy**: new mappings persist in `*_relabeled` and become
  available for future calls. The system learns online.
- **Infrastructure reuse**: the relabel pipeline already exists offline; this
  wires it into the hot path rather than building new.
- **Willingness stays closed-set**: it's an ordered scalar with defined
  boundaries (ADR-005), not a free-form label. Closed-set is correct there.

## Consequences

- **Latency**: worst-case ~2x when a novel label triggers a relabel LLM call.
  The Latency Budget table is updated to reflect this conditional cost.
- **Hot-path writes**: `*_relabeled` CSV appends from the online API require
  atomic writes (file lock or DB upsert) to handle concurrency.
- **ADR-009 still holds**: this is one online LLM call for extraction + at most
  one for relabel, not a separate offline F002 pass.
- **Taxonomy drift**: the relabel LLM determines mappings autonomously. Mappings
  should be periodically reviewed by Human to catch drift.

## Related changes

- F008 `extract_state_llm` prompt changed to open-set for facts/emotions.
- F008 `extract_state` now calls `_apply_relabel` synchronously (was post-hoc in
  F009 server).
- F008 `_append_relabel_to_csv` added to persist new mappings.
- SCBGE_GUIDELINE.md Step 2.1 updated.
