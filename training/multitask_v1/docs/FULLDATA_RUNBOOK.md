# Multitask v1 — Full-data runbook

与 multihead 全量机流程对齐。契约：`SPECIFICATION.md` + `docs/BUILD_DATASET.md`。

## 0. 环境

```bash
# Ascend
source /usr/local/Ascend/ascend-toolkit/set_env.sh   # 按机器实际路径
python -c "import torch,torch_npu; print(torch.npu.is_available())"
```

确认：

- `output_rewarded.py` 在仓库根（或改 `configs/build_multitask_dataset.yaml` 的 `input_path`）
- encoder：`hfl/chinese-roberta-wwm-ext-large`（与 multihead 同路径）
- 可选 Stage1 ckpt：`training/checkpoints/stage1/stage1_last.pt`

## 1. 建库

```bash
python training/multitask_v1/scripts/build_multitask_dataset.py \
  --config training/multitask_v1/configs/build_multitask_dataset.yaml
```

产出：

- `training/multitask_v1/data/multitask_{train,val,test}.jsonl`
- `training/multitask_v1/data/reports/build_summary.md`

## 2. 开训前门禁

```bash
python training/multitask_v1/scripts/audit_fulldata_ready.py --strict
# 可选：顺带跑 multihead map/patch 审计
python training/multitask_v1/scripts/audit_fulldata_ready.py --run-multihead-audits --strict
```

## 3. 训练

```bash
python training/multitask_v1/scripts/train_multitask.py \
  --config training/multitask_v1/configs/train_multitask.yaml \
  --device npu:0
```

默认配置已对齐 multihead：

| 项 | 值 |
|----|-----|
| device | `npu:0` |
| model | chinese-roberta-wwm-ext-large |
| epochs / batch | 8 / 16 |
| warmup / grad_clip / early_stop | 0.1 / 1.0 / 2 |
| EN class weight | on（Fact + Emotion + Will） |
| init_from_encoder | true（缺 ckpt 则 WARN 后从 HF 训） |

产出：`checkpoints/multitask_v1/multitask_best.pt` + `val_metrics_best.md`

## 4. 评估

```bash
python training/multitask_v1/scripts/eval_multitask.py \
  --ckpt training/multitask_v1/checkpoints/multitask_v1/multitask_best.pt \
  --config training/multitask_v1/configs/train_multitask.yaml \
  --split test \
  --device npu:0
```

写出 `eval_test.json` / `eval_test.md`（Fact evidence-only + Emotion strict/adj + Will）。

## 5. 本地无全量数据时

```bash
python training/multitask_v1/scripts/smoke_check.py
# 或
python training/multitask_v1/scripts/build_multitask_dataset.py --smoke
python training/multitask_v1/scripts/train_multitask.py --smoke
```

`--smoke` 强制 `__mock__` + `cpu`，不依赖 NPU / HF / `output_rewarded.py`。
