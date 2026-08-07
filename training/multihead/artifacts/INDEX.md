# multihead artifacts 索引

按时间线归档；**当前生效**以粗体标出。

## 当前生效

| 路径 | 说明 |
|------|------|
| **`v3.1.2_patch1/`** | Ontology/map/boundary gate 拷贝包 + `LIST.md`（下一轮 `state_v312_patch1`） |
| **`v3.1.2_freeze/`** | v3.1.2 冻结快照（baseline） |
| **`v3.1.2_must_replace/`** | 全量机从 V3→v3.1.2 必换文件 |

## 评估与决策（只读交付）

| 路径 | 说明 |
|------|------|
| `V312_EVAL_TEST_V32_FULL.md` | 全量 v3.1.2 test · eval report **v3.2** 全文 + 分析 |
| `V312_FULLDATA_TRAIN_EVAL_REPORT.md` | 全量训练/评估纪要 |
| `V3_FULLDATA_TRAIN_EVAL_REPORT.md` | 改窗前 V3 对照 |
| `state_v312_eval_test.md` | 早期 legacy 指标摘录 |
| `DECISION_PACKAGE_V312_TEXT_FROM_SCREENSHOTS.md` | Residual audit 文字版（截图转录） |

## 历史 / 迁移（勿当 runtime）

| 路径 | 说明 |
|------|------|
| `v3.1.1_baseline/` | 改窗前对照 |
| `v3.1.2_migration/` | 一次性迁移证据 |
| `v3.1.2_must_replace.zip` | must_replace 压缩包 |

## 命名约定（避免混淆）

| 名字 | 含义 |
|------|------|
| ontology `v3.1.2` / `v3.1.2-patch1` | 训练本体版本 |
| eval report **v3.2** | 指标报告框架（Evidence Positive F1） |
| ckpt `state_v312` / `state_v312_patch1` | 权重目录 |
| eval **`eval_v33`** | patch1 之后的评估报告文件名 |
| freeze 候选 `ontology_fact_v3.2` | patch 验证通过后的本体冻结名 |
