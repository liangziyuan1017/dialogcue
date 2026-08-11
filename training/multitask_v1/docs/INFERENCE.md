# Multitask v1 — Inference（可用解码，不用训练 mask）

## 核心原则

训练时的 `fact_mask` / `emotion_mask` **只表示「有没有监督」**，推理时**不要**伪造 mask。

模型总会输出每个 head 的类别分布。业务「报不报」用**解码 + 阈值**：

### Fact

1. Softmax → argmax  
2. 预测 = schema default（`none`/`no`）→ `active=false`  
3. Binary：正类仅当 `P(pos) ≥ threshold` 才 fire（可用 **per-head** 阈值）  

### Emotion / Willingness

- top-1；若 `max_prob < min_prob` 则 `abstain`

## 训完后校准（推荐）

```bash
# 方式 A：训练结束自动扫 val
python training/multitask_v1/scripts/train_multitask.py \
  --config training/multitask_v1/configs/train_multitask.yaml \
  --calibrate

# 方式 B：已有 ckpt 单独扫
python training/multitask_v1/scripts/calibrate_thresholds.py \
  --ckpt training/multitask_v1/checkpoints/multitask_v1/multitask_best.pt \
  --config training/multitask_v1/configs/train_multitask.yaml \
  --split val
```

写出：`<ckpt_dir>/thresholds.json`（含 `fact_binary_threshold`、per-head、emo/will min_prob）。

## 推理（自动读 thresholds.json）

```bash
python training/multitask_v1/scripts/infer_multitask.py \
  --ckpt .../multitask_best.pt \
  --input sample.json
```

- 默认加载同目录 `thresholds.json`（若存在）  
- 也可用 `--thresholds path.json`  
- CLI `--fact-threshold` / `--emotion-min-prob` / `--willingness-min-prob` 可覆盖文件  

没有 thresholds 文件时：Fact=0.5，emo/will 不弃权。

### 输入 JSON

```json
{"context_window": "[collector] ...\n[customer] ..."}
```

或 turns + `anchor_turn_id`（脚本内 4×200 裁窗）。

业务优先读 **`fact_active` + emotion + willingness`**。
