# Multihead State Training — 设计审阅文档（v3.1.1）

**状态：结构冻结；v3.1.2 起建库标签范围为 window-supported（见 §7）**  
**用途：同事 / 业务 / 研发审阅；不以本地小样本 supervision 数字为验收依据。**  
**权威配置：** `configs/schema_v3.1.yaml` · `label_handler/ontology_v2/{proposed_ontology,training_ontology_v3}.yaml`  
**建库策略变更归档：** `artifacts/v3.1.2_migration/BUILD_LABEL_SCOPE_CHANGE.md`  
**FH/NR 冻结语义（v3.1.2.1/2）：** 以 `artifacts/v3.1.2_freeze/CHANGELOG_v3_to_v3.1.2.md` 与 `configs/annotation_policy_v3.1.2.yaml` 为准；本文 §4.3 边界未逐条写入 A∧B / speech-act 硬规则。  
过时备忘已迁至 [`archive/`](archive/)。

> 同事审阅结论（约 9.1/10）：训练目标 / ontology / 建库 / 推理已统一为 **current state estimation**；建议冻结后只做 include_raw 与 per-head 调优。下文已吸收其边界、交互、Loss/Eval 补充。

---

## 0. 训练第一原则（写进 README 置顶）

**Evidence-only supervision：未提及 ≠ 负样本。**

客户没提收入 ≠ 客户有收入。`head_mask` 解决的是**监督污染**，不只是类别不平衡。

---

## 1. 一句话定位

在催收对话上，用 **近窗文本** 预测客户 **当前决策相关状态**（多头 Softmax/Binary），**不训练** P0/P1；长期记忆与 need_update 在推理时用 `merge` + `diff` 派生。

这是从「fact 增量更新（memory_before→after）」到「**当前状态估计**」的架构升级，与业务员看最近几轮再判断困难/触达/协商的方式一致。

相对已冻结的 E1-A（~41-fact 扁平 Softmax）：本方案是 **平行的新栈**，入口在 `training/multihead/`。

---

## 2. 设计目标与非目标

### 目标

| # | 目标 |
|---|------|
| 1 | Head 对齐催收决策（困难协商、触达、资产路径、法务/合规、柔性处理等） |
| 2 | **Evidence-only**：未提及 ≠ 负样本 |
| 3 | 训推窗口一致（先 turn、再 budget；非整段 prefix） |
| 4 | 结构冻结后，用 **per-head confusion / FP 样本** 驱动改动 |

### 非目标（本轨不做）

- Emotion / Willingness Softmax 训练（仅 slot relocate 用旧 mapping）
- 独立训练 need_update / active_heads（P0/P1）
- 继续扩 ontology / 再拆 head（直至 v4）

---

## 3. 系统分层

```text
知识层   proposed_ontology.yaml          Domain → Fact → include_raw
训练层   training_ontology_v3.yaml       train_head / train_value / include_raw
Schema   schema_v3.1.yaml                19 heads + rule_signals + train_policy
映射层   raw_to_multihead.yaml           raw → (head, value)（导出产物）
         raw_to_multihead_overrides.yaml 污染 drop / 别名
数据层   build_state_dataset.py          JSONL: labels + head_mask + window
模型层   train_state.py / eval_state.py  CE + mask + EN（可选 focal）；macro-F1
风险层   rule_signals                    SelfHarm / Deceased / Fraud…（不进 Softmax）
```

业务员「一句话标签」≈ 多个 head 取值的组合（例：失业无法还款 → Employment.disrupted + Income.unavailable + FinancialHardship.yes）。

---

## 4. Head 清单（v3.1.1）

**19 heads**；**IdentityProcess `train=false`**（始终 mask=0）。**22** 个正训练 train_label。

### 4.1 Core decision heads（催收主路径）

| Head | 决策动作 |
|------|----------|
| FinancialHardship | 困难协商 |
| RepaymentCapability | 方案降档（部分/无法） |
| NegotiationRequest | 进入协商 |
| Contactability | 触达策略 |
| Asset | 资产路径 |

### 4.2 全表

| Head | 类型 | 取值（默认在末） | 决策含义 |
|------|------|------------------|----------|
| Employment | binary | disrupted / none | 就业中断 |
| Income | binary | unavailable / none | 收入不可用 |
| FinancialHardship | binary | yes / no | 困难**原因**侧 → 困难协商 |
| RepaymentCapability | softmax | partial / insufficient / none | 当前**支付能力** |
| Health | binary | yes / no | 健康困难 → 柔性 |
| FamilyBurden | binary | yes / no | 家庭负担 |
| Asset | softmax | available / unavailable / none | 资产路径 |
| Contactability | softmax | reachable / unreachable / **denied** / none | 触达策略 |
| Commitment | softmax | committed / resistant / none | 承诺/抵抗 |
| Responsibility | binary | denying / none | 否认责任 |
| DebtDispute | binary | yes / no | 债务争议 |
| LegalProceeding | binary | yes / no | 诉讼程序（可与合规共现） |
| ComplianceRisk | binary | yes / no | 合规/投诉风险（可与诉讼共现） |
| BankConstraint | binary | yes / no | 银行外部约束 |
| ObjectiveBlocker | binary | yes / no | 客观阻碍 |
| CognitiveSupport | binary | yes / no | 认知/沟通支持 |
| NegotiationRequest | process | yes / no | **显式协商请求** |
| IdentityProcess | event | yes / no | **不训练**；核验流程 |
| Grievance | process | yes / no | 安抚处理 |

### 4.3 关键边界（标注 / include_raw 必须遵守）

#### FinancialHardship vs RepaymentCapability

- **FH** = 困难**原因/处境**（为什么难）  
- **RC** = 当前**支付能力表述**（还能付多少）

| 句子 | FH | RC |
|------|----|-----|
| 生病住院 | yes | none（未谈支付额度） |
| 只能还 500 | yes（常共现） | **partial** |
| 完全没钱 / 一点都还不了 | yes | **insufficient** |
| 工资没发，没钱还 | yes | insufficient（若明确「还不起」） |

二者高度共现是正常的；不要把 FH 标成「付不起」的代名词，否则模型会把 FH 学成 RC。

#### NegotiationRequest（Process → Binary）

**yes 的 trigger（guideline）：**

- 明确请求方案/动作：分期、延期、减免、协商还款、「能不能…」、「我想申请…」

**不是 yes：**

- 「我考虑一下」「再说吧」「看情况」——意图未形成请求  
- 仅陈述困难而无协商动作请求 → 走 FH/RC，不标 NegotiationRequest

目标：压低「见困难就 yes」导致的高 recall / 低 precision。

#### Contactability.denied

- **reachable**：可联/愿联/偏好联系节奏（当前可触达）  
- **unreachable**：联不上、失联、客观联系失败  
- **denied**：**主动拒绝合作的联系行为**（拒接策略性拒绝、拒提供联系方式、否认通知并推卸配合等）  
- 勿把「暂时不方便」一律打成 denied（优先 reachable 约束或 unknown）

#### Employment.active

仅 Memory/Profile；Softmax **只监督 disrupted**。禁止把「在职」标成训练正类。

### 4.4 明确不监督（Softmax）

| 概念 | 处理 |
|------|------|
| Employment.active | Memory/Profile |
| SelfHarm | `rule_signals.SelfHarmRisk` |
| Deceased / OrganizedFraud / … | rule_signals |

### 4.5 冻结规则

| 允许 | 不允许（直至 v4） |
|------|-------------------|
| include_raw / definition / examples / collector_action | 新增或再拆 head |
| rule_signals / overrides | 随意改 values / train_head·train_value |
| per-head threshold / focal / sampling 调参 | — |

---

## 5. 监督机制（Evidence-only）

| 情况 | 存储 | Loss |
|------|------|------|
| 累计证据命中非默认 | `label=<value>`, `mask=1` | 计入 |
| 未提及 / 仅默认 | `label=unknown`, `mask=0` | **不计入** |
| IdentityProcess | 可打标供 eval | **始终 mask=0** |

禁止：把「对话没提」当成 `none/no` 负样本。

---

## 6. Head Interaction（只作分析，不做 loss）

Heads 在 loss 上独立，但业务上有依赖。训练后应输出 **co-occurrence / 条件共现**，用于 error analysis，**不写进 loss 规则**。

示例（分析焦点，非硬约束）：

| 模式 | 含义 |
|------|------|
| Employment.disrupted → Income.unavailable | 失业常伴随收入中断 |
| Income.unavailable → FinancialHardship | 收入问题常伴随困难协商 |
| FH=yes + NegotiationRequest=yes | 困难后进入方案协商 |
| Asset.unavailable + RC.insufficient | 无资产且付不起 |
| LegalProceeding ∥ ComplianceRisk | 可共现（已拆 binary） |

**训练后必看：** per-head confusion + FP 样本（Health/Asset/NegotiationRequest FP 最能指导 include_raw）。

---

## 7. 数据流与窗口

```text
对话 raw_state
    → encode：先最多 4 turns，再 ≤200 字从最早裁  → 得到 turn_ids + 文本
    → slot_relocate（仅 turn_ids 内客户轮）
    → window_raws = 上述轮次的 facts
    → raw_to_multihead → labels + head_mask
    → split JSONL
```

**v3.1.2 标签范围（定稿）：window-supported current state**

| | 训练 | 推理（系统侧） |
|--|------|----------------|
| 模型 | 近窗文本 → **窗内可证实** 的 observable state | 同左 |
| 长期记忆 | **不**用累计 memory 做 Softmax 监督 | `merge(previous_memory, observable)` 维护粘性状态 |

禁止：用第 1–N 轮累计 raw 监督「只看见第 N-3…N 轮文本」的样本（objective mismatch）。

详见：`artifacts/v3.1.2_migration/BUILD_LABEL_SCOPE_CHANGE.md`

### 窗口契约（先 turn，再 budget）

| 步骤 | 规则 |
|------|------|
| 1 | 从当前轮往前取**最多 4 个 turn**（保留问答结构） |
| 2 | 若总长 **> 200** 字：从最早 turn 裁/删，尽量保住当前轮与客户轮 |
| 3 | 若 4 轮仍 **< 100** 字：首版**不强制扩窗**（不强行加更早轮）；后续可做可选 pinned evidence |
| 4 | **标签 raw ⊆ 步骤 1–2 最终 `turn_ids`**（与文本严格对齐） |

训推必须共用同一 `encode_recent_window`。

### 建库闸门

- Q1 unmap / 截断率（`build_state_dataset.yaml`）
- W3：`positive < 30` 或 `masked_ratio > 99%` → review（全量后才有意义）
- `audit_v31_consistency.py`：多归属 / 极性 / orphan

报告：`data/reports/head_supervision_stats.md`

---

## 8. 模型与训练

| 项 | 定稿 |
|----|------|
| Encoder | 中文 RoBERTa-large（可 warm-start E1-A） |
| 结构 | Shared encoder + 每 head 独立分类头 |
| Loss | **CE × head_mask** + Effective Number（β=0.999）；**可选 focal**（`use_focal`） |
| LR | encoder 1e-5 / head 5e-5 |
| 主指标 | per-head / overall **macro-F1**（仅 mask=1） |
| Early stop | val macro-F1 |
| Eval | binary head **可扫 threshold**（默认 0.5；`--sweep-threshold`） |
| Sampling | 配置预留 `sampling.ensure_min_supervised`（baseline 默认关；稀有 head 过少时再开） |

稀有正例（Grievance / ComplianceRisk / ObjectiveBlocker / Health）优先：EN → 不够再开 focal；再不够再做 head-aware sampling。

推理：

```text
pred = Model(encode_window(...))
memory' = merge(previous_memory, pred)   # 非默认覆盖；unknown/默认不擦除
need_update / active_heads = diff(previous, memory')
```

---

## 9. 目录与命令

```text
training/multihead/
  docs/DESIGN_v3.1.1.md              # 本文件（审阅权威）
  configs/schema_v3.1.yaml
  configs/train_state.yaml           # use_focal / sampling 开关
  scripts/{export,audit,build,train,eval}_*.py
  archive/p012_legacy/
```

```bash
python training/multihead/scripts/export_raw_to_multihead.py
python training/multihead/scripts/audit_v31_consistency.py
python training/multihead/scripts/build_state_dataset.py --config training/multihead/configs/build_state_dataset.yaml
python training/multihead/scripts/train_state.py --config training/multihead/configs/train_state.yaml
python training/multihead/scripts/eval_state.py --ckpt .../state_best.pt --split test
python training/multihead/scripts/eval_state.py --ckpt .../state_best.pt --split val --sweep-threshold
```

---

## 10. 已关闭问题

1. Asset / Contactability 极性拆分  
2. Health 污染迁出；SelfHarm → rule  
3. 词表收敛到 22 正类 / 19 head  
4. Evidence-only / head_mask  
5. LegalProceeding ∥ ComplianceRisk  
6. Employment.active / IdentityProcess 与训练策略一致  

---

## 11. 下一步（模型迭代，不是 ontology 迭代）

1. 全量建库 → supervision gate  
2. Baseline 训练（`use_focal: false`）  
3. Per-head confusion + FP 样本 + co-occurrence  
4. 只允许两类改动：**include_raw / overrides**，以及 **threshold / focal / sampling**  
5. **禁止**再动 head 结构  

---

## 12. 审阅检查清单

- [x] Evidence-only + 近窗 current state（同事认可）  
- [x] Legal 双 binary  
- [ ] FH vs RC 边界是否按 §4.3 执行标注/抽检  
- [ ] NegotiationRequest trigger 是否按 guideline  
- [ ] denied = 主动拒联（非 unreachable）  
- [ ] 全量后 supervision gate  
- [ ] 训练后输出 co-occurrence + FP 清单  

**文档版本：** v3.1.1-review2 · 吸收同事边界 / 交互 / Loss·Eval 建议  
