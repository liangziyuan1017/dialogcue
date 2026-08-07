# Stage2 Multihead Training (**v3.1.2** · **patch1** in progress)

并行于已冻结的 E1-A（见 [`../FREEZE_LEGACY.md`](../FREEZE_LEGACY.md)）。

**冻结交付包：** [`artifacts/v3.1.2_freeze/`](artifacts/v3.1.2_freeze/)  
**当前 patch：** [`artifacts/v3.1.2_patch1/`](artifacts/v3.1.2_patch1/)（Asset/Contactability/Commitment path-A）  
**产物索引：** [`artifacts/INDEX.md`](artifacts/INDEX.md)

## 训练第一原则

**Evidence-only supervision：未提及 ≠ 负样本。**  
客户没提收入 ≠ 客户有收入。`head_mask` 解决的是监督污染，不只是类别不平衡。

**建库标签范围（v3.1.2）：** Softmax 标签只来自 **与输入文本相同的近窗 `turn_ids`**（`label_scope=window`）。  
累计对话 memory **不**再作为训练监督；长期粘性状态在推理侧 `merge`。

**审阅设计文档：** [`docs/DESIGN_v3.1.1.md`](docs/DESIGN_v3.1.1.md) + `configs/annotation_policy_v3.1.2.yaml`  
过时备忘：[`docs/archive/`](docs/archive/)

## LIVE 脚本

| 脚本 | 作用 |
|------|------|
| `scripts/export_raw_to_multihead.py` | 导出 `raw_to_multihead.yaml` |
| `scripts/audit_v31_consistency.py` | 映射一致性审计 |
| `scripts/audit_patch1_boundary.py` | **patch1** 污染映射 + resistant≥50 门禁 |
| `scripts/build_state_dataset.py` | 建库（window 标签） |
| `scripts/train_state.py` | 训练 |
| `scripts/eval_state.py` | 评估（写 eval report v3.2 框架） |
| `scripts/reformat_eval_report.py` | 已有 `eval_*.json` → v3.2 md（无需重推理） |
| `scripts/export_decision_package.py` | Residual / 分布 / ontology 决策包 |

v3.1.2 迁移一次性脚本 → [`scripts/archive/v312_migration/`](scripts/archive/v312_migration/)（**勿再跑**）

## 生效配置

| 文件 | 作用 |
|------|------|
| `configs/schema_v3.1.yaml` | 19-head + patch1 changelog |
| `configs/raw_to_multihead.yaml` | 导出映射（runtime 权威） |
| `configs/raw_to_multihead_overrides.yaml` | 污染 drop（含 patch1） |
| `configs/annotation_policy_v3.1.2.yaml` | 标注/建库策略（含 Asset/Contact/Commitment patch1） |
| `configs/build_state_dataset.yaml` | 建库 |
| `configs/train_state.yaml` | 训练（全量机可设 `device: "npu:0"`） |

Ontology：`label_handler/ontology_v2/training_ontology_v3.yaml`（**version: training_ontology_v3.1.2-patch1**）

## 评估主指标（report v3.2）

- Primary：**Evidence Positive F1**（evidence-only；含 class coverage）  
- Legacy macro-F1：附录 only  
- IdentityProcess：**Excluded from primary score**

## 下一轮命名

| 对象 | 名 |
|------|-----|
| ckpt | `state_v312_patch1` |
| eval 文件 | `eval_v33*` |
| Emotion | 并行准备、**不同训** |

## 命令（patch1）

```bash
python training/multihead/scripts/export_raw_to_multihead.py
python training/multihead/scripts/audit_v31_consistency.py
python training/multihead/scripts/audit_patch1_boundary.py
# 重建库后：
python training/multihead/scripts/audit_patch1_boundary.py --train-jsonl .../state_train.jsonl --strict
python training/multihead/scripts/train_state.py --config training/multihead/configs/train_state.yaml
python training/multihead/scripts/eval_state.py --ckpt .../state_v312_patch1/state_best.pt --split test --device npu:0
```

详见 [`artifacts/v3.1.2_patch1/LIST.md`](artifacts/v3.1.2_patch1/LIST.md)。
