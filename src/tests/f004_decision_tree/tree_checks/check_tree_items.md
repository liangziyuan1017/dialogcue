# Decision Tree Check Items

This document describes every check in `tree_checks/`, the root cause it
guards against, and how it is verified.

## File Layout

| File | Checks | Category |
|------|--------|----------|
| `common.py` | — | shared infrastructure (Report, walkers, helpers) |
| `check_structure.py` | S1–S18 | structure |
| `check_nodes.py` | N1–N22 | node |
| `check_sentences.py` | SE1–SE16 | sentence |
| `check_sentences.py` | T1–T5 | termination |
| `check_gestures.py` | G1–G11 | gesture |
| `check_gestures.py` | C1–C9 | coverage |
| `check_scoring.py` | SC1–SC28 | scoring |
| `check_branching.py` | B1–B13 | branching |
| `check_branching.py` | A1–A8 | additive |
| `check_output.py` | O1–O8 | output |
| `check_output.py` | D1–D5 | per_dialog |

---

## Structure (S1–S18)

### S1 — Root state_id is `initial_contact`
- **Root cause:** The tree root must be the opening contact node. A corrupted
  or mis-built tree may have a wrong root state.
- **How checked:** `tree["state_id"] == "initial_contact"`.

### S2 — Root role is `opening`
- **Root cause:** The root node represents the start of a collection call and
  must have role `opening`.
- **How checked:** `tree["role"] == "opening"`.

### S3 — Exactly one `normal_end` node
- **Root cause:** Multiple or zero normal-end nodes break the assumption that
  all closing sentences converge to a single terminal.
- **How checked:** Count root children with `state_id == "normal_end"`.

### S4 — Exactly one `abrupt_end` node
- **Root cause:** The abrupt-end node is the fallback terminal for dialogs that
  do not reach a closing action. There must be exactly one.
- **How checked:** Count root children with `state_id == "abrupt_end"`.

### S5 — End nodes are direct children of root
- **Root cause:** End nodes nested deeper in the tree would be unreachable as
  global terminals and break leaf linking.
- **How checked:** All `normal_end`/`abrupt_end` nodes appear in
  `root["children"]`.

### S6 — End nodes have `role=ending`
- **Root cause:** End nodes without the `ending` role confuse downstream
  rendering and traversal logic.
- **How checked:** Every end node's `role == "ending"`.

### S7 — All three structural anchors present
- **Root cause:** S1 ∧ S3 ∧ S4 must hold simultaneously.
- **How checked:** Combined assertion of S1, S3, S4.

### S8 — Every leaf is an end node or has ending gesture *(warn)*
- **Root cause:** A leaf that is neither an end node nor has an ending gesture
  is a dangling branch — the dialog path reaches a dead end without proper
  termination.
- **How checked:** Walk all nodes; for leaves (no children), verify
  `is_end(node)` or `sentence_pool` contains an entry with
  `gesture_type == "ending"`.

### S9 — All paths terminate at an end node
- **Root cause:** A path that never reaches `normal_end` or `abrupt_end`
  represents an unterminated dialog branch.
- **How checked:** Recursive descent: every child path must eventually reach
  an end node.

### S10 — No cycles in the tree
- **Root cause:** A cycle (node appearing as its own descendant) causes
  infinite loops in traversal and rendering.
- **How checked:** DFS with a path-id set; if a node id reappears on the
  current path, a cycle is detected.

### S11 — *skip* (same as S10)
### S12 — *skip* (runtime concern)

### S13 — No shared node_ids *(warn)*
- **Root cause:** Multiple nodes with the same `node_id` indicate a DAG share
  or a hash collision. While sharing is sometimes intentional, it can cause
  double-processing.
- **How checked:** Group all nodes by `node_id`; flag groups with >1 member.

### S14 — Single-child ratio < 85%
- **Root cause:** A tree where >85% of non-end, non-root nodes have exactly
  one child is degenerate — it is essentially a linked list, not a branching
  tree.
- **How checked:** Count single-child nodes / total non-end non-root nodes.

### S15 — Max depth *(warn)*
- **How checked:** Report the maximum depth of the tree.

### S16 — Node count *(warn)*
- **How checked:** Report the total number of nodes.

### S17 — DAG shared nodes count *(warn)*
- **How checked:** Report the number of shared node_ids.

### S18 — *skip* (visual concern)

---

## Node (N1–N22)

### N1 — Every non-end node has `node_id`
- **Root cause:** `node_id` is a content hash used for deduplication and
  rendering. Missing it breaks downstream lookups.
- **How checked:** Walk all non-end nodes; verify `"node_id" in node`.

### N2 — Every non-end node has `inherited_facts`
- **Root cause:** `inherited_facts` is populated by `_propagate_facts`. Missing
  it means the propagation step was skipped or the node was added after
  propagation.
- **How checked:** Walk all non-end nodes; verify `"inherited_facts" in node`.

### N3 — Every non-end node has `inherited_emotions`
- **Root cause:** Same as N2 but for emotions.
- **How checked:** Walk all non-end nodes; verify `"inherited_emotions" in node`.

### N4 — Every node role is valid
- **Root cause:** An invalid role (not in `{opening, ending, decision, action}`)
  breaks rendering and traversal assumptions.
- **How checked:** Walk all nodes; verify `role` is in the valid set.

### N5 — *skip* (covered by S2)
### N6 — *skip* (covered by S6)

### N7 — Fact/emotion children have `role=decision`
- **Root cause:** A fact or emotion branch_key on a node without `role=decision`
  violates the tree schema (only decision nodes branch on facts/emotions).
- **How checked:** For every child with `facts` or `emotions` in branch_key,
  verify `role in (None, "decision")`.

### N8 — Action children have `role=action`
- **Root cause:** An action branch_key on a node without `role=action` violates
  the tree schema.
- **How checked:** For every child with `action` in branch_key, verify
  `role in (None, "action")`.

### N9 — No composite branch keys (facts + emotions)
- **Root cause:** A node with both `facts` and `emotions` in its branch_key
  was not properly split by `_split_composite_nodes`. Each node should branch
  on exactly one dimension.
- **How checked:** Walk all nodes; verify no branch_key has both `facts` and
  `emotions`.

### N10 — No multi-fact branch keys
- **Root cause:** A branch_key with `facts: [f1, f2]` was not properly split
  into a chain of single-fact nodes.
- **How checked:** Walk all nodes; verify `len(branch_key["facts"]) <= 1`.

### N11 — Branch keys have exactly one top-level key
- **Root cause:** A branch_key with multiple top-level keys (e.g.
  `{"facts": [...], "action": "..."}`) violates the single-dimension branching
  rule.
- **How checked:** Walk all non-root nodes; verify `len(branch_key) == 1` when
  branch_key is non-empty.

### N12 — No duplicate sibling nodes by identity
- **Root cause:** Two children of the same parent with identical
  `(inherited_facts, inherited_emotions, branch_key)` are redundant duplicates
  that should have been merged by `_deduplicate_nodes`.
- **How checked:** For each parent, compute child identities and detect
  duplicates.

### N13 — *skip* (same as N12)

### N14 — Own fact not in inherited_facts
- **Root cause:** A node that branches on fact `f` where `f` is already in
  `inherited_facts` is a redundant branch — the fact was already accumulated by
  an ancestor.
- **How checked:** For each node, verify `branch_key["facts"]` ∩
  `inherited_facts` = ∅.

### N15 — Own emotion not in inherited_emotions
- **Root cause:** Same as N14 but for emotions.
- **How checked:** For each node, verify `branch_key["emotions"]` ∩
  `inherited_emotions` = ∅.

### N16 — No redundant fact nodes
- **Root cause:** Same as N14, reported per node rather than per fact.
- **How checked:** Same logic as N14, aggregated by node.

### N17 — No redundant emotion nodes
- **Root cause:** Same as N15, reported per node.
- **How checked:** Same logic as N15, aggregated by node.

### N18 — Keywords sorted in branch_key
- **Root cause:** Unsorted fact/emotion lists in branch_key break deterministic
  comparison and rendering.
- **How checked:** For each node, verify `branch_key["facts"]` and
  `branch_key["emotions"]` are sorted.

### N19 — Action nodes have correct state_id and role
- **Root cause:** An action branch_key must have `state_id` starting with `a:`
  and `role == "action"`.
- **How checked:** Walk all nodes with `action` in branch_key; verify state_id
  prefix and role.

### N20 — End nodes have `end_type` in branch_key
- **Root cause:** End nodes without `end_type` in branch_key break end-node
  detection logic.
- **How checked:** Walk all end nodes; verify `"end_type" in branch_key`.

### N21 — *skip* (runtime concern)
### N22 — *skip* (runtime concern)

---

## Sentence (SE1–SE16)

### SE1–SE4 — Required sentence fields
- **Root cause:** Every sentence must have `script_text`, `script_id`,
  `source_call_ids`, and `customer_willingness`. Missing fields break
  rendering and scoring.
- **How checked:** Walk all sentence pools; verify each field is present.

### SE5 — Sentences with `collector_action` have `fact_context`
- **Root cause:** `fact_context` is populated by `_propagate_facts`. A sentence
  with `collector_action` but no `fact_context` indicates the propagation was
  incomplete.
- **How checked:** Walk all sentences; if `collector_action` is set, verify
  `"fact_context" in sentence`.

### SE6 — All sentences have `fact_context` (except end nodes)
- **Root cause:** Same propagation concern as SE5, extended to all sentences.
- **How checked:** Walk all sentences in non-end nodes; verify
  `"fact_context" in sentence`.

### SE7 — Action sentences are under action nodes
- **Root cause:** A sentence with `collector_action` in a non-action node
  indicates misplaced sentences after tree construction.
- **How checked:** Walk all sentences; if `collector_action` is set and the
  parent node is not the root or an end node, verify `"action" in
  parent.branch_key`.

### SE8 — Non-action sentences not in action node pools
- **Root cause:** A sentence without `collector_action` in an action node's
  pool indicates a mixed pool that should have been split.
- **How checked:** Walk all sentences in action nodes; verify
  `collector_action` is set.

### SE9 — `willingness=None` with `collector_action` *(warn)*
- **Root cause:** A sentence with `customer_willingness=None` and a
  `collector_action` may indicate a missing willingness annotation from the
  customer turn preceding the collector action.
- **How checked:** Walk all sentences; flag those with `willingness=None`,
  `collector_action` set, and no `gesture_type`.

### SE10 — No synthetic `other` action
- **Root cause:** The action `"other"` is a synthetic placeholder that should
  not appear in the final tree.
- **How checked:** Walk all sentences; verify `collector_action != "other"`.

### SE11 — *skip* (covered by SE9)

### SE12 — Leaf nodes with empty sentence_pool *(warn)*
- **Root cause:** A leaf node (no children) with an empty sentence_pool is a
  dangling branch. This is the same concern as T1 but as a warning.
- **How checked:** Walk all non-end, non-root leaves; verify sentence_pool is
  non-empty.

### SE13 — No duplicate `script_text` in a node's pool *(warn)*
- **Root cause:** Duplicate sentences in the same node's pool indicate a merge
  or deduplication failure.
- **How checked:** For each node, verify all `script_text` values are unique.

### SE14 — No sentences > 100 chars *(warn)*
- **Root cause:** Overly long sentences may not have been properly split during
  merge, or the merge word limit was not enforced.
- **How checked:** Walk all sentences; flag those with
  `len(script_text) > 100`.

### SE15 — *skip* (runtime concern)
### SE16 — *skip* (runtime concern)

---

## Termination (T1–T5)

### T1 — Exactly 2 end nodes in the entire tree
- **Root cause:** `_link_leaves_to_abrupt_end` used to add the `abrupt_end` dict
  as a child of every leaf node. When serialized to JSON, this created hundreds
  of duplicate `abrupt_end` copies scattered throughout the tree. The fix
  removed leaf linking entirely — leaves are implicitly terminated at
  `abrupt_end`. This check verifies there are exactly 2 end nodes (1
  `normal_end` + 1 `abrupt_end`).
- **How checked:** Walk all nodes; count nodes with `state_id` in
  `("normal_end", "abrupt_end")`. Must equal 2.

### T2 — End nodes have empty sentence_pool
- **Root cause:** `_consolidate_endpoints` used to collect all ending sentences
  (including non-closure actions like `empathy`, `information`,
  `plan_proposal`) into `normal_end`'s sentence_pool. End nodes are terminals
  that mark the end of a dialog path — they should not contain sentences. The
  fix places closing sentences in their proper action nodes and gives end nodes
  empty pools.
- **How checked:** Walk all end nodes; verify `sentence_pool` is empty.

### T3 — End nodes are direct children of root
- **Root cause:** End nodes nested deeper in the tree (as children of action or
  decision nodes) are unreachable as global terminals and pollute the tree
  visualization. This can happen if end nodes are added as children of leaves
  during tree construction.
- **How checked:** Walk all end nodes; verify each is in `root["children"]`.

### T4 — No empty fact/emotion subtrees
- **Root cause:** When customer turns introduce new facts/emotions after the
  last collector action, the tree builder creates fact/emotion nodes with no
  sentences. The entire subtree has no sentences because no collector turn
  follows. These are pruned by `_prune_empty_subtrees`. This check verifies
  the pruning was effective.
- **How checked:** For every non-end, non-root, non-action node with a
  non-empty branch_key, recursively check if the subtree contains any
  sentences. If not, it is a hard fail.

### T5 — No end node children outside root
- **Root cause:** End nodes should only appear as direct children of the root.
  An end node as a child of a non-root node is a stray copy that was not
  cleaned up.
- **How checked:** Walk all non-root, non-end nodes; verify no child is an end
  node.

---

## Gesture (G1–G11)

### G1 — Root pool has opening gesture sentences
- **Root cause:** The root node's sentence_pool should contain greeting
  sentences with `gesture_type == "opening"`.
- **How checked:** Verify root sentence_pool has at least one entry with
  `gesture_type == "opening"`.

### G2 — Root has no `a:greeting` child
- **Root cause:** Greetings should be in the root pool, not as a child action
  node. An `a:greeting` child indicates the greeting was not properly extracted
  to the root.
- **How checked:** Verify no root child has `state_id == "a:greeting"`.

### G3 — Records provided for gesture check
- **How checked:** Verify records argument is not None.

### G4 — `normal_end` has empty sentence_pool
- **Root cause:** End nodes are terminals that mark the end of a dialog path.
  They should not contain sentences. Previously, `_consolidate_endpoints`
  collected all ending sentences into `normal_end`, including non-closure
  actions. The fix gives end nodes empty pools and places closing sentences in
  their proper action nodes.
- **How checked:** Verify `normal_end["sentence_pool"]` is empty.

### G5 — `normal_end` is a pure terminal marker *(pass)*
- **How checked:** Structural pass — `normal_end` has no sentences and no
  children.

### G6 — No ending sentences inside end nodes
- **Root cause:** Ending sentences (with `gesture_type == "ending"`) should
  remain in their action nodes, not be collected into end nodes. This is the
  inverse of the old G6 which checked for ending sentences outside end nodes.
- **How checked:** Walk all sentences; if `gesture_type == "ending"`, verify
  the parent node is NOT an end node.

### G7 — Records provided
- **How checked:** Verify records argument is not None.

### G8 — *skip* (needs records)
### G9 — Structural: greetings in root pool at insert *(pass)*
### G10 — Structural: closings in normal_end at insert *(pass)*
### G11 — *skip* (runtime concern)

---

## Coverage (C1–C9)

### C1 — All call_ids from data are in tree
- **Root cause:** A call_id present in the rewarded records but not in the tree
  indicates a dialog that was not added to the tree.
- **How checked:** Compute the set of call_ids from records and from tree
  sentences; verify no missing call_ids.

### C2 — All facts from data are in tree *(warn)*
- **Root cause:** A fact present in the records but not in any tree node's
  branch_key or inherited_facts indicates a fact that was not branched on.
- **How checked:** Compute fact sets from records and tree; report missing.

### C3 — All emotions from data are in tree *(warn)*
- **Root cause:** Same as C2 but for emotions.
- **How checked:** Compute emotion sets from records and tree; report missing.

### C4 — Empty-pool branch nodes allowed *(pass)*
### C5 — *skip* (runtime concern)
### C6 — *skip* (needs scored tree)
### C7–C9 — Counts *(warn)*

---

## Scoring (SC1–SC28)

### SC1 — `bg_constraints` has correct keys
- **Root cause:** The background constraints dict must have exactly the 10
  bitmask keys. Wrong keys indicate a schema change in the scoring pipeline.
- **How checked:** For each scored sentence, verify
  `set(bg_constraints.keys()) == BITMASK_KEYS`.

### SC2 — `bg_bitmask` has correct keys
- **How checked:** Same as SC1 but for `bg_bitmask`.

### SC3 — `bg_bitmask_int` in [0, 1023]
- **Root cause:** The bitmask integer encodes 10 boolean flags, so it must be
  in [0, 1023].
- **How checked:** Verify `0 <= bg_bitmask_int <= 1023`.

### SC4 — `bg_bitmask_int` matches encoding
- **Root cause:** The integer must be the bitwise encoding of `bg_bitmask`.
- **How checked:** Recompute the expected integer from `bg_bitmask` and
  compare.

### SC5 — *skip* (covered by SC4)
### SC6 — Multi-source sentences have bg_constraints *(warn)*

### SC7 — `win_rate` in [0, 1]
- **How checked:** Verify `0 <= win_rate <= 1`.

### SC8 — `win_rate` matches blend formula *(warn)*
- **Root cause:** `win_rate` should equal
  `weight * sentence_hwr + (1 - weight) * node_hwr` where
  `weight = n / (n + 2)`.
- **How checked:** Recompute the expected value and compare.

### SC9 — `win_rate_node` in [0, 1]
### SC10 — `win_rate_node` present
### SC11–SC14 — *skip* (covered by SC8)
### SC15 — `sas` in [0, 1]
### SC16–SC18 — *skip* (runtime computation)
### SC19 — `uplift_score == 0`
### SC20 — `csi == 0`
### SC21 — `deferred == True`
### SC22 — No embedding in JSON
- **Root cause:** Embeddings should be stored in the DB, not in the JSON file.
- **How checked:** Walk all sentences; verify `"embedding" not in sentence`.

### SC23 — `conversation_context` present
### SC24 — *skip* (DB-only)
### SC25 — `bg_background` is a dict with 10 fields
- **Root cause:** `bg_background` must contain digit-count, int, and passthrough fields derived from context_lookup (not customer_info_lookup). Missing or extra keys indicate a schema change.
- **How checked:** Walk all scored sentences; verify `bg_background` is a dict with the expected keys (business_loan_digits, mortgage_balance_digits, other_loan_digits, wealth_digits, current_balance_digits, education, days_delinquent, recent_contact_count, risk_level, complaint_score).

### SC26 — No numeric fields in bitmask
- **Root cause:** Numeric fields (balances, counts, scores) belong in `bg_background`, not `bg_constraints`. Their presence in bg_constraints would break bitmask encoding.
### SC27 — *skip* (covered by SC4+SC5)
### SC28 — *skip* (runtime concern)

---

## Branching (B1–B13)

### B1 — No `willingness` in branch_key
- **Root cause:** `willingness` is a customer attribute, not a branching
  dimension. Its presence in branch_key indicates a schema violation.
- **How checked:** Walk all nodes; verify `"willingness" not in branch_key`.

### B2–B9 — *skip* (covered by N9/N10, B1, or runtime)

### B10 — Action nodes are under decision nodes
- **Root cause:** An action child of a non-decision node (not the root)
  indicates a misplaced action node.
- **How checked:** For every action child, verify the parent has `facts` or
  `emotions` in its branch_key (or is the root).

### B11 — *skip* (covered by N16)
### B12 — *skip* (covered by N17)
### B13 — *skip* (runtime concern)

---

## Additive (A1–A8)

### A1 — *skip* (covered by N9)
### A2 — *skip* (covered by N9/N10)
### A3 — merge validity *(pass)*

### A4 — No duplicate script_ids per call_id *(warn)*
- **Root cause:** Two sentences with the same `script_id` from the same
  `call_id` indicate a merge or deduplication failure.
- **How checked:** Group sentences by call_id; detect duplicate script_ids.

### A5 — *skip* (covered by N12)
### A6 — *skip* (runtime concern)
### A7 — Base structure *(pass)*
### A8 — *skip* (runtime concern)

---

## Output (O1–O8)

### O1 — `decision_tree.json` loaded
### O2 — `decision_tree_scored.json` loaded

### O3 — Node set matches between base and scored tree
- **Root cause:** The scored tree should have the same nodes as the base tree.
  A mismatch indicates the scored tree is stale.
- **How checked:** Compare `state_id` sets between both trees.

### O4 — Scored sentences have all scoring fields
- **How checked:** Verify each scored sentence has all fields in
  `scored_fields`.

### O5–O8 — *skip* (DB-only)

---

## Per-Dialog (D1–D5)

### D1 — No duplicate facts in a dialog's path *(warn)*
- **Root cause:** A dialog that passes through the same fact branch twice
  indicates a redundant branching or a cycle.
- **How checked:** Trace each call_id's path through the tree; verify no
  duplicate facts in the path.

### D2 — No duplicate emotions in a dialog's path *(warn)*
- **How checked:** Same as D1 but for emotions.

### D3 — Dialogs reach an end node *(warn)*
- **Root cause:** A dialog whose path does not terminate at an end node
  indicates an incomplete tree path.
- **How checked:** For each dialog, verify the last node in its path is an end
  node or has an end node child.

### D4 — No duplicate script_ids *(warn)*
- **How checked:** Collect all script_ids; verify no duplicates.

### D5 — No duplicate nodes by identity *(warn)*
- **How checked:** Walk all nodes; detect duplicate identities.
