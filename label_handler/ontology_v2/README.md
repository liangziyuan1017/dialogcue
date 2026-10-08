# Ontology v2 — **FROZEN v3.1.2-patch1**

Working tree keeps **live frozen artifacts**.  
**唯一冻结快照：** [`freeze/v3.1.2/`](freeze/v3.1.2/)  
**Changelog：** [`freeze/v3.1.2/CHANGELOG_v3_to_v3.1.2.md`](freeze/v3.1.2/CHANGELOG_v3_to_v3.1.2.md)

## Live files（勿随意改）

| File | Role |
|------|------|
| [`training_ontology_v3.yaml`](training_ontology_v3.yaml) | 训练本体（含 patch1） |
| [`proposed_ontology.yaml`](proposed_ontology.yaml) | 知识本体 |
| [`freeze/v3.1.2/`](freeze/v3.1.2/) | baseline 镜像（含 raw_to_trainable / schema 等） |

Canonical schema: `training/multihead/configs/schema_v3.1.yaml`  
Canonical train map: `training/multihead/configs/raw_to_multihead.yaml`

## Structure freeze

Until v4：不新增 head / head value。多任务栈见 `training/multitask_v1/`。

## Regenerate map

```bash
python training/multihead/scripts/export_raw_to_multihead.py
python training/multihead/scripts/audit_v31_consistency.py
```

## Obsolete（本分支已移除）

- `label_handler/fact/raw_to_trainable_mapping.yaml` — Stage2 legacy  
- 顶层 `raw_to_trainable_mapping_v3.1.2.yaml` — 与 `freeze/v3.1.2/` 内重复，已删顶层副本  
- `training/multihead/artifacts/v3.1.2_{freeze,must_replace,patch1}/` — 交付拷贝包，已删  
