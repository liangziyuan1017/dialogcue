# Multihead State Training (v3.1.2)

独立交付分支：仅含 **ontology v3.1.2 冻结产物** 与 **multihead 建库 / 训练 / 评估** 生效代码。  
无 pipeline 旧栈、无归档迁移脚本、无本地 data/checkpoint。

## 布局

```
label_handler/ontology_v2/          # 训练本体 + 知识本体 + freeze 镜像
label_handler/fact/raw_to_trainable_mapping.yaml  # 可选：重新 export 时 legacy bridge
training/multihead/
  configs/                          # schema / map / overrides / build / train
  scripts/                          # export → audit → build → train → eval（仅 5 个）
  src/                              # 自包含 runtime
  docs/DESIGN_v3.1.1.md             # 架构审阅
  artifacts/v3.1.2_freeze/          # 冻结交付包 + CHANGELOG
```

## 命令（仓库根目录）

```bash
python training/multihead/scripts/export_raw_to_multihead.py
python training/multihead/scripts/audit_v31_consistency.py
python training/multihead/scripts/build_state_dataset.py --config training/multihead/configs/build_state_dataset.yaml
python training/multihead/scripts/train_state.py --config training/multihead/configs/train_state.yaml
python training/multihead/scripts/eval_state.py --ckpt training/multihead/checkpoints/state_v31/state_best.pt --split test
```

全量机还需：编码器权重（见 `configs/train_state.yaml` 的 `model_name`）、建库输入数据路径、以及（训练时）可写的 `data/state` / `checkpoints` 目录。

## 文档

- `training/multihead/README.md`
- `training/multihead/artifacts/v3.1.2_freeze/CHANGELOG_v3_to_v3.1.2.md`
- `label_handler/ontology_v2/README.md`
