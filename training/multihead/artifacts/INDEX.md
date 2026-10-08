# multihead artifacts 索引（精简）

**Runtime 以仓库内生效路径为准，不以本目录拷贝包为准。**

## 当前生效（勿在 artifacts 找）

| 路径 | 说明 |
|------|------|
| `training/multihead/configs/` | schema / map / overrides / build / train |
| `training/multihead/scripts/` | export → audit → build → train → eval |
| `label_handler/ontology_v2/training_ontology_v3.yaml` | 训练本体（含 patch1） |
| `label_handler/ontology_v2/proposed_ontology.yaml` | 知识本体 |
| `training/multitask_v1/` | Fact+Emotion+Willingness 多任务（对接 main F008） |

## 唯一冻结快照

| 路径 | 说明 |
|------|------|
| `label_handler/ontology_v2/freeze/v3.1.2/` | v3.1.2 冻结镜像 + CHANGELOG（baseline 对照） |

## 已从本分支移除（历史交付包 / 重复镜像）

- `artifacts/v3.1.2_freeze/`（与 ontology freeze 重复）
- `artifacts/v3.1.2_must_replace/` 及 `.zip`（内容已合入 configs）
- `artifacts/v3.1.2_patch1/` 及 `.zip`（内容已合入 configs / ontology）
- 全量评测长报告 `V3_*` / `V312_*` / `state_v312_eval_test.md`
- `label_handler/fact/raw_to_trainable_mapping.yaml`（Stage2 legacy；多头用 `raw_to_multihead.yaml`）
- `label_handler/ontology_v2/raw_to_trainable_mapping_v3.1.2.yaml`（与 freeze 内同文件重复）

需要完整历史包时，请从 `debt_collection-training-archive` 或对应 tag/commit 取回。
