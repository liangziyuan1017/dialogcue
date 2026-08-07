# v3.1.2 必须替换包（从全量 V3 / state_v31 → 冻结 v3.1.2）

**包路径：** `training/multihead/artifacts/v3.1.2_must_replace/`  
**用途：** 只含「不做就不是 3.1.2」的文件；拷到全量机仓库**根目录**下同名路径即可。

## 拷贝方式（推荐）

在全量机仓库根目录执行（先备份同名旧文件）：

```bash
# 假设本包已放到 /tmp/v3.1.2_must_replace
cp -a /tmp/v3.1.2_must_replace/training/multihead/configs/. training/multihead/configs/
cp -a /tmp/v3.1.2_must_replace/training/multihead/scripts/build_state_dataset.py training/multihead/scripts/
cp -a /tmp/v3.1.2_must_replace/label_handler/ontology_v2/. label_handler/ontology_v2/
```

或按下面清单逐个覆盖。

---

## 文件清单 → 目标位置

| 包内相对路径 | 拷贝到（仓库根下） | 说明 |
|--------------|-------------------|------|
| `training/multihead/configs/raw_to_multihead.yaml` | `training/multihead/configs/raw_to_multihead.yaml` | **运行时权威 map**（冻结） |
| `training/multihead/configs/raw_to_multihead_overrides.yaml` | `training/multihead/configs/raw_to_multihead_overrides.yaml` | FH/NR 污染桥 drop |
| `training/multihead/configs/schema_v3.1.yaml` | `training/multihead/configs/schema_v3.1.yaml` | 19-head schema |
| `training/multihead/configs/annotation_policy_v3.1.2.yaml` | `training/multihead/configs/annotation_policy_v3.1.2.yaml` | window + 头证据策略（**新建或覆盖**） |
| `training/multihead/configs/build_state_dataset.yaml` | `training/multihead/configs/build_state_dataset.yaml` | 建库配置；**请改 `input_path` 指向全量数据** |
| `training/multihead/scripts/build_state_dataset.py` | `training/multihead/scripts/build_state_dataset.py` | **window 标签**（相对旧 V3 最关键脚本） |
| `label_handler/ontology_v2/training_ontology_v3.yaml` | `label_handler/ontology_v2/training_ontology_v3.yaml` | 冻结训练本体（由 freeze 的 `training_ontology_v3.1.2.yaml` 命名） |
| `label_handler/ontology_v2/proposed_ontology.yaml` | `label_handler/ontology_v2/proposed_ontology.yaml` | 知识本体 |

### NPU / eval 落到 CPU 时请再拷（补丁）

| 包内相对路径 | 拷贝到 | 说明 |
|--------------|--------|------|
| `training/multihead/configs/train_state.yaml` | `training/multihead/configs/train_state.yaml` | 含 `device: "npu:0"`；**合并前保留你的 data/output_dir/model_name 路径** |
| `training/multihead/scripts/eval_state.py` | `training/multihead/scripts/eval_state.py` | 打印 device 诊断；强制 NPU 失败会报错 |
| `training/multihead/src/device_utils.py` | `training/multihead/src/device_utils.py` | NPU 检测与报错 |

---

## 拷贝后必做

1. 编辑 `training/multihead/configs/build_state_dataset.yaml` 的全量 `input_path`  
2. 建议改 `train_state.yaml` 的 `output_dir` → 如 `../checkpoints/state_v312`（勿覆盖 `state_v31`）  
3. 重建库 → 训练 → eval：

```bash
python training/multihead/scripts/build_state_dataset.py --config training/multihead/configs/build_state_dataset.yaml
python training/multihead/scripts/train_state.py --config training/multihead/configs/train_state.yaml
python training/multihead/scripts/eval_state.py --ckpt training/multihead/checkpoints/state_v312/state_best.pt --split test
```

## 本包不含（一般不用换）

`train_state.py` / `eval_state.py` / `device_utils.py` / `src/models/*` 等——V3 multihead 骨架可继续用。  
若 NPU/诊断有问题，再单独同步这些文件。
