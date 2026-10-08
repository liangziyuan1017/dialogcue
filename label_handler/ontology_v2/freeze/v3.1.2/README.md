# Freeze v3.1.2（文档-only）

本目录**不再存放**与 `configs/` / live ontology 重复的 YAML 快照。

| 保留 | 说明 |
|------|------|
| [`CHANGELOG_v3_to_v3.1.2.md`](CHANGELOG_v3_to_v3.1.2.md) | v3 → v3.1.2 变更说明 |
| [`MANIFEST.json`](MANIFEST.json) | 冻结时 checksum 记录（历史对照） |

**当前生效（patch1）请用：**

- `label_handler/ontology_v2/training_ontology_v3.yaml`
- `label_handler/ontology_v2/proposed_ontology.yaml`
- `training/multihead/configs/{schema_v3.1,raw_to_multihead,annotation_policy_v3.1.2}.yaml`

需要完整 baseline YAML 时，从 git 历史 `16a784c^` 或 `debt_collection-training-archive` 取回。
