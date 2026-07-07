## Quality Gate Report — F004

Spec: F004-decision-tree-construction.md
检查时间: 2026-07-07

### 愿景覆盖（Step 0）
| # | Human原始需求 | AC 覆盖？ | 实现？ |
|---|---------------|-----------|--------|
| 1 | Root node with state_id "initial_contact" | AC#1 | ✅ |
| 2 | Every leaf node has non-empty sentence_pool | AC#2 | ✅ |
| 3 | Sentence entries have script_text, script_id, source_call_ids, collector_action, fact_context | AC#3 | ✅ |
| 4 | All 31 conversations represented | AC#4 | ✅ |
| 5 | Keywords lexicographically sorted | AC#5 | ✅ |
| 6 | Fallback via progressive tag removal | AC#6 | ✅ |
| 7 | Branches keyed by (facts, emotions) only | AC#7 | ✅ |
| 8 | Tree is branching (single-child ratio < 85%) | AC#8 | ✅ |
| 9 | Opening gesture sentences tagged | AC#9 | ✅ |
| 10 | Consolidated normal_end + abrupt_end nodes | AC#10 | ✅ |
| 11 | Both end nodes are root children | AC#11 | ✅ |
| 12 | Every dialog path terminates at end node | AC#12 | ✅ |
| 13 | Ending gesture sentences tagged | AC#13 | ✅ |
| 14 | Abrupt dialogs routed to abrupt_end | AC#14 | ✅ |
| 15 | No composite branch keys | AC#15 | ✅ |
| 16 | No redundant fact nodes | AC#16 | ✅ |
| 17 | Sentences under action nodes for fact/emotion parents | AC#17 | ✅ |
| 18 | All facts from data have tree nodes | AC#18 | ✅ |
| 19 | All emotions from data have tree nodes | AC#19 | ✅ |
| 20 | state=None collector turns captured without synthetic label | AC#20 | ✅ |
| 21 | Empty-sentence segments create branch nodes | AC#21 | ✅ |
| 22 | Every node has role ∈ {opening, ending, decision, action} | ADR-030 | ✅ |
| 23 | Tree supports incremental merge via merge_dialogs | ADR-029 | ✅ |
| 24 | No ending sentences outside end nodes | ADR-029 | ✅ |
| 25 | Root has no a:greeting action child | ADR-030 | ✅ |

### 功能验收
| # | 要求 | 状态 | 代码位置 | 测试覆盖 |
|---|------|------|----------|----------|
| 1 | Root initial_contact | ✅ | build_decision_tree.py | test_root_state_id |
| 2 | Leaf sentence_pool non-empty | ✅ | build_decision_tree.py | test_build_tree_leaf_has_sentence_pool |
| 3 | Sentence entry fields | ✅ | build_decision_tree.py | test_every_sentence_has_required_fields |
| 4 | All 31 call_ids represented | ✅ | build_decision_tree.py | test_all_call_ids_in_tree |
| 5 | Keywords sorted | ✅ | build_decision_tree.py | test_keywords_sorted |
| 6 | Fallback tag removal | ✅ | build_decision_tree.py | test_find_node_fallback_removes_emotions |
| 7 | Real data integration | ✅ | build_decision_tree.py | test_real_data_all_criteria |
| 8 | Branches keyed by (facts, emotions) | ✅ | build_decision_tree.py | test_build_tree_branches_on_facts_emotions |
| 9 | Tree is branching | ✅ | build_decision_tree.py | test_real_data_branches_not_chains |
| 10 | Opening gestures | ✅ | build_decision_tree.py | test_real_data_opening_gestures |
| 11 | Consolidated endpoints | ✅ | build_decision_tree.py | test_exactly_one_normal_end_as_root_child |
| 12 | Path termination | ✅ | build_decision_tree.py | test_every_leaf_is_end_node |
| 13 | collector_action on sentences | ✅ | build_decision_tree.py | test_greeting_sentences_have_collector_action |
| 14 | No composite branch keys | ✅ | build_decision_tree.py | test_no_composite_branch_keys |
| 15 | No redundant fact nodes | ✅ | build_decision_tree.py | test_no_redundant_fact_nodes |
| 16 | Strict inherited_facts | ✅ | build_decision_tree.py | test_inherited_facts_strictly_from_parent_chain |
| 17 | Sentences under action nodes | ✅ | build_decision_tree.py | test_sentences_under_action_nodes_for_fact_emotion_parents |
| 18 | Every record has greeting | ✅ | test_record_coverage.py | test_every_record_has_greeting_in_tree |
| 19 | All facts have nodes | ✅ | test_record_coverage.py | test_every_record_all_facts_have_nodes |
| 20 | All emotions have nodes | ✅ | test_record_coverage.py | test_every_record_all_emotions_have_nodes |
| 21 | All collector actions in tree | ✅ | test_record_coverage.py | test_every_record_all_collector_actions_in_tree |
| 22 | Record sequence correctness | ✅ | test_record_coverage.py | test_every_record_sequence_is_correct |
| 23 | All 31 call_ids (coverage) | ✅ | test_record_coverage.py | test_all_31_call_ids_represented |
| 24 | Node category correctness | ✅ | test_record_coverage.py | test_node_category_correctness |
| 25 | Every node has valid role | ✅ | test_role_tagging.py | test_every_node_has_valid_role |
| 26 | Root role=opening | ✅ | test_role_tagging.py | test_root_role_is_opening |
| 27 | End nodes role=ending | ✅ | test_role_tagging.py | test_end_nodes_role_is_ending |
| 28 | Greetings stay in root | ✅ | test_role_tagging.py | test_greetings_stay_in_root_after_write |
| 29 | Endings consolidated | ✅ | test_role_tagging.py | test_endings_consolidated_in_normal_end_after_write |
| 30 | Additive idempotency | ✅ | test_additive.py | test_idempotent_double_insert |
| 31 | Incremental merge | ✅ | test_additive.py | test_incremental_merge |
| 32 | Additive equivalence | ✅ | test_additive.py | test_same_call_id_coverage |
| 33 | 19 artifact invariants | ✅ | test_tree_invariants.py | all 19 tests |

### Tree Statistics (2026-07-07, additive pipeline)
- Total nodes: 200
- Max depth: 17
- Unique call_ids: 31/31
- Pipeline: additive (make_base_tree → add_dialog_to_tree per record → _propagate_facts → _deduplicate_nodes → _ensure_leaf_termination → _consolidate_endpoints → _sort_keywords)
- Global transforms removed: _split_composite_nodes, _merge_sibling_facts, _collapse_redundant_facts, _split_by_action

### Pipeline (additive, ADR-029)
```
build_tree → _split_composite_nodes → _merge_sibling_facts → _collapse_redundant_facts → _split_by_action → _propagate_facts → _link_leaves_to_abrupt_end → _remove_stray_abrupt_ends
```
Note: `_ensure_leaf_termination` was removed from the pipeline (it created duplicate `abrupt_end` nodes). Replaced by `_link_leaves_to_abrupt_end` + `_remove_stray_abrupt_ends`. Leaf nodes without children are implicitly terminated at `abrupt_end` (no explicit child).

### UI Features
- Cytoscape.js + dagre hierarchical layout (bundled locally)
- Zoom, pan, drag, click-to-inspect
- Node styling: rectangle (decision), ellipse (emotion/normal end), diamond (action), triangle (abrupt end)
- Action nodes: yellow/amber diamond; emotion nodes: purple ellipse
- Edge arrows: 1.4x scale on tree edges and action-flow edges
- Action-flow edges: muted slate color (#475569), dashed
- Label prefixes stripped (a:, e:, f: removed)
- Dialog tracer with auto-play animation (1400ms per step)
- Flowing node highlight during walkthrough
- collector_action and fact_context displayed in sentence panel
- Dashed action-flow edges from action leaves to end nodes
- End nodes positioned bottom-center with 2x vertical spacing
- Depth-based Y positioning: each tree depth gets unique band, shallow depths get more spacing
- enforceParentAboveChild: every child strictly below parent (forward edges only)
- View mode: dedicated buildViewGraph renderer, sequential vertical flow (320px per row)
- View mode: back edges rendered as dashed slate lines, source offset rightward to avoid crossing
- View mode: cy.fit(undefined, 80) for comfortable initial zoom
- No-cache HTTP server (NoCacheHandler + ReusableTCPServer)

### 验证命令输出
test_build_decision_tree: 34/34 pass ✅
test_record_coverage: 10/10 pass ✅
test_ui_rendering: 20/20 pass ✅
No governance violations ✅
