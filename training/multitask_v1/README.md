# Multitask v1

Fact (19-head patch1) + Emotion (11) + Willingness (5)，共享 encoder。

| 文档 | 用途 |
|------|------|
| [`SPECIFICATION.md`](SPECIFICATION.md) | 契约真源 |
| [`docs/BUILD_DATASET.md`](docs/BUILD_DATASET.md) | 建库契约 |
| [`docs/FULLDATA_RUNBOOK.md`](docs/FULLDATA_RUNBOOK.md) | **全量机**建库/训/评步骤 |

不修改 `training/multihead/`；Fact schema/map/evidence metrics 只读引用。

## 本地验证（无全量数据）

```bash
python -m pytest training/multitask_v1/tests -q
python training/multitask_v1/scripts/smoke_check.py
```

## 全量机（与 multihead 同级）

```bash
# 1) 建库
python training/multitask_v1/scripts/build_multitask_dataset.py \
  --config training/multitask_v1/configs/build_multitask_dataset.yaml

# 2) 门禁
python training/multitask_v1/scripts/audit_fulldata_ready.py --strict

# 3) 训练（默认 npu:0 + RoBERTa large）
python training/multitask_v1/scripts/train_multitask.py \
  --config training/multitask_v1/configs/train_multitask.yaml

# 4) 评估
python training/multitask_v1/scripts/eval_multitask.py \
  --ckpt training/multitask_v1/checkpoints/multitask_v1/multitask_best.pt \
  --split test
```

细节见 [`docs/FULLDATA_RUNBOOK.md`](docs/FULLDATA_RUNBOOK.md)。  
推理解码（不用训练 mask）见 [`docs/INFERENCE.md`](docs/INFERENCE.md)。  
训完用 `calibrate_thresholds.py`（或 `train --calibrate`）写 `thresholds.json`；`infer_multitask.py` 会自动加载。
