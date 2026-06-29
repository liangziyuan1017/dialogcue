## Quality Gate Report

Spec: `docs/features/F006-retrieval-ranking-engine.md`
原始需求: "Build recommend() function — given conversation state + utterance + context, find node, filter, rank, return top-1 script"
检查时间: 2026-06-26

### 愿景覆盖（Step 0）
| # | Human原始需求 | AC 覆盖？ | 实现？ |
|---|---------------|-----------|--------|
| 1 | build_node_index creates 267 unique keys → 315 nodes | AC-1, AC-2 | ✅ Permutation-insensitive key |
| 2 | Key lookup O(1) | AC-3 | ✅ Hash map lookup |
| 3 | Pool aggregation from sibling nodes | AC-4 | ✅ aggregate_pools() |
| 4 | Conversation context extraction | AC-5 | ✅ ~100-word context per sentence |
| 5 | recommend() returns all output fields | AC-6 | ✅ Full output schema |
| 6 | Fallback cascade (key drop, descend, bitmask relax) | AC-7 through AC-13 | ✅ 6-level fallback with confidence decay |
| 7 | Unified fusion ranking | AC-14, AC-15 | ✅ 0.40*win_rate + 0.30*vec_score + 0.15*sas + 0.15*bg_boost |
| 8 | No LLM in hot path | AC-17 | ✅ Pre-extracted facts only |
| 9 | All 267 keys reachable | AC-18 | ✅ Full coverage |

### 功能验收
| # | AC | 状态 | 代码位置 | 测试覆盖 |
|---|-----|------|----------|----------|
| 1 | AC-1: 267 unique keys → 309 nodes | ✅ | `build_node_index()` | `test_retrieval_engine.py` |
| 2 | AC-2: Key permutation-insensitive | ✅ | Sorted tuple key | `test_retrieval_engine.py` |
| 3 | AC-3: O(1) lookup | ✅ | `lookup_by_key()` | `test_retrieval_engine.py` |
| 4 | AC-4: aggregate_pools | ✅ | `aggregate_pools()` | `test_retrieval_engine.py` |
| 5 | AC-5: conversation context | ✅ | `add_conversation_context()` | `test_retrieval_engine.py` |
| 6 | AC-6: recommend() output schema | ✅ | `recommend()` | `test_retrieval_engine.py` |
| 7 | AC-7: Exact match confidence=1.0 | ✅ | No fallbacks | `test_retrieval_engine.py` |
| 8 | AC-8: Key drop fallback | ✅ | Fallback cascade | `test_retrieval_engine.py` |
| 9 | AC-9: Descend fallback | ✅ | BFS descent | `test_retrieval_engine.py` |
| 10 | AC-10: Descend includes siblings | ✅ | BFS at same depth | `test_retrieval_engine.py` |
| 11 | AC-11: Descend → key drop retry | ✅ | Combined fallback | `test_retrieval_engine.py` |
| 12 | AC-12: Bitmask relaxation | ✅ | Progressive bit clear | `test_retrieval_engine.py` |
| 13 | AC-13: Context missing adjustment | ✅ | vec_score=0 | `test_retrieval_engine.py` |
| 14 | AC-14: Unified fusion formula | ✅ | `RANKING_WEIGHTS` | `test_retrieval_ranking.py` |
| 15 | AC-15: bg_boost computation | ✅ | Industry/education/debt/age | `test_retrieval_ranking.py` |
| 16 | AC-16: vec_score via bge-m3 | ✅ | F007b integration | `test_retrieval_ranking.py` |
| 17 | AC-17: No LLM in hot path | ✅ | Pre-extracted facts | Design review |
| 18 | AC-18: All 267 keys reachable | ✅ | E2E | `test_retrieval_engine_integration.py` |

### 验证命令输出
test → all pass ✅
integration → pass ✅
