---
id: F001
name: Data Schema Alignment
status: complete
owner: agent
source: ROADMAP.md
created: 2026-06-10
depends_on: F000
merged: 2026-06-10 63e5a0c
---

# F001: Data Schema Alignment

## Why

Raw records in `/data/output_manual.py` use the original collection system schema. Downstream features (F002–F006) require a SOP-aligned schema with `turns_annotated`, `reward`, `state_transitions`, and `context` fields derived from `customer_info`.

## What

Map all 31 raw records to SOP-aligned schema:
- Derive `turns_annotated` from `response.dialog` (each turn gets `turn_index`, `role`, `text`)
- Set `reward` to `null` (populated by F003)
- Set `state_transitions` to `[]` (populated by F004)
- Derive `context` constraint dict from `customer_info` fields (9 fields per SOP mapping)
- Output to `/src/f001_schema_alignment/output_aligned.py`

### Context Constraint Mapping (from plan.md Phase 0)

| SOP Field | Source Field | Transform |
|-----------|-------------|-----------|
| `has_auto_loan` | `他行是否有车贷` / `我行是否有车贷` | Bool: contains "有车贷" |
| `has_mortgage` | `他行是否有房贷` / `我行是否有房贷` | Bool: contains "有房贷" |
| `credit_rating` | `24期缴款评等` | Enum: map first char (Z=good, B=moderate, 0=bad) |
| `days_delinquent` | `mob_typ` | Int: M1 → 30 |
| `total_debt` | `总欠款` | Int (parse numeric) |
| `external_debt` | `外部欠款金额` | Int (parse "总余额NNN") |
| `has_negotiation_history` | `历史协商情况` | Bool: ≠ "无协商历史" |
| `available_plans` | `当前可使用的协商方案` | List of plan types (reduction/mina/installment) |
| `social_insurance_stable` | `社保缴纳情况` | Bool: has "有社保" and not "灵活就业" |

## Acceptance Criteria

- [x] All 31 records present in output
- [x] Every record has `turns_annotated`, `reward`, `state_transitions`, `context`
- [x] All 21 context fields populated (no nulls in required fields, per ADR-006)
- [x] Original dialog data preserved verbatim

## Dependencies

- F000 (State Keyword Discovery) — completed, `state_keywords.json` exists

## Links

- [ROADMAP.md](../ROADMAP.md) — dependency graph + architecture decisions
- [ADR-006](../decisions/ADR-006-context-constraint-mapping.md) — context constraint mapping

## Implementation Plan

See [implementation-plan.md](F001-implementation-plan.md)

## Review Notes

**Review 1:** Include F000 state labels from `output_labeled.py` in `turns_annotated`.
- Resolution: `build_turns_annotated` now reads `output_labeled.py` and carries `state` dict (facts/emotions/willingness/action) into each turn. 493/805 turns labeled.
- Status: Fixed ✅

## Files

| File | Purpose |
|------|---------|
| `src/f001_schema_alignment/align_schema.py` | Schema alignment script |
| `src/test_align_schema.py` | Tests |
| `src/f001_schema_alignment/output_aligned.py` | Generated output |
