## Quality Gate Report

Spec: `docs/features/F005-context-tagging-quality-scoring.md`
原始需求: "Tag each sentence with context constraints and compute quality scores (HWR, SAS) for ranking"
检查时间: 2026-06-26

### 愿景覆盖（Step 0）
| # | Human原始需求 | AC 覆盖？ | 实现？ |
|---|---------------|-----------|--------|
| 1 | Every sentence has bg_constraints with 10 bitmask fields | AC-1, AC-2, AC-3 | ✅ All 10 fields present, bitmask int 0–1023 |
| 2 | Every sentence has win_rate (blended HWR) | AC-4, AC-5 | ✅ Blended formula with node-level aggregation |
| 3 | Every sentence has SAS | AC-6, AC-7 | ✅ DeepSeek embedding cosine similarity |
| 4 | UC and CSI deferred | AC-8 | ✅ Both = 0 with deferred: true |
| 5 | Bitmask AND filtering correct | AC-9 | ✅ (S & C) == S compatibility check |
| 6 | All 31 conversations represented | AC-10 | ✅ All call_ids in source_call_ids |
| 7 | Output to decision_tree_scored.json | AC-11 | ✅ File generated |

### 功能验收
| # | AC | 状态 | 代码位置 | 测试覆盖 |
|---|-----|------|----------|----------|
| 1 | AC-1: bg_constraints with 10 fields | ✅ | `score_tree.py` | `test_score_tree_scoring.py` |
| 2 | AC-2: bg_bitmask integer | ✅ | Bitmask encoding | `test_score_tree_scoring.py` |
| 3 | AC-3: bg_bitmask_int correctly encodes | ✅ | `_encode_bitmask()` | `test_score_tree_scoring.py` |
| 4 | AC-4: win_rate ≥ 0 and ≤ 1 | ✅ | Blended HWR | `test_score_tree_scoring.py` |
| 5 | AC-5: Blending formula correct | ✅ | `weight = n/(n+2)` | `test_score_tree_scoring.py` |
| 6 | AC-6: sas ≥ 0 and ≤ 1 | ✅ | Cosine similarity | `test_score_tree_scoring.py` |
| 7 | AC-7: SAS via char bigram TF-IDF | ✅ | `scoring_metrics.py` (ADR-020) | `test_score_tree_scoring.py` |
| 8 | AC-8: UC=0, CSI=0 deferred | ✅ | `score_tree.py` | `test_score_tree_scoring.py` |
| 9 | AC-9: Bitmask AND filtering | ✅ | `(sb & qb) == sb` | `test_score_tree_scoring.py` |
| 10 | AC-10: All 31 conversations | ✅ | E2E | `test_score_tree_integration.py` |
| 11 | AC-11: Output file exists | ✅ | `decision_tree_scored.json` | Integration test |

### 验证命令输出
test → all pass ✅
integration → pass ✅
