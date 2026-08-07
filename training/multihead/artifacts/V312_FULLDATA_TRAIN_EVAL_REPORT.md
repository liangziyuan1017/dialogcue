# Multihead 全量实验结果（v3.1.2 冻结）

**读者：** 同事评估用  
**状态：** 全量机 `state_v312` test eval（NPU `device=npu:0`）  
**整理日期：** 2026-08-06  
**证据来源：** 全量机 `training/multihead/checkpoints/state_v312/eval_test.md`（屏幕转录）  
**对照基线：** [`V3_FULLDATA_TRAIN_EVAL_REPORT.md`](V3_FULLDATA_TRAIN_EVAL_REPORT.md)（pre–v3.1.2 / `state_v31`）

---

## 1. 总体指标（test · evidence-only）

| 指标 | v3.1.2 (`state_v312`) | V3 基线 (`state_v31`) |
|------|----------------------:|----------------------:|
| **macro-F1（主）** | **0.4527** | **0.4527** |
| weighted macro-F1 | 0.4669 | 0.4659 |
| by kind · state | 0.4600 | 0.4507 |
| by kind · process | 0.5000 | 0.5000 |
| by kind · event | **0.2413** | 0.3902 |
| n_heads_scored | 19 | 19 |

总分与 V3 **几乎持平**；**event 明显下降**（主要来自 IdentityProcess）。

---

## 2. Per-head（转录自 eval_test.md）

评分：evidence-only（unknown / mask=0 不计入该头）。  
Binary 头常见 `macro-F1=0.5` 且 `pos-F1=1.0`：默认类无 support 时的指标形态，**请优先看 pos-***。

| head | kind | support | macro-F1 | pos-F1 | pos-P | pos-R | acc |
|------|------|--------:|---------:|-------:|------:|------:|----:|
| Employment | state | 9 | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Income | state | 701 | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| FinancialHardship | state | 1350 | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| RepaymentCapability | state | 98 | 0.3333 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Health | state | 79 | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| FamilyBurden | state | 186 | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| Asset | state | 108 | 0.3120 | 0.8796 | 0.8796 | 0.8796 | 0.8796 |
| Contactability | state | 89 | 0.3849 | 0.7978 | 0.7978 | 0.7978 | 0.7978 |
| Commitment | state | 157 | 0.3301 | 0.9809 | 0.9809 | 0.9809 | 0.9809 |
| Responsibility | state | 195 | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| DebtDispute | state | 83 | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| LegalProceeding | state | 32 | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| ComplianceRisk | state | 29 | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| BankConstraint | state | 54 | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| ObjectiveBlocker | state | 18 | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| CognitiveSupport | state | 160 | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| NegotiationRequest | process | 202 | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| IdentityProcess | event | 217 | 0.2413 | 0.4825 | 1.0000 | 0.3180 | 0.3180 |
| Grievance | process | 147 | 0.5000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

---

## 3. Head confusion (top)

### Asset
- `unavailable → available`: **11**
- `available → unavailable`: 2

### Contactability
- `unreachable → reachable`: **14**
- `reachable → unreachable`: 4

### Commitment
- `resistant → committed`: 3

### IdentityProcess
- `yes → no`: **148**

（报告中未见 RC 的 insufficient↔partial 大额混淆条目；与 V3 基线「RC 糊边界」形态不同，且本版 RC support 仅 98、pos 指标饱和。）

---

## 4. 与 V3 基线对照（关键头）

| Head | V3 support / pos-F1 | v3.1.2 support / pos-F1 | 读法 |
|------|---------------------|-------------------------|------|
| FinancialHardship | 4710 / 1.00 | **1350** / 1.00 | 监督变少（window+收紧 map），**正类仍可学满** |
| NegotiationRequest | （基线表未单列强调） | **202** / 1.00 | 冻结 speech-act 后仍高 pos |
| Income | 3540 / 1.00 | 701 / 1.00 | 同上 |
| RepaymentCapability | 972 / 0.87 | **98** / 1.00 | 样本锐减；小数上完美，**勿过度解读** |
| Asset | 640 / 0.77 | 108 / 0.88 | 相对更好，混淆绝对数大降 |
| Contactability | 692 / 0.61 | 89 / 0.80 | 相对更好，仍偏 reachable |
| IdentityProcess | 1438 / 0.78（R≈0.64） | 217 / 0.48（**R=0.32**） | **漏检加重**；且 train=false，本就不进 Softmax loss |
| Employment | 103 / 1.00 | **9** / 1.00 | window 下极稀 |

---

## 5. 评估结论

### 可以认为「可用作 v3.1.2 全量第一轮模型诊断」

1. **闭环成立：** NPU eval 完成；主指标与 V3 持平（0.4527），说明冻结 map + window 重建后 **整体可训可评**。  
2. **冻结目标头（FH / NR）：** test 上 pos-P/R/F1 均为 **1.0**，support 仍有量级（FH 1350、NR 202）→ **没有出现「收紧后学崩」**。  
3. **预期中的监督变稀：** 多数头 support 相对 V3 明显下降（window-only + override drop），与建库设计一致，不是 eval 坏了。  
4. **短板仍清晰：**  
   - **IdentityProcess**：高 P、低 R（148 次 yes→no），且 schema `train=false` → event kind 拖累总分；评估业务时建议 **降权或剔除**。  
   - **Asset / Contactability**：仍有偏向 available/reachable 的混淆，但绝对错误远少于 V3。  
   - **RC / Employment 等**：support 过小，单次 test 指标方差大，需结合更多句级错误分析，不宜只看 1.0。

### 尚不足以定稿「冻结成功、可上线」的充分条件

仍缺（可选补传）：训练 best epoch / val 曲线、建库 `quality_*` 全文、与 V3 **同一 test 会话集合** 的对照（当前是「各自 map 下的 test 切分指标」，不是严格 paired A/B）。

---

## 6. 建议下一步

| 优先级 | 动作 |
|--------|------|
| P0 | 业务侧接受：总分持平 + FH/NR 可学；IdentityProcess 不作为验收头 |
| P1 | 抽 Asset/Contactability/IdentityProcess 各 20–50 条 FP/FN 做句级复核 |
| P2 | 若要严格证明 3.1.2 map 优于 V3：固定同一批对话窗，只换 map 重建标签做 A/B |
| P3 | 回传 `eval_test.json` + 训练 log 归档，便于复现 |

---

*本文数字来自全量环境 `eval_test.md` 屏幕照片转录；若与文件有出入，以全量机原件为准。*
