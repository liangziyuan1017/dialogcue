# F008 × Multitask BERT（Bert_training）对接说明

`extraction.provider: bert` 时，本仓通过 `src/f008_state_extraction/bert_extractor.py`
调用 **Bert_training** 分支的 `training/multitask_v1/src/f008_compat.py`，用已训练的
Fact / Emotion / Willingness 多任务模型替代 DeepSeek 抽状态。

训练细节以 Bert_training 文档为准：

- `training/multitask_v1/docs/FULLDATA_RUNBOOK.md`
- `training/multitask_v1/docs/SCBGE_INTEGRATION.md`

---

## 前置条件

1. 已在 **Bert_training** 训出 `multitask_best.pt`（建议同目录有 `thresholds.json`）
2. 本机可访问该 checkpoint，以及 Bert_training 的 `training/multitask_v1` 源码树
3. 安装与训练一致的推理依赖（`torch`；encoder 权重路径可读）

默认保持 `extraction.provider: llm`，不装 BERT 依赖也可跑通在线链路。

---

## 配置

`config.md`：

```yaml
extraction:
  provider: bert
  bert:
    model_dir: "/abs/path/to/checkpoints/multitask_v1"  # 或 multitask_best.pt
    device: auto   # cpu | cuda | mps | npu:0
    multitask_root: "/abs/path/to/Bert_training_repo/training/multitask_v1"
```

环境变量（可覆盖配置）：

| 变量 | 含义 |
|------|------|
| `EXTRACTION_PROVIDER=bert` | 打开 BERT 抽状态 |
| `EXTRACTION_BERT_MODEL_DIR` | checkpoint 目录或 `.pt` |
| `MULTITASK_V1_ROOT` | `training/multitask_v1` 根目录 |

可选：`extraction.bert.fact_map_path` / `thresholds_path` / `train_config`。

---

## 训练（在 Bert_training 仓）

```bash
python training/multitask_v1/scripts/build_multitask_dataset.py \
  --config training/multitask_v1/configs/build_multitask_dataset.yaml
python training/multitask_v1/scripts/audit_fulldata_ready.py --strict
python training/multitask_v1/scripts/train_multitask.py \
  --config training/multitask_v1/configs/train_multitask.yaml \
  --calibrate
python training/multitask_v1/scripts/eval_multitask.py \
  --ckpt training/multitask_v1/checkpoints/multitask_v1/multitask_best.pt \
  --split test
```

契约自测（无需真实 RoBERTa）：

```bash
python -m pytest training/multitask_v1/tests/test_f008_compat.py -q
```

---

## 对接检查清单

1. [ ] `multitask_root` 下存在 `src/f008_compat.py`
2. [ ] `model_dir` 指向含 `multitask_best.pt` 的目录（或直接指向 `.pt`）
3. [ ] `provider: bert` 或 `EXTRACTION_PROVIDER=bert`
4. [ ] 跑 `pytest src/tests/f008_state_extraction -q`（LLM 路径仍用 mock）
5. [ ] 在线抽一句话，确认返回 `method == "bert"` 且 facts/emotions/willingness 合理

未配置 `model_dir` / `multitask_root` 时，`extract_state_bert` 会抛 `RuntimeError`；
在线 `extract_state` 会捕获并回退 keyword（与原占位行为一致）。

---

## 输出约定

与 LLM 路径同形：`facts` / `emotions` / `actions` / `willingness` / `confidence` / `method:"bert"`。

- Emotion / Willingness：与 multitask 冻结词表一致（如 `distress`、`weak`）
- Facts：经 `f008_fact_group_map.yaml` 映射到本仓 taxonomy group（如 `financial_hardship`）
- Actions：multitask v1 **无**催收动作头 → 恒 `[]`（催收动作仍用 LLM/keyword）

---

## 边界

- 在线 `extract_state(utterance)` 目前只传句子，不传历史窗；适配层按**客户单句**推理。离线 F000 会传 `role` + `context_turns`。
- Fact 组名若与决策树节点不一致，改 Bert_training 侧 map 或扩展本仓 taxonomy，无需重训 encoder（除非标签语义变了）。
