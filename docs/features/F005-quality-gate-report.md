## Quality Gate Report

Spec: `docs/features/F005-context-tagging-quality-scoring.md`
原始需求: "Tag each sentence with context constraints and compute quality scores (HWR, SAS) for ranking"
检查时间: 2026-07-07

### 愿景覆盖（Step 0）
| # | Human原始需求 | AC 覆盖？ | 实现？ |
|---|---------------|-----------|--------|
| 1 | Every sentence has bg_constraints with 10 bitmask fields | AC-1, AC-2, AC-3 | ✅ All 10 fields present, bitmask int 0–1023 |
| 2 | Every sentence has win_rate (blended HWR) | AC-4, AC-5 | ✅ Blended formula with node-level aggregation (ADR-031) |
| 3 | Every sentence has win_rate_node | AC-5, AC-6 | ✅ Node-level HWR stored for transparency |
| 4 | Every sentence has SAS | AC-7, AC-8 | ✅ Char bigram TF-IDF cosine similarity (no external API) |
| 5 | UC and CSI deferred | AC-9 | ✅ Both = 0 with deferred: true |
| 6 | Bitmask AND filtering correct | AC-10 | ✅ (S & C) == S compatibility check |
| 7 | All 31 conversations represented | AC-11 | ✅ All call_ids in source_call_ids |
| 8 | Output to decision_tree_scored.json | AC-12 | ✅ File generated |
| 9 | Embedding absent from JSON (DB-only per guideline) | AC-13 | ✅ No embedding field; conversation_context present |
| 10 | 10-bit bitmask (range 0–1023) | — | ✅ Kept at 10 fields per user decision |

### 功能验收
| # | AC | 状态 | 代码位置 | 测试覆盖 |
|---|-----|------|----------|----------|
| 1 | AC-1: bg_constraints with 10 fields | ✅ | `score_tree.py` | `test_scored_invariants.py` |
| 2 | AC-2: bg_bitmask integer | ✅ | Bitmask encoding | `test_scored_invariants.py` |
| 3 | AC-3: bg_bitmask_int correctly encodes (0–1023) | ✅ | `_encode_bitmask()` | `test_scored_invariants.py` |
| 4 | AC-4: win_rate ≥ 0 and ≤ 1 | ✅ | Blended HWR | `test_scored_invariants.py` |
| 5 | AC-5: Blending formula correct | ✅ | `weight = n/(n+2)` | `test_scored_invariants.py` |
| 6 | AC-6: win_rate_node exists and ∈ [0,1] | ✅ | `compute_node_hwr` | `test_scored_invariants.py` |
| 7 | AC-7: sas ≥ 0 and ≤ 1 | ✅ | Cosine similarity | `test_scored_invariants.py` |
| 8 | AC-8: SAS via jieba word bigram TF-IDF (ref-vocab-restricted) | ✅ | `scoring_metrics.py` (ADR-020) | `test_score_tree_scoring.py` |
| 9 | AC-9: UC=0, CSI=0 deferred | ✅ | `score_tree.py` | `test_scored_invariants.py` |
| 10 | AC-10: Bitmask AND filtering | ✅ | `(sb & qb) == sb` | `test_score_tree_scoring.py` |
| 11 | AC-11: All 31 conversations | ✅ | E2E | `test_score_tree_integration.py` |
| 12 | AC-12: Output file exists | ✅ | `decision_tree_scored.json` | Integration test |
| 13 | AC-13: Embedding absent, conversation_context present | ✅ | `score_tree.py` | `test_scored_invariants.py` |
| 14 | 12 artifact invariants | ✅ | — | `test_scored_invariants.py` |

### 验证命令输出
test → all pass ✅
integration → pass ✅
invariants → 12/12 pass ✅
