# v3.1.2-patch1 执行清单（Commitment 路径 A）

**决策：** Residual Audit 后进入 patch phase；Commitment 选 **A**（保留 `committed/resistant`，补 resistant≥50，本轮不拆 uncertain/refusal）。

## 版本命名（锁定）

| 对象 | 版本 |
|------|------|
| 当前模型 | `state_v312` |
| 下一轮训练 | `state_v312_patch1` |
| ontology | `training_ontology_v3.1.2-patch1` → freeze 候选名 `ontology_fact_v3.2` |
| eval report | `eval_v33`（勿与现有 eval report v3.2 框架混淆） |
| Emotion | **并行准备、不同训**（本轮不挂 head） |

## 本轮已改（仓库）

| 文件 | 变更 |
|------|------|
| `label_handler/ontology_v2/training_ontology_v3.yaml` | version→patch1；Asset/Contact/Commitment 定义+include_raw 清洗 |
| `training/multihead/configs/raw_to_multihead_overrides.yaml` | patch1 drops/remaps |
| `training/multihead/configs/raw_to_multihead.yaml` | 已本地 re-export（map 门禁通过） |
| `training/multihead/configs/annotation_policy_v3.1.2.yaml` | Asset/Contact/Commitment 边界 + resistant≥50 gate |
| `training/multihead/configs/schema_v3.1.yaml` | changelog_v3_1_2_patch1 |
| `training/multihead/scripts/audit_patch1_boundary.py` | 映射污染 + resistant 计数门禁 |

**拷贝包：** `training/multihead/artifacts/v3.1.2_patch1/`（含 configs + ontology + scripts + 本 LIST）

本地校验：`audit_patch1_boundary` 映射错误 **0**；`audit_v31_consistency` polarity/multi-head **通过**（orphans 含主动 drop 的 raw，预期）。resistant 门禁需全量机重建 train 后再 `--strict`。

## 全量机必跑（按序）

```bash
# 1) 重新导出 runtime map（覆盖 raw_to_multihead.yaml）
python training/multihead/scripts/export_raw_to_multihead.py

# 2) 映射一致性（已有）
python training/multihead/scripts/audit_v31_consistency.py

# 3) patch1 边界门禁（map 侧；train 未重建前 resistant 可能 WARN）
python training/multihead/scripts/audit_patch1_boundary.py

# 4) 重建 state 数据集（改 input_path / output）
# 编辑 build_state_dataset.yaml → output 指向 data/state_patch1/ 等
python training/multihead/scripts/build_state_dataset.py \
  --config training/multihead/configs/build_state_dataset.yaml

# 5) 再跑门禁（必须 --strict 绿灯才能训）
python training/multihead/scripts/audit_patch1_boundary.py \
  --train-jsonl training/multihead/data/state/state_train.jsonl \
  --strict

# 6) 训练（output_dir → checkpoints/state_v312_patch1）
python training/multihead/scripts/train_state.py \
  --config training/multihead/configs/train_state.yaml

# 7) 评估 → 报告命名 eval_v33*
python training/multihead/scripts/eval_state.py \
  --ckpt training/multihead/checkpoints/state_v312_patch1/state_best.pt \
  --split test --device npu:0
```

## Asset patch 摘要

- **available** = 本人可支配/可处置资产  
- **unavailable** = 无资产 / 非本人产权 / 不可处分（含家人房、朋友住）  
- Drop from available Softmax：`self_residence`, `housing`, `housing_situation`, …  
- Remap → unavailable：`staying_with_friend`, `family_house`, `borrowed_residence`, `third_party_asset`  
- Drop：`no_overdue_mortgage`（≠ 无资产）

## Contactability patch 摘要

- 只问：当前能否有效沟通  
- Drop：`time_constraint`, `busy`, `location`, `contact_difficulty`, `missed_communication`, …  
- `busy_afternoon` 仍可落 reachable（忙可改约）

## Commitment path A

- 值不变：`committed` / `resistant` / `none`  
- **开训门禁：** train 上 `Commitment=resistant` 且 mask=1 的样本 **≥50**  
- 若重建后仍 <50：先补标注/采样，禁止开训

## 明确不做

- 不扩 AssetCapability 多值  
- 不把 Commitment 改成 uncertain/refusal（记为 v3.2 freeze follow-up）  
- 不同训 Emotion  
- 不追求 legacy macro-F1

## 验收

1. `audit_patch1_boundary.py --strict` 通过  
2. Residual 再跑：Asset/Contact 污染类错误显著下降  
3. Commitment resistant recall > 0（至少不再 0/3）  
4. 主指标仍用 Evidence Positive F1（eval_v33）
