# Multitask v1 Specification（Fact + Emotion + Willingness）

**Status:** frozen contract for coding  
**Path:** `training/multitask_v1/`（不修改 `training/multihead/`）  
**Principle:** 文档先行；实现必须与本文件及 `configs/contract.yaml` 对齐。

---

## 1. Goal

交付可训练、可评估的生产向对话理解模型：

```
Shared Encoder
 ├── Fact: 19-head v3.1.2-patch1（masked multi-head classification）
 ├── Emotion: 11-class CE（v1 无 adjacency loss）
 └── Willingness: 5-class CE
```

- **multihead/**：state tracking 实验，冻结不动  
- **multitask_v1/**：三任务联合 + window context 的交付代码

---

## 2. Fact（必须澄清）

### 2.1 结构

不是 flat MLC，也不是 per-head **BCE**。是 **19 个独立 categorical head**：

```
每个 head:
  Linear(hidden, n_values)          # n_values = ontology 该类目数（含 none/no 等）
  loss = CrossEntropyLoss over values
  unknown / not-observed → 不参与 loss，也不进 evidence-only eval
```

等价语义（两种实现择一，当前代码用「行级 mask 过滤后再 CE」，与 `ignore_index=-100` 等价）：

```
# conceptual
loss_h = CE(logits_h, label_h)   # only rows with head_mask[h]==1
# OR
loss_h = CE(logits_h, label_h, ignore_index=-100)
```

**禁止：** 把 19 个 head 做成 flat multi-label BCE。

契约句（冻结）：

> Fact heads are categorical classification heads with masked CrossEntropyLoss. Unknown/not-observed samples are excluded from loss and from evidence-only evaluation.

## 2b. Task masks（Emotion / Willingness 未标注绝不当作类别）

每条样本必须带任务级 mask（已实现字段名）：

| 字段 | 含义 |
|------|------|
| `fact_mask[head]` | 该 Fact head 有证据才为 1 |
| `emotion_mask` | 窗口内可映射到 11 类才为 1；否则 0 |
| `willingness_mask` | 窗口内可映射到 5 类才为 1；否则 0 |

```json
{
  "fact_labels": {"Asset": "unavailable", "Income": "unknown"},
  "fact_mask": {"Asset": 1, "Income": 0},
  "emotion": null,
  "emotion_mask": 0,
  "willingness": "conditional",
  "willingness_mask": 1,
  "task_mask": {"fact": 1, "emotion": 0, "willingness": 1}
}
```

- `emotion is null` / 不可映射 → **`emotion_mask=0`**，placeholder index **不进 CE**（不会当成 distress=0 训）
- Willingness 同理
- 建库策略见 `docs/BUILD_DATASET.md`：`anchor_then_window_last`；无证据保持 null

### 2.2 Ontology / Schema

| 项 | 值 |
|----|-----|
| Fact ontology | `training_ontology_v3.1.2-patch1` |
| Runtime schema | `training/multihead/configs/schema_v3.1.yaml`（只读引用 YAML，非 runtime import 训练代码） |
| Map / overrides | multihead `raw_to_multihead*.yaml`（只读） |

### 2.3 Training vs Evaluation

| 阶段 | 行为 |
|------|------|
| **Training** | 保留 positive / negative（如 `none`/`no`）监督；`unknown`/`missing` → `head_mask=0` **不进 loss** |
| **Evaluation** | **evidence-only**：仅 `head_mask=1` 且 label≠unknown 计分；主指标沿用 multihead Evidence Positive F1 |

> **evidence-only 仅用于 evaluation scoring，不用于「训练时丢掉全部负例」。**

`IdentityProcess`：train 默认 mask=0；eval 口径与 multihead 一致（非 primary）。

### 2.4 Commitment vs Willingness

禁止混用 `resistant`：

| 命名空间 | 标签 |
|----------|------|
| `fact.Commitment` | `committed` / `resistant` / `none` |
| `willingness` | `resistant` / `weak` / `conditional` / `negotiating` / `strong` |

Checkpoint metadata 必须分字段记录。

---

## 3. Emotion

### 3.1 Labels（11v1，冻结）

顺序固定（index = 训练/评估 id）：

1. `distress`  
2. `despair`  
3. `complaint`  
4. `irritation`  
5. `hostility`  
6. `anxiety`  
7. `distrust`  
8. `confusion`  
9. `defensive`  
10. `negotiation`  
11. `engagement`

权威名单与 deploy `tag_labels_emotion.py` / `configs/labels_emotion.yaml` 一致。

### 3.2 v1 Training

- Loss：**11-class CE only**  
- **不引入** adjacency soft-label / adjacency loss  
- `adjacency: none`（写入 checkpoint）

### 3.3 v1 Evaluation（strict + adjacent）

必须同时输出：

| 指标 | 用途 |
|------|------|
| `strict_accuracy` / `strict_macro_f1` / `strict_weighted_f1` | 主报告 |
| confusion matrix | 主报告 |
| `adj_accuracy` / `adj_macro_f1` | 邻近可解释指标（**不进训练**） |
| `emotion_confusion_graph`（或等价 top confusions） | 落盘 |

邻接表：`configs/emotion_adjacent.yaml`  
默认评估集合 = `data_validated ∪ rule_only`（字段 `eval_set: all_rule`）。  
metadata 必须写明用了哪一档，避免 v1 / v1.1 口径漂移。

### 3.4 v1.1（本仓库本期不做实现，仅契约预留）

只改 Emotion loss：`CE` vs `CE + adjacency soft label`；  
dataset / encoder / Fact / Willingness / context **全部冻结**。

---

## 4. Willingness

5 级顺序（冻结）：

```
resistant → weak → conditional → negotiating → strong
```

v1：5-class CE。  
Eval：`accuracy` / `macro_f1` / `weighted_f1`（strict）。

---

## 5. Context（冻结）

```yaml
context:
  strategy: window_only
  max_turns: 4
  max_chars: 200
```

与 multihead 已验证的 window 规则一致：最多 4 turns、最多 200 chars，从最旧 turn 裁剪，尽量保留 anchor。

---

## 6. Checkpoint metadata（最低字段）

```yaml
fact: v3.1.2-patch1
emotion: 11v1
willingness: 5v1
adjacency: none          # train loss; eval may still report adj metrics
context:
  strategy: window_only
  max_turns: 4
  max_chars: 200
model:
  encoder: <name or __mock__>
  hidden_size: <int>
loss:
  fact: masked_multihead_ce
  emotion: ce
  willingness: ce
  task_weights: {fact: ..., emotion: ..., willingness: ...}
schema_fact_path: <path>
emotion_adjacent_eval_set: all_rule   # or data_validated
```

---

## 7. Loss 合成

```
L = w_f * L_fact + w_e * L_emotion + w_w * L_willingness
```

默认权重见 `configs/train_multitask.yaml`。  
Emotion / Willingness 无标签样本：各自 mask 出 loss（与 Fact mask 同理）。

---

## 8. Dataset build（必须，全量训前）

契约细节见 [`docs/BUILD_DATASET.md`](docs/BUILD_DATASET.md)。

```bash
python training/multitask_v1/scripts/build_multitask_dataset.py \
  --config training/multitask_v1/configs/build_multitask_dataset.yaml
```

对每个 **customer anchor turn**：

1. Context：与训练相同的 `window_only / max_turns=4 / max_chars=200`（先裁窗，再取 `turn_ids`）
2. **Fact**：window 内 customer raw facts → multihead `raw_to_multihead` → `fact_labels` + `fact_mask`（unknown→mask0；与 `build_state_dataset` 同口径）
3. **Emotion / Willingness**：同一 `turn_ids` 上 raw → 冻结 mapping → 单标签；无证据则 `null`（训练 mask=0）
4. 选择策略（冻结）：`anchor_then_window_last`（优先 anchor turn 最后一条可映射标签，否则窗口内时间序最后一条）
5. 写出 `data/multitask_{train,val,test}.jsonl`

禁止用「全对话累计 memory」做 Softmax/CE 监督。  
全量训练配置应 `use_mock_if_missing: false`。

---

## 9. Directory layout

```
training/multitask_v1/
  SPECIFICATION.md
  docs/BUILD_DATASET.md
  README.md
  configs/
    contract.yaml
    build_multitask_dataset.yaml
    labels_*.yaml / emotion_adjacent.yaml / train_multitask.yaml
  src/
    build_samples.py   # 建库核心
    ...
  scripts/
    build_multitask_dataset.py
    train_multitask.py / eval_multitask.py / smoke_check.py
  tests/
```

禁止在 `training/multihead/` 内为 multitask 改代码。Fact schema / map / label_mask / conversation_parser **只读引用**。

---

## 10. Local verification（门禁）

开训前 / CI 本地至少：

```bash
python -m pytest training/multitask_v1/tests -q
python training/multitask_v1/scripts/smoke_check.py
```

全量机按 [`docs/FULLDATA_RUNBOOK.md`](docs/FULLDATA_RUNBOOK.md)：

```bash
build_multitask_dataset.py → audit_fulldata_ready.py --strict → train_multitask.py → eval_multitask.py --split test
```

Smoke：合成对话建库 → mock encoder 1 epoch → eval（无 HF、可不依赖 `output_rewarded.py`）。
全量默认：`device=npu:0`、RoBERTa large、EN class weight、warmup/grad_clip/early_stop、encoder 热启。

---

## 11. Non-goals (v1)

- 不改 Emotion 11 / Willingness 5 ontology  
- 不训练 adjacency loss  
- 不覆盖 multihead checkpoints / 报告  
- 不追求 legacy flat-fact macro-F1 可比
