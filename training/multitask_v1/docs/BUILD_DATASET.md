# Multitask v1 Dataset Build Contract

与 [`../SPECIFICATION.md`](../SPECIFICATION.md) 对齐。实现：`scripts/build_multitask_dataset.py` + `src/build_samples.py`。

## 为什么必须建库

训练脚本只 **消费** JSONL。没有 build，就只能 mock，无法做真实 Fact/Emotion/Willingness 联合训练，也无法与 multihead Fact 口径对齐。

## 输入 / 输出

| | |
|--|--|
| 输入 | `output_rewarded*.py`（与 multihead `conversation_parser` 同格式） |
| 配置 | `configs/build_multitask_dataset.yaml` |
| 输出 | `data/multitask_{train,val,test}.jsonl` + `data/reports/` 摘要 |

## 单条样本字段

```json
{
  "conversation_id": "...",
  "turn_id": 12,
  "split": "train",
  "input": {
    "context_window": "[collector] ...\n[customer] ...",
    "turn_ids": [9, 10, 11, 12],
    "window_turns": 4,
    "char_budget": 200,
    "char_len": 180,
    "truncated": false
  },
  "fact_labels": { "Employment": "disrupted", "Income": "unknown", "...": "..." },
  "fact_mask": { "Employment": 1, "Income": 0, "...": "..." },
  "labels": { "...": "..." },
  "head_mask": { "...": "..." },
  "emotion": "complaint",
  "willingness": "conditional",
  "meta": {
    "label_scope": "window",
    "emotion_policy": "anchor_then_window_last",
    "willingness_policy": "anchor_then_window_last",
    "window_raws": [],
    "emotion_raws": [],
    "willingness_raws": []
  }
}
```

- `labels` / `head_mask`：与 multihead 同形，便于对照  
- `fact_*`：multitask loader 主字段（`dataset.py` 两者皆认）  
- `emotion` / `willingness`：可映射的 11/5 类名，或 `null`

## 标签范围（冻结）

1. **先** `encode_recent_window`（4 turns / 200 chars）得到 `turn_ids`  
2. Fact / Emotion / Willingness **全部**只使用这些 `turn_ids` 上的 customer 标注  
3. 不用累计对话 memory 做监督

## Fact

只读 multihead：

- `raw_to_multihead.yaml` + schema  
- `SlotRelocator`（emotion/will 槽里的 fact-like raw → facts）  
- `build_labels_and_masks`（非默认才 mask=1；IdentityProcess 恒 0）

## Emotion / Willingness

- Mapping：默认指向 multihead `configs/slot_relocate/emotion_mapping.yaml` 与 `willingness_ontology.yaml`（与 Fact 建库同源，避免口径分裂）  
- Vocab：`configs/labels_emotion.yaml` / `labels_willingness.yaml`  
- 策略：`anchor_then_window_last`  
  - 优先 **anchor** customer turn 上最后一条可映射标签  
  - 否则取 window 内时间序 **最后** 一条可映射标签  
  - 皆无 → `null`（训练 mask=0）  
- 若某 raw 仅是 fact（可 map 到 multihead）且 **不是** emotion/will 可映射标签，则不进 emotion/will 监督（与 slot relocate 一致）

## Split

按 **conversation_id** 划分（seed=42，默认 0.8/0.1/0.1），与 multihead 一致，避免对话泄漏。

## Smoke

```bash
python scripts/build_multitask_dataset.py --smoke
```

写入临时合成对话（不依赖仓库内 `output_rewarded.py`），产出小 JSONL，供单测与 `smoke_check`。
