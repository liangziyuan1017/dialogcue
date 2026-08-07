# Multihead 全量实验结果（V3 / pre–v3.1.2）

**读者：** 同事评估用  
**状态：** 全量数据环境已跑通 train + test eval；**不是** v3.1.2 冻结 map 后的结果  
**整理日期：** 2026-08-05  
**证据来源：** 全量机 `training/multihead/checkpoints/state_v31/eval_test.md`（`state_best.pt` · `--split test`）

---

## 1. 版本边界（请先读）

| 项目 | 本报告 |
|------|--------|
| 训练栈 | Stage2 **Multihead**（19-head current state，非 E1-A 扁平 Softmax） |
| Checkpoint 目录 | `checkpoints/state_v31/`（配置 `output_dir: state_v31`） |
| 相对 v3.1.2 | **之前**：无 FH A∧B / NR speech-act 冻结补丁；map 为当时全量机上的 multihead 导出 |
| 相对知识本体「压缩 v3」 | 已是 multihead 训练层（schema v3.1），不是 47-fact 旧 Stage2 |

后续若对比 **v3.1.2 冻结 map**，需重建库 +（建议）重训后再 eval；本文件只作 **pre–v3.1.2 全量基线**。

---

## 2. 训练设定（配置快照）

来自当时 / 当前仓库 `configs/train_state.yaml` 约定（全量机按此跑）：

| 项 | 值 |
|----|-----|
| Encoder | `chinese-roberta-wwm-ext-large` |
| 设备 | Ascend NPU（全量环境） |
| batch_size | 16 |
| max_length | 256 |
| epochs | 8（early_stop_patience=2） |
| Loss | CE + mask + Effective-Number class weight；focal=off |
| 监督原则 | Evidence-only（`unknown` / `head_mask=0` 不进 loss） |
| 窗口 | ≤4 turns / ≤200 chars（与建库一致） |
| 输出 | `checkpoints/state_v31/state_best.pt`（按 val macro-F1） |

**说明：** 本整理以 **test eval 报告** 为主；若需 epoch-loss / 早停轮次，请另附全量机训练日志（本仓库未入库）。

---

## 3. Test 总体结果

评分模式：**evidence-only**（各头仅统计有证据监督的样本）。

| 指标 | 数值 |
|------|-----:|
| **macro-F1（主指标）** | **0.4527** |
| weighted macro-F1 | 0.4659 |
| by kind · state | 0.4507 |
| by kind · process | 0.5000 |
| by kind · event | 0.3902 |
| n_heads_scored | 19 |

**读数提示（binary 头）：**  
表中常见 `macro-F1 ≈ 0.5` 且 `pos-F1 = 1.0`。在 evidence-only 下若几乎只有正类被计入，macro 会对「无 support 的默认类」平均进 0 分 F1，从而把完美正类拉成 ~0.5。**评估 binary 头请优先看 pos-F1 / pos-P / pos-R**，不要只看 macro-F1。

Support 量级（如 FinancialHardship **4710**、Income **3540**）表明这是 **全量切分**，不是本地小样本。

---

## 4. 分头结果（test）

### 4.1 偏强（大正类 / 高 pos 指标）

| Head | kind | support | macro-F1 | pos-F1 | pos-P | pos-R | acc |
|------|------|--------:|---------:|-------:|------:|------:|----:|
| Employment | state | 103 | 0.50 | 1.00 | 1.00 | 1.00 | 1.00 |
| Income | state | 3540 | 0.50 | 1.00 | 1.00 | 1.00 | 1.00 |
| FinancialHardship | state | 4710 | 0.50 | 1.00 | 1.00 | 1.00 | 1.00 |
| Health 等若干 binary | state | （见图） | ~0.50 | 1.00 | 1.00 | 1.00 | 1.00 |

解读：在 **当时 map + window 监督** 下，困难/收入类大正类头 **可学性很强**；这是后续做 3.1.2 语义收紧前的「宽监督」基线，不等于冻结后的业务纯度。

### 4.2 偏弱（建议同事重点看）

| Head | kind | support | macro-F1 | pos-F1 | 备注 |
|------|------|--------:|---------:|-------:|------|
| Contactability | state | 692 | **0.28** | 0.61 | 触达三类混淆重 |
| Asset | state | 640 | **0.29** | 0.77 | 系统性偏向 available |
| RepaymentCapability | state | 972 | **0.31** | 0.87 | insufficient↔partial |
| Commitment | state | 506 | 0.33 | 0.97 | 少量 committed↔resistant |
| IdentityProcess | event | 1438 | **0.39** | 0.78 | 高 P、低 R（漏检） |

其余 head 细节以全量机 `eval_test.md` 全文表为准。

---

## 5. 主要混淆（Head confusion top）

### RepaymentCapability
- `insufficient → partial`：**116**
- `partial → insufficient`：13  

→ 模型偏把「不足」判成「部分可还」；能力边界仍糊。

### Asset
- `unavailable → available`：**142**
- `available → unavailable`：4  

→ 明显偏向「有资产/可用」。

### Contactability
- `unreachable → reachable`：**136**
- `reachable → unreachable`：**103**
- `unreachable → denied`：23  
- `reachable → denied`：6  

→ 可达 / 不可达双向糊；另有少量打成 denied。

### Commitment
- `committed → resistant`：7  
- `resistant → committed`：7  

→ 量小，对称互换。

### IdentityProcess
- `yes → no`：**518**  
- （报告可见 pos-P=1.0、pos-R≈0.64）  

→ **几乎不误报正类，但大量漏检**；且训练配置里 IdentityProcess 常为 mask=0 / 弱监督，解读时需结合「是否真正进 Softmax loss」。

---

## 6. 给同事的评估结论（建议口径）

1. **全量闭环成立：** multihead 在 Ascend 全量数据上可完成建库→训练→test eval；主指标 macro-F1 **≈0.45**。  
2. **结构可学：** FH / Income 等证据充足的 binary 头 pos 指标接近饱和 → 架构与窗口设定不是主瓶颈。  
3. **当前短板：**  
   - **多类状态边界**：RC、Asset、Contactability  
   - **IdentityProcess 漏检**（若业务需要该头，需单独看监督是否打开）  
4. **与 v3.1.2 的关系：** 本结果 **不能** 代表 FH/NR 冻结后的纯度或指标；3.1.2 目标是减监督污染与对齐 speech-act，**可能拉低部分 raw 召回、换业务可解释性**——应用冻结 map 重建后再做 A/B。  
5. **指标使用：** 对外汇报 binary 头请并列 **pos-F1**；勿单独用 macro-F1=0.5 解读为「只学了一半」。

---

## 7. 建议的下一步（评估后）

| 优先级 | 动作 |
|--------|------|
| P0 | 用 **v3.1.2 冻结 map** 全量 rebuild → train → eval，与本基线对比 FH/NR/RC |
| P1 | 抽 RC / Asset / Contactability 混淆句做错误分析（模型 vs 标签） |
| P2 | 明确 IdentityProcess 是否保留为训练目标；若否，评估报告可降权或剔除 |
| P3 | 归档全量机 `eval_test.md` / `eval_test.json` + 训练 log 到交付包，便于复现 |

---

## 8. 附件索引

| 路径（全量机） | 内容 |
|----------------|------|
| `training/multihead/checkpoints/state_v31/state_best.pt` | 最佳权重 |
| `training/multihead/checkpoints/state_v31/eval_test.md` | 本报告数字来源 |
| `training/multihead/configs/train_state.yaml` | 训练/评估共享配置 |
| `training/multihead/artifacts/v3.1.2_freeze/` | **更新** 后的冻结交付（对照用，非本跑） |

---

*文档依据全量环境屏幕截取的 `eval_test.md` 整理；若同事需要 JSON 原件或训练曲线，请从全量机同目录导出后补链。*
