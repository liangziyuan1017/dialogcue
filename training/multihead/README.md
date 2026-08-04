# Stage2 Multihead Training (**v3.1.2** frozen · window labels)

并行于已冻结的 E1-A（见 [`../FREEZE_LEGACY.md`](../FREEZE_LEGACY.md)）。

**冻结交付包：** [`artifacts/v3.1.2_freeze/`](artifacts/v3.1.2_freeze/)  
**演进说明：** [`artifacts/v3.1.2_freeze/CHANGELOG_v3_to_v3.1.2.md`](artifacts/v3.1.2_freeze/CHANGELOG_v3_to_v3.1.2.md)

## 训练第一原则

**Evidence-only supervision：未提及 ≠ 负样本。**  
客户没提收入 ≠ 客户有收入。`head_mask` 解决的是监督污染，不只是类别不平衡。

**建库标签范围（v3.1.2）：** Softmax 标签只来自 **与输入文本相同的近窗 `turn_ids`**（`label_scope=window`）。  
累计对话 memory **不**再作为训练监督；长期粘性状态在推理侧 `merge`。  
过程证据：[`artifacts/v3.1.2_migration/`](artifacts/v3.1.2_migration/)（非 runtime）

**审阅设计文档：** [`docs/DESIGN_v3.1.1.md`](docs/DESIGN_v3.1.1.md)（架构）+ freeze CHANGELOG / `configs/annotation_policy_v3.1.2.yaml`（FH/NR 语义）  
过时备忘：[`docs/archive/`](docs/archive/)

## LIVE 脚本（仅此 5 个）

| 脚本 | 作用 |
|------|------|
| `scripts/export_raw_to_multihead.py` | 导出 `raw_to_multihead.yaml` |
| `scripts/audit_v31_consistency.py` | 一致性审计 |
| `scripts/build_state_dataset.py` | 建库（window 标签） |
| `scripts/train_state.py` | 训练 |
| `scripts/eval_state.py` | 评估 |

v3.1.2 迁移一次性脚本 → [`scripts/archive/v312_migration/`](scripts/archive/v312_migration/)（**勿再跑**）  
旧 P0/P1/P2 → [`archive/p012_legacy/`](archive/p012_legacy/)（勿再引用）

**运行时独立于冻结的 `training/src`：** parser / remap / TextEncoder 已 vendoring 进 `multihead/src/`（见 [`src/VENDOR.md`](src/VENDOR.md)）。

## 生效配置

| 文件 | 作用 |
|------|------|
| `configs/schema_v3.1.yaml` | 19-head + 边界 note |
| `configs/raw_to_multihead.yaml` | 导出映射（runtime 权威） |
| `configs/raw_to_multihead_overrides.yaml` | 污染 drop |
| `configs/annotation_policy_v3.1.2.yaml` | 标注/建库策略（boundary/freeze） |
| `configs/build_state_dataset.yaml` | 建库 |
| `configs/train_state.yaml` | 训练 |
| `configs/slot_relocate/*.yaml` | 仅 slot relocate（非 Softmax 目标） |

Ontology（仍在 label_handler）：`ontology_v2/{proposed_ontology,training_ontology_v3}.yaml`

## 定稿原则

| | 做法 |
|--|------|
| **输入** | 先最多 4 turn，再 ≤200 字从最早裁 |
| **目标** | 19-head current state（IdentityProcess train=false） |
| **监督** | Evidence-only |
| **Loss** | CE + mask + EN；可选 focal |
| **结构** | **冻结**；FH/NR 勿再为指标改 include_raw；RC 走 eval corpus |

## 命令

```bash
# Stage2 全量 dump 仍 emit 粗 raw（如 financial_hardship）时：默认开 legacy bridge
# （overrides 里的空列表仍会挡住污染标签；勿用 --no-legacy-bridge，否则 Q1 unmap 会暴涨）
python training/multihead/scripts/export_raw_to_multihead.py
python training/multihead/scripts/audit_v31_consistency.py
python training/multihead/scripts/build_state_dataset.py --config training/multihead/configs/build_state_dataset.yaml
python training/multihead/scripts/train_state.py --config training/multihead/configs/train_state.yaml
python training/multihead/scripts/eval_state.py --ckpt training/multihead/checkpoints/state_v31/state_best.pt --split test
```

全量环境建议拷贝：`training/multihead/`（可无 archive）+ `label_handler/ontology_v2/`（可无 archive）+ 编码器权重 + 全量数据路径；**不必**再拷 `training/src`。  
若需在全量机 **重新 export**，还要有 `label_handler/fact/raw_to_trainable_mapping.yaml`（legacy bridge 源）；更简单是直接拷已导出的 `configs/raw_to_multihead.yaml`（含 bridge）。

**注意：** `data/archive_pre_v312_window/` 与 `checkpoints/archive_pre_v312_window/` 是 window 改动前的本地小样本产物，勿当 v3.1.2 训练数据。
