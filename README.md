# Bert_training

独立训练分支：ontology v3.1.2-patch1 + multihead Fact + **multitask_v1**（Fact/Emotion/Willingness）。

与 `main`（SCBGE）无共同产品代码；对接见 `training/multitask_v1/docs/SCBGE_INTEGRATION.md`。

## 布局

```
label_handler/ontology_v2/     # 训练/知识本体 + freeze/v3.1.2 唯一快照
training/multihead/            # Fact 19-head 建库/训练/评估（schema 供 multitask 只读）
training/multitask_v1/         # 多任务主线 + F008 适配
```

## 常用命令

```bash
# multitask（推荐）
python training/multitask_v1/scripts/train_multitask.py \
  --config training/multitask_v1/configs/train_multitask.yaml --calibrate

# multihead Fact-only（legacy 对照）
python training/multihead/scripts/train_state.py \
  --config training/multihead/configs/train_state.yaml
```

## 文档

- `training/multitask_v1/README.md`
- `training/multitask_v1/docs/SCBGE_INTEGRATION.md`
- `training/multihead/README.md`
- `training/multihead/artifacts/INDEX.md`（精简说明 / 已删除冗余清单）
- `label_handler/ontology_v2/freeze/v3.1.2/CHANGELOG_v3_to_v3.1.2.md`
