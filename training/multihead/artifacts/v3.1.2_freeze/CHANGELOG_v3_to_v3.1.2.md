# Ontology 演进：v3 → v3.1.2

**冻结日：** 2026-08-04  
**当前状态：** `ontology ready for model validation`（非 perfect）  
**交付包：** `training/multihead/artifacts/v3.1.2_freeze/`  
**镜像：** `label_handler/ontology_v2/freeze/v3.1.2/`

---

## 1. 一句话总结

从「知识事实压缩层（v3）」演进为「19-head 多头状态 Softmax + window 证据监督（v3.1.x）」，并在 v3.1.2 完成 **FH / NR 语义收敛与冻结**；停止大规模语义迁移，进入全量建库与模型诊断闭环。

---

## 2. 版本线

```
v3（trainability）
  └─ knowledge facts ≈47 + training_ontology_v3（头/值/include_raw）
       ↓
v3.1（multihead schema）
  └─ schema_v3.1：19 heads / Softmax + unknown + head_mask
  └─ raw_to_multihead：raw → (head, value)
  └─ E1-A 并行冻结；本线独立
       ↓
v3.1.1
  └─ 全量建库试点；发现 cumulative memory 监督 ≠ window 输入
  └─ baseline 冻结目录：artifacts/v3.1.1_baseline/
       ↓
v3.1.2（本冻结）
  └─ label_scope=window
  └─ P0 语义收窄 → Remap Impact → A∪B 纠偏（防监督塌缩）
  └─ RC.insufficient 审计 / C→Commitment move
  └─ Boundary RC2 + FH/NR gold 校准
  └─ v3.1.2.1 FH patch + freeze
  └─ v3.1.2.2 NR speech-act patch + freeze
  └─ Cross-head Stability 门禁
```

---

## 3. 相对 v3 的结构性变化

| 维度 | v3 | v3.1.2 |
|------|----|--------|
| 训练目标 | 可训练 fact / 合并知识层 | **当前状态**多头 Softmax |
| 标签空间 | knowledge facts / train values | **19 heads**（schema_v3.1） |
| 无证据 | 常默认或粗标 | **unknown + head_mask=0** |
| 文本范围 | 会话/记忆常累计 | **recent window**（≤4 turns / 200 chars） |
| 监督 raw | include_raw 宽候选 | include_raw + overrides；**move > drop** |
| 映射产物 | Stage2 `raw_to_trainable`（fact 名） | **`raw_to_multihead`**（head.value）+ 扁平交付映射 |
| 验收 | 覆盖率 / trainability | Adaptation + Boundary + Purity + Cross-head → **模型诊断** |

---

## 4. v3.1 → v3.1.2 关键工作包

### 4.1 建库对齐（体系）

- **问题：** 输入是 recent window，标签却用累计 `memory_raws` → 目标错位。  
- **修复：** `build_state_dataset.py`：`label_scope=window`，仅 window 内 customer facts 映射。  
- **文档：** `BUILD_LABEL_SCOPE_CHANGE.md`、`annotation_policy_v3.1.2.yaml`

### 4.2 P0 语义与监督保留（FH / RC / NR）

- **问题：** 首次白名单过猛（FH 196→25）→ unmapped-with-evidence = 减监督。  
- **纠偏：** Remap Impact + **A∪B 保留 / 仅 drop C**；Supervision retention。  
- **RC.insufficient：** retention 低但无力支付多经 FH（Stage2→`repayment_inability`）→ 收窄合理。  
- **C→Target：** `willing_to_pay` → Commitment（宁 move 不静默 drop）。

### 4.3 Boundary Consistency

- RC1（seed-raw）作废 → 归档 `step5_reports/archive/rc1/`  
- **RC2：** utterance-first、definition-strict；FH 全量人工校准；NR speech-act gold 校准。

### 4.4 小补丁（非大重构）

| Patch | 内容 | 结果 |
|-------|------|------|
| **v3.1.2.1 FH** | 6 个污染 legacy 桥 override drop + A∧B 硬证据 | Human-adj pos **95%** / adj rej **98.3%** → **FH FROZEN** |
| **v3.1.2.2 NR** | ~100 history/他行/方案状态桥 drop；保留 current-request | adj rej **96.7%** / recall **92.5%** → **NR FROZEN** |

### 4.5 治理与门禁

- `HEAD_CHANGE_SUMMARY.md`、`SEMANTIC_CONVERGENCE_v3.1.2.md`  
- Raw Adaptation / Boundary Purity / **Cross-head Stability**  
- 方法论：`definition → evidence → exclude → remap → RC2 → human purity → freeze → **model diagnostics**`

---

## 5. 冻结声明

- **FinancialHardship v3.1.2.1：** freeze criterion satisfied；再改需新 boundary 证据，禁止为指标优化。  
- **NegotiationRequest v3.1.2.2：** speech-act freeze；禁止为 temporal FP 删除 `negotiation_attempt`。  
- **RepaymentCapability：** 不挡训练；corpus 作评估集，不靠大规模改 ontology。  
- **整包 v3.1.2：** 进入全量建库 + 训练；建议 A/B（v3.1.1 map vs v3.1.2 map）。

---

## 6. 交付文件路径（权威）

### 冻结包

`training/multihead/artifacts/v3.1.2_freeze/`

| 文件 | 用途 |
|------|------|
| `training_ontology_v3.1.2.yaml` | 训练本体 |
| `raw_to_multihead.yaml` | **运行时**映射 |
| `raw_to_trainable_mapping.yaml` | 扁平交付（raw→主键 train_label） |
| `raw_to_multihead_overrides.yaml` | 显式 drop / 阻 legacy |
| `schema_v3.1.yaml` | 19-head schema |
| `annotation_policy_v3.1.2.yaml` | 标注/建库策略 |
| `proposed_ontology.yaml` | 知识层 47 facts |
| `MANIFEST.json` | 校验和与统计 |
| `README.md` | 使用说明 |

### 镜像（label_handler）

`label_handler/ontology_v2/freeze/v3.1.2/`（同上）  
另：`label_handler/ontology_v2/raw_to_trainable_mapping_v3.1.2.yaml`

### 线上工作副本（与冻结内容一致）

- `label_handler/ontology_v2/training_ontology_v3.yaml`（`status: frozen`）  
- `training/multihead/configs/raw_to_multihead.yaml`

### 已归档（失效勿用）

| 路径 | 说明 |
|------|------|
| `step5_reports/archive/rc1/` | Boundary RC1（seed-raw，非冻结依据） |
| `configs/archive/*.txt` / `scripts/archive/*.txt` | 旧快照副本 |
| `artifacts/v3.1.1_baseline/` | 迁移对照基线（保留） |
| `artifacts/v3.1.2_migration/` | 迁移过程证据（保留，非 runtime） |
| `label_handler/fact/raw_to_trainable_mapping.yaml` | **Stage2 fact 旧映射**；多头训练请用 v3.1.2 冻结包 |
| `label_handler/ontology/raw_to_trainable_mapping.yaml` | 更早 V2 canonical；已过时 |

---

## 7. 统计快照（冻结时）

| 指标 | 值 |
|------|---:|
| raw keys | 5926 |
| mapped | 5780 |
| intentional drop | 146 |
| primary trainable labels | 24 |
| FH include_raw（约） | ~95 |
| NR include_raw（current-request） | 保留核心请求词 |
| FH human-adj purity | 95% / 98.3% |
| NR human-adj purity | 92.5% / 96.7% |

---

## 8. 下一步（非 ontology）

1. 全量环境 rebuild（window + 冻结 map）  
2. 训练 +（建议）A/B vs v3.1.1 map  
3. `MODEL_DIAGNOSTICS_v3.1.2.md`：FH/NR/RC P/R、交叉混淆、unknown  
4. 用模型证据决定 v3.1.3（RC），禁止无证据语义大迁移  

---

## 9. 相关过程文档索引

- `artifacts/v3.1.2_migration/HEAD_CHANGE_SUMMARY.md`  
- `artifacts/v3.1.2_migration/SEMANTIC_CONVERGENCE_v3.1.2.md`  
- `artifacts/v3.1.2_migration/PATCH_v3.1.2.1_FH.md`  
- `artifacts/v3.1.2_migration/PATCH_v3.1.2.2_NR.md`  
- `artifacts/v3.1.2_migration/REMAP_IMPACT_REPORT.md`  
- `artifacts/v3.1.2_migration/step5_reports/RAW_ADAPTATION_REPORT.md`  
- `artifacts/v3.1.2_migration/step5_reports/rc2/`（正式 boundary）  
- `artifacts/v3.1.2_migration/step5_reports/cross_head/`
