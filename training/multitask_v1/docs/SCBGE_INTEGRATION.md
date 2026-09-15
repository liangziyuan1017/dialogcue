# Multitask v1 → SCBGE `main` F008 对接

本文说明：在 **`Bert_training`** 上完成训练后，如何把 checkpoint 接到 **`main`** 预留的 `extract_state_bert` 接口。

相关代码：

| 路径 | 作用 |
|------|------|
| `src/f008_compat.py` | 产出与 main 一致的 `{facts,emotions,actions,willingness,confidence,method}` |
| `configs/f008_fact_group_map.yaml` | Fact head → SCBGE canonical group 名 |
| `integration/drop_in_bert_extractor.py` | 覆盖 main 占位实现的 drop-in |
| `tests/test_f008_compat.py` | 契约测试（mock ckpt，无需 RoBERTa 权重） |

---

## 1. 训练（本分支）

详见 [`FULLDATA_RUNBOOK.md`](FULLDATA_RUNBOOK.md)。最短路径：

```bash
# 建库 → 门禁 → 训练（建议加 --calibrate）→ 评估
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

产物：

- `.../multitask_best.pt`
- 同目录 `thresholds.json`（`--calibrate` 或 `calibrate_thresholds.py`）

本地无全量数据时：

```bash
python -m pytest training/multitask_v1/tests -q
```

---

## 2. 适配层在做什么

`main` 的 F008 期望：

```python
{
  "facts": ["financial_hardship", ...],   # canonical group 名
  "emotions": ["distress", ...],          # 与 labels_emotion.yaml 一致
  "actions": [],                          # v1 无催收动作头，固定 []
  "willingness": "weak" | None,           # 5 档
  "confidence": 0.0..1.0,
  "method": "bert",
}
```

`f008_compat.extract_state_bert`：

1. 用 `context_turns` + 当前句拼 4×200 窗（与训练一致）
2. `decode_multitask_output`（读 `thresholds.json`）
3. `fact_active` → `f008_fact_group_map.yaml` → `facts`
4. 客户角色填 emotion / willingness；**催收员角色清空客户态**，`actions=[]`

Willingness / Emotion 词表已与 main 文档示例对齐。Fact 组名通过 YAML 映射；若 main taxonomy 变更，只改 map，不必重训。

---

## 3. 接到 `main`（三步）

### 3.1 准备路径

假设：

- Bert_training 仓：`/path/to/debt_collection`（本分支）
- main 仓 / 同仓 main 工作树：`/path/to/scbge_main`
- ckpt 目录：`.../checkpoints/multitask_v1/`

### 3.2 替换占位实现

把本仓文件拷到 main：

```text
training/multitask_v1/integration/drop_in_bert_extractor.py
  →  src/f008_state_extraction/bert_extractor.py
```

（main 文档见 `docs/features/F008-bert-multitask-bridge.md`。）

### 3.3 改 `config.md`

```yaml
extraction:
  provider: bert          # 或运行时 EXTRACTION_PROVIDER=bert
  bert:
    model_dir: "/path/to/checkpoints/multitask_v1"   # 或 multitask_best.pt
    device: auto          # cpu | cuda | mps | npu:0
    multitask_root: "/path/to/debt_collection/training/multitask_v1"
    # 可选：
    # fact_map_path: ".../configs/f008_fact_group_map.yaml"
    # thresholds_path: ".../thresholds.json"
    # train_config: ".../configs/train_multitask.yaml"
```

环境变量等价项：

- `EXTRACTION_PROVIDER=bert`
- `EXTRACTION_BERT_MODEL_DIR=...`
- `MULTITASK_V1_ROOT=.../training/multitask_v1`

### 3.4 冒烟

```bash
# 在 Bert_training
python -c "
from pathlib import Path
import sys
sys.path.insert(0, 'training/multitask_v1/src')
from f008_compat import extract_state_bert
print(extract_state_bert('我现在没钱还', model_dir='training/multitask_v1/checkpoints/multitask_v1', device='cpu'))
"

# 在 main（provider=bert 后）
pytest src/tests/f008_state_extraction -q
```

未装 torch / 未设 `model_dir` 时保持 `provider: llm`，占位不会被调用。

---

## 4. 已知边界

| 项 | 说明 |
|----|------|
| **无 Action 头** | 催收员 `actions` 恒为 `[]`；动作仍靠 LLM/keyword，或后续单独模型 |
| **在线 F008 只传 utterance** | main 当前 `extract_state(utterance)` 不传 role/context；适配层按客户单句窗推理。离线 F000 会传 `role` + `context_turns` |
| **标签空间** | Fact 经 map 对齐 SCBGE group；若树节点缺某 group，需扩 taxonomy 或改 map |
| **依赖** | `provider: bert` 时需要 torch + 与训练相同的 encoder 权重路径 |

---

## 5. 仅验证契约（无 ckpt）

```bash
python -m pytest training/multitask_v1/tests/test_f008_compat.py -q
```

测试用 `__mock__` encoder 写临时 `.pt`，断言输出键与 `financial_hardship` / emotion / willingness 映射。
