# Ontology v2 — **FROZEN v3.1.2**

Working tree keeps **live frozen artifacts**. Historical audits under [`archive/`](archive/).  
**Freeze package:** [`freeze/v3.1.2/`](freeze/v3.1.2/)  
**Changelog:** [`../../training/multihead/artifacts/v3.1.2_freeze/CHANGELOG_v3_to_v3.1.2.md`](../../training/multihead/artifacts/v3.1.2_freeze/CHANGELOG_v3_to_v3.1.2.md)

## Live files (frozen — do not edit without model diagnostics)

| File | Role |
|------|------|
| [`training_ontology_v3.yaml`](training_ontology_v3.yaml) | Train ontology (`status: frozen`, version `training_ontology_v3.1.2`) |
| [`raw_to_trainable_mapping_v3.1.2.yaml`](raw_to_trainable_mapping_v3.1.2.yaml) | Flattened raw → train_label delivery map |
| [`proposed_ontology.yaml`](proposed_ontology.yaml) | Knowledge ontology (47 facts) |

Historical design notes: [`archive/docs/`](archive/docs/)（`DESIGN_PRINCIPLES.md` · `SCHEMA_V3.1_POINTER.md`）  
Canonical schema: `training/multihead/configs/schema_v3.1.yaml`

## Canonical training map (runtime)

`training/multihead/configs/raw_to_multihead.yaml`  
(also copied in `freeze/v3.1.2/raw_to_multihead.yaml`)

## Structure freeze

Until v4 / new evidence: **no new heads / head values**.  
FH / NR include_raw frozen. RC corpus = eval set, not mass ontology edits.

## Regenerate map (only if overrides/ontology intentionally patched)

```bash
python training/multihead/scripts/export_raw_to_multihead.py
python training/multihead/scripts/audit_v31_consistency.py
# freeze re-pack (archived one-off; only if shipping a new freeze tag):
# python training/multihead/scripts/archive/v312_migration/freeze_v312_package.py
```

## Obsolete (do not use for multihead train)

- `label_handler/fact/raw_to_trainable_mapping.yaml` — Stage2 fact names  
- `label_handler/ontology/raw_to_trainable_mapping.yaml` — early V2  
- Boundary RC1 under `training/multihead/artifacts/v3.1.2_migration/step5_reports/archive/rc1/`
- Migration one-offs under `training/multihead/scripts/archive/v312_migration/`
