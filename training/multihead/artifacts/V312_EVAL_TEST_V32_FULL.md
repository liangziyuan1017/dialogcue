# State Multihead Eval Report v3.2（全量机转录）

**来源：** 全量环境 `training/multihead/checkpoints/state_v312/eval_test_v32.md`（屏幕转录）  
**对照 checkpoint：** `state_best.pt`  
**整理日期：** 2026-08-06  
**v3.2 补丁：** 已按评审加入 class coverage、head-level evidence 措辞、IdentityProcess non-primary 标注（代码见 `src/metrics/state_metrics.py`；全量机用 `reformat_eval_report.py` 可离线重出）。

---

## Evaluation Setting

- ontology: v3.1.2 freeze
- model: state_best.pt
- scoring: evidence-only
  - unknown excluded
  - head_mask=0 excluded
- split: test
- heads evaluated: 19
- head-level evidence instances (sum of per-head supports): **3914**
  - not dialogue count; each row is one (head, labeled instance) under evidence-only
- timestamp: 2024-08-06T10:20:55Z（机内时区/时钟以原件为准）

---

## 1. Overall Summary

| Metric | Value |
|---|---:|
| Evidence Positive F1 (weighted) | **0.9626** |
| Evidence Positive Precision (weighted) | 0.9913 |
| Evidence Positive Recall (weighted) | 0.9355 |
| Evaluated Heads | 19 |
| Head-level evidence instances | 3914 |

> Evidence Positive *：各头 pos-P/R/F1 按该头 support 加权平均（binary：正类；multi-state：非默认类 micro 聚合）。**须结合 class coverage 解读**——某一头可接近满分，但测试集可能只覆盖其中一个状态。

### By slice

| slice | heads (support>0) | main metric shown |
|---|---:|---|
| state (binary-like) | 12 | weighted pos-F1 |
| state (multi-state) | 4 | class-macro-F1 + per-class recall |
| process | 2 | pos-F1 |
| non-primary | 1 | Excluded from primary score |

---

## 1b. Coverage Summary

| Head | Supported classes | Total classes | Class coverage |
|---|---:|---:|---:|
| Employment | 1 | 2 | 50.0% |
| Income | 1 | 2 | 50.0% |
| FinancialHardship | 1 | 2 | 50.0% |
| RepaymentCapability | 1 | 3 | 33.3% |
| Health | 1 | 2 | 50.0% |
| FamilyBurden | 1 | 2 | 50.0% |
| Asset | 2 | 3 | 66.7% |
| Contactability | 2 | 4 | 50.0% |
| Commitment | 2 | 3 | 66.7% |
| Responsibility | 1 | 2 | 50.0% |
| DebtDispute | 1 | 2 | 50.0% |
| LegalProceeding | 1 | 2 | 50.0% |
| ComplianceRisk | 1 | 2 | 50.0% |
| BankConstraint | 1 | 2 | 50.0% |
| ObjectiveBlocker | 1 | 2 | 50.0% |
| CognitiveSupport | 1 | 2 | 50.0% |
| NegotiationRequest | 1 | 2 | 50.0% |
| IdentityProcess † | 1 | 2 | 50.0% |
| Grievance | 1 | 2 | 50.0% |

† Non-primary head (excluded from primary State Multihead score).

> Binary 在 evidence-only 下默认类 support 常为 0 → coverage≈50% 属预期，不影响 pos-F1 主读法。Multi-state 低 coverage（如 RC 33%）才是「满分易误读」的关键。

---

## 2. Head Summary

| Head | Kind | Type | Support | Active/Total | Primary Metric |
|---|---|---|---:|---:|---|
| Employment | state | binary | 9 | 1/2 | pos-F1 |
| Income | state | binary | 701 | 1/2 | pos-F1 |
| FinancialHardship | state | binary | 1350 | 1/2 | pos-F1 |
| RepaymentCapability | state | multi-state | 98 | 1/3 | class-macro-F1 |
| Health | state | binary | 79 | 1/2 | pos-F1 |
| FamilyBurden | state | binary | 186 | 1/2 | pos-F1 |
| Asset | state | multi-state | 108 | 2/3 | class-macro-F1 |
| Contactability | state | multi-state | 89 | 2/4 | class-macro-F1 |
| Commitment | state | multi-state | 157 | 2/3 | class-macro-F1 |
| Responsibility | state | binary | 195 | 1/2 | pos-F1 |
| DebtDispute | state | binary | 83 | 1/2 | pos-F1 |
| LegalProceeding | state | binary | 32 | 1/2 | pos-F1 |
| ComplianceRisk | state | binary | 29 | 1/2 | pos-F1 |
| BankConstraint | state | binary | 54 | 1/2 | pos-F1 |
| ObjectiveBlocker | state | binary | 18 | 1/2 | pos-F1 |
| CognitiveSupport | state | binary | 160 | 1/2 | pos-F1 |
| NegotiationRequest | process | binary | 202 | 1/2 | pos-F1 |
| IdentityProcess | event | non-primary | 217 | 1/2 | Excluded from primary score |
| Grievance | process | binary | 147 | 1/2 | pos-F1 |

---

## 3. Binary Heads (state, primary: pos-F1)

| Head | Support | Pos-P | Pos-R | Pos-F1 | Acc |
|---|---:|---:|---:|---:|---:|
| Employment | 9 | 1.0 | 1.0 | 1.0 | 1.0 |
| Income | 701 | 1.0 | 1.0 | 1.0 | 1.0 |
| FinancialHardship | 1350 | 1.0 | 1.0 | 1.0 | 1.0 |
| Health | 79 | 1.0 | 1.0 | 1.0 | 1.0 |
| FamilyBurden | 186 | 1.0 | 1.0 | 1.0 | 1.0 |
| Responsibility | 195 | 1.0 | 1.0 | 1.0 | 1.0 |
| DebtDispute | 83 | 1.0 | 1.0 | 1.0 | 1.0 |
| LegalProceeding | 32 | 1.0 | 1.0 | 1.0 | 1.0 |
| ComplianceRisk | 29 | 1.0 | 1.0 | 1.0 | 1.0 |
| BankConstraint | 54 | 1.0 | 1.0 | 1.0 | 1.0 |
| ObjectiveBlocker | 18 | 1.0 | 1.0 | 1.0 | 1.0 |
| CognitiveSupport | 160 | 1.0 | 1.0 | 1.0 | 1.0 |

Note: class-macro-F1 is **not** primary for evidence-only binary heads (default class often has zero support → macro ≈ 0.5 even when pos-F1 = 1.0).

---

## 4. Multi-state Heads (primary: per-class recall)

### `RepaymentCapability`

| Metric | Value |
|---|---:|
| support | 98 |
| Active classes | 1/3 |
| Classes with support>0 | 1 |
| Class coverage | 33.3% |
| class-macro-F1 | 0.3333 |
| class-weighted-F1 | 1.0 |
| acc | 1.0 |
| default value | `none` |

| Class | Support | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| `partial` | 98 | 1.0 | 1.0 | 1.0 |
| `insufficient` | 0 | 0.0 | 0.0 | 0.0 |
| `none` | 0 | 0.0 | 0.0 | 0.0 |

> Class coverage 33.3% (1/3): high acc / class-weighted-F1 may reflect only the observed states — do not read as full multi-state mastery.

### `Asset`

| Metric | Value |
|---|---:|
| support | 108 |
| Active classes | 2/3 |
| Classes with support>0 | 2 |
| Class coverage | 66.7% |
| class-macro-F1 | 0.312 |
| class-weighted-F1 | 0.8407 |
| acc | 0.8796 |
| default value | `none` |

| Class | Support | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| `available` | 97 | 0.8962 | 0.9794 | 0.936 |
| `unavailable` | 11 | 0.0 | 0.0 | 0.0 |
| `none` | 0 | 0.0 | 0.0 | 0.0 |

Confusion (top):
- `unavailable→available`: 11
- `available→unavailable`: 2

> Class coverage 66.7% (2/3): high acc / class-weighted-F1 may reflect only the observed states — do not read as full multi-state mastery.

### `Contactability`

| Metric | Value |
|---|---:|
| support | 89 |
| Active classes | 2/4 |
| Classes with support>0 | 2 |
| Class coverage | 50.0% |
| class-macro-F1 | 0.3849 |
| class-weighted-F1 | 0.8068 |
| acc | 0.7978 |
| default value | `none` |

| Class | Support | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| `reachable` | 24 | 0.5882 | 0.8333 | 0.6897 |
| `unreachable` | 65 | 0.9273 | 0.7846 | 0.85 |
| `denied` | 0 | 0.0 | 0.0 | 0.0 |
| `none` | 0 | 0.0 | 0.0 | 0.0 |

Confusion (top):
- `unreachable→reachable`: 14
- `reachable→unreachable`: 4

> Class coverage 50.0% (2/4): high acc / class-weighted-F1 may reflect only the observed states — do not read as full multi-state mastery.

### `Commitment`

| Metric | Value |
|---|---:|
| support | 157 |
| Active classes | 2/3 |
| Classes with support>0 | 2 |
| Class coverage | 66.7% |
| class-macro-F1 | 0.3301 |
| class-weighted-F1 | 0.9715 |
| acc | 0.9809 |
| default value | `none` |

| Class | Support | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| `committed` | 154 | 0.9809 | 1.0 | 0.9904 |
| `resistant` | 3 | 0.0 | 0.0 | 0.0 |
| `none` | 0 | 0.0 | 0.0 | 0.0 |

Confusion (top):
- `resistant→committed`: 3

> Class coverage 66.7% (2/3): high acc / class-weighted-F1 may reflect only the observed states — do not read as full multi-state mastery.

---

## 5. Process / Event Heads

| Head | Kind | Support | Pos-P | Pos-R | Pos-F1 | Note |
|---|---|---:|---:|---:|---:|---|
| NegotiationRequest | process | 202 | 1.0 | 1.0 | 1.0 | - |
| IdentityProcess | event | 217 | 1.0 | 0.318 | 0.4825 | Excluded from primary score; train=false; low recall |
| Grievance | process | 147 | 1.0 | 1.0 | 1.0 | - |

---

## 6. Error Summary

### Asset
- `unavailable→available`: 11
- `available→unavailable`: 2

### Contactability
- `unreachable→reachable`: 14
- `reachable→unreachable`: 4

### Commitment
- `resistant→committed`: 3

### IdentityProcess
- `yes→no`: 148

---

## 7. Confidence Analysis

_Not populated in offline reformat (requires eval-time logit/confidence capture)._

| Head | Avg confidence (correct) | Avg confidence (error) |
|---|---:|---:|
| _(pending)_ | — | — |

---

## 8. Appendix — Legacy Metrics

| Metric | Value |
|---|---:|
| macro-F1 | 0.4527 |
| weighted macro-F1 | 0.4669 |
| by kind | `{'state': 0.46, 'process': 0.5, 'event': 0.2413}` |

> Legacy metrics are kept for backward compatibility only and are **not** primary evaluation criteria under evidence-only binary heads.

> Not comparable across ontology versions when evidence policy changes.

---

# 指标分析

## 1. 总览：v3.2 主指标 vs Legacy

| | 数值 | 读法 |
|--|-----:|------|
| **Evidence Positive F1 (weighted)** | **0.9626** | 有证据时「认事实」能力很强 |
| Evidence Positive P / R | 0.9913 / 0.9355 | 偏保守：误报少，漏检略多 |
| Legacy macro-F1 | 0.4527 | **严重低估**（binary 无默认类 → 头内 macro≈0.5） |

结论：用 v3.2 主指标看，全量 v3.1.2 模型在 evidence-only 设定下 **整体已可用**；不要再用 0.45 当能力结论。

## 2. Binary state：冻结目标头达标

- FH（1350）、Income（701）、NR（202）、Grievance（147）等：**pos-P/R/F1 = 1.0**
- 12 个 state binary 在表上全部满分 → 在「有证据才计分」口径下，**正类识别接近饱和**
- Employment 仅 9 条：满分可信度低，属稀有头，勿过度解读

业务含义：v3.1.2 freeze + window 后，**困难/收入/协商请求等大正类头没有学崩**。

## 3. Multi-state：真实瓶颈在少数类

### RepaymentCapability（support=98）
- 计分集 **只有 `partial`（98）**，`insufficient`/`none` support=0
- acc=1.0、class-weighted-F1=1.0，但 class-macro-F1=0.3333（三个类等权，两个空类 F1=0）
- **不能**说「RC 学得完美」；只能说「当前 test 证据窗里几乎只有 partial」——标注/窗口分布问题，优先 residual 审计而非调 loss

### Asset（108）
- `available` 强（R≈0.98）；**`unavailable` 全军覆没**（11/11 → available，R=0）
- 这是清晰的 **少数类漏检 / 偏向 available**，适合 11 条人工看（ontology vs 模型）

### Contactability（89）
- `unreachable` 为主（65）；双向混淆：unreachable→reachable 14，反向 4
- `denied` 在 test 证据集中为 0
- class-weighted-F1≈0.81 尚可；业务应盯 **unreachable 是否被打成 reachable**

### Commitment（157）
- 几乎全是 `committed`（154）；**3 条 `resistant` 全错成 committed**
- 与 RC 类似：多数类完美，少数类归零 → 先看 3 条样本再决定是否动 ontology

## 4. Process / Event

| Head | 结论 |
|------|------|
| NegotiationRequest / Grievance | pos 满分，冻结 NR 侧表现健康 |
| IdentityProcess | P=1、R=0.318、yes→no **148**；且 train=false → **Excluded from primary score**，不应进 State 主验收；对应同事 P1 |

IdentityProcess 几乎单独解释了 Evidence Positive Recall（0.9355）相对 Precision（0.9913）的缺口，以及 legacy event kind 的 0.2413。

## 5. 优先级建议（与同事路线对齐）

| 优先级 | 依据 |
|--------|------|
| **P0 已完成** | 本报告体系已暴露真实能力（0.96 vs 0.45） |
| **P1 IdentityProcess** | 最大 residual；移出/降权 State 验收，另立 event 方案 |
| **P1 小样本审计** | Asset unavailable×11、Contactability×18 混淆、Commitment resistant×3、RC 仅 partial 分布 |
| **暂缓** | 换 encoder / focal / 追 legacy macro-F1 |

## 6. 一句话结论

> 全量 v3.1.2 在 **evidence positive** 口径下加权 F1≈**0.96**，binary 与 NR/Grievance 很强；剩余问题集中在 **IdentityProcess 漏检** 与 **multi-state 少数类（unavailable / resistant / RC 分布）**，应用 residual 分析推进，而不是继续刷 legacy macro-F1。
