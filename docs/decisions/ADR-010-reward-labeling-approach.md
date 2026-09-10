---
REMOVED_FIELD_id: ADR-010
title: Reward Labeling via LLM with Counterfactual Verification
status: accepted
created: 2026-06-11
decision_type: architecture
feature_ids: [F003]
---

# ADR-010: Reward Labeling via LLM with Counterfactual Verification

## Context

F003 requires assigning R ∈ {0, 1} per conversation to indicate whether the collector achieved a repayment commitment. This binary reward is the ground truth for downstream win-rate computation (F005) and retrieval ranking (F006).

## Decision

Use LLM to detect repayment commitment triggers in final turns, then perform counterfactual verification to credit the preceding collector action. Cross-validate against `plan_evaluation` to flag inconsistencies.

- R=1 when customer explicitly agrees to pay, promises to pay, or accepts a plan
- R=0 otherwise
- `reward_evidence` records the trigger turn text and index
- `reward_action_credit` records the collector turn that preceded the commitment

## Why

Manual labeling of 31 records is feasible but not scalable. LLM-based labeling with counterfactual verification provides consistency and auditability. Cross-validation against `plan_evaluation` catches edge cases.

## Consequences

- Reward is binary — no partial credit for "negotiating" willingness
- LLM may misclassify ambiguous turns — cross-validation catches these
- `plan_evaluation` is the secondary truth source, not primary
