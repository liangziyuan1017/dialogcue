# Ontology Freeze v3.1.2

**Status:** frozen (2026-08-04)  
**Purpose:** delivery package for full rebuild + model validation (not further semantic migration).

## Canonical files (use these)

| File | Role |
|------|------|
| `training_ontology_v3.1.2.yaml` | Train ontology (heads / include_raw / definitions) |
| `raw_to_multihead.yaml` | **Runtime** raw → multihead map |
| `raw_to_trainable_mapping.yaml` | Flattened delivery view (raw → primary train_label) |
| `raw_to_multihead_overrides.yaml` | Explicit drops / bridge blocks |
| `schema_v3.1.yaml` | 19-head schema |
| `annotation_policy_v3.1.2.yaml` | Window scope + head evidence rules |
| `proposed_ontology.yaml` | Knowledge ontology (47 facts) |
| `MANIFEST.json` | Checksums + counts |

## Live working copies (same freeze)

- `label_handler/ontology_v2/training_ontology_v3.yaml` (status=frozen)
- `training/multihead/configs/raw_to_multihead.yaml`

## Frozen heads

- FinancialHardship (v3.1.2.1)
- NegotiationRequest (v3.1.2.2)

RC remains eval/calibration-open; do not block training.

## Do not edit without new evidence

Further FH/NR changes require boundary evidence + model diagnostics, not metric chasing.
