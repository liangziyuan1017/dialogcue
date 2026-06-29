# Detailed Description of the Decision Tree

## 1. What It Is

This is a **domain-specific N-ary state-transition decision tree** for ICBC credit card debt collection. It is **not** a classic CS tree (not BST, AVL, Red-Black, B-tree, trie, or segment tree). It has no balancing, no ordering invariant, and no left/right pointers.

Each node represents a **customer dialog state** keyed by a composite `(facts, emotions)` branch key. Each node stores a **sentence pool** — the set of collector scripts that were used at that state across all conversations. The tree encodes the flow of conversations: root → first customer state → next state → ... → terminal.

## 2. Global Structure

| Metric | Value |
|--------|-------|
| Total nodes | **60** |
| Leaf nodes | 28 |
| Internal nodes | 32 |
| Max depth | **13** |
| Max branching factor | **22** (at root) |
| Total sentences across all pools | 320 |
| Unique source conversations | 31 |

### Depth Distribution

```
depth  0:   1 node   (root)
depth  1:  22 nodes  (all first customer states)
depth  2:  12 nodes
depth  3:   4 nodes
depth  4:   5 nodes
depth  5:   2 nodes
depth  6:   2 nodes
depth  7:   3 nodes
depth  8:   1 node
depth  9:   3 nodes
depth 10:   2 nodes
depth 11:   1 node
depth 12:   1 node
depth 13:   1 node   (deepest leaf)
```

The tree is **heavily right-skewed** — 22 of 32 internal nodes have exactly 1 child (81.2% chain ratio). The root fans out to 22 children, but most branches quickly collapse into linear chains. Only 5 internal nodes branch to 2+ children.

### Branching Factor Histogram

| Children | Nodes |
|----------|-------|
| 0 (leaves) | 28 |
| 1 (chain) | 26 |
| 2 | 4 |
| 3 | 1 |
| 22 | 1 (root) |

## 3. The Root Node

`initial_contact` is the root. Its sentence pool is the **largest in the tree** with **106 sentences** contributed by **all 31 conversations**. This is where every dialog begins — it contains every greeting and every first-response script ever used:

| Action | Count | Role |
|--------|-------|------|
| greeting | 24 | Opening scripts |
| pressure | 24 | Initial pressure tactics |
| information | 21 | Informational responses |
| plan_proposal | 16 | Early plan offers |
| closure | 11 | Quick closures |
| legal_threat | 6 | Legal escalation scripts |
| empathy | 4 | Empathetic openings |

## 4. Branch Key Architecture

Each non-terminal node is identified by a composite key `{facts: [...], emotions: [...]}`. The key type distribution:

| Key Type | Nodes | Share |
|----------|-------|-------|
| **Fact-only** | 28 | 47% |
| **Emotion-only** | 19 | 32% |
| **Combined (facts + emotions)** | 10 | 17% |
| **Empty (root + terminals)** | 3 | 5% |

The tree is **fact-dominant** — nearly half the nodes branch on factual circumstances alone (financial_hardship, bankruptcy, wage_garnishment, etc.). Emotion-only nodes tend to appear deeper in the tree, capturing emotional shifts within an already-established factual context.

### All 41 Fact Keywords (by frequency)

| Keyword | Frequency | Description |
|---------|-----------|-------------|
| financial_hardship | 9 | Most common fact — appears in 9 nodes |
| request_installment | 3 | Customer requesting payment plan |
| ability_to_pay | 3 | Customer claims ability to pay |
| external_debt_uncollected | 2 | Other banks' uncollected debts |
| multiple_debts | 2 | Customer has multiple obligations |
| prior_contact_attempt | 2 | Previous collection attempts |
| income_statement | 1 | Customer provides income documentation |
| payment_history | 1 | Reference to payment track record |
| other_bank_policy | 1 | Cites another bank's policy |
| salary_delay | 1 | Salary payment delayed |
| bankruptcy | 1 | Customer declares bankruptcy |
| self_employed | 1 | Self-employed status |
| previous_offer | 1 | References prior repayment offer |
| repayment_intent | 1 | Expresses intent to repay |
| other_bank_refund | 1 | Refund from another bank |
| income_timing | 1 | Timing of income receipt |
| bank_account_frozen | 1 | Account is frozen |
| legal_procedure_pending | 1 | Legal action in progress |
| legal_resolution | 1 | Legal matter resolved |
| debt_priority | 1 | Prioritizing which debt to pay |
| billing_dispute | 1 | Disputes the bill |
| family_illness | 1 | Family member is ill |
| promise_date | 1 | Promises payment by a date |
| acknowledge_debt | 1 | Acknowledges the debt |
| wage_garnishment | 1 | Wages being garnished |
| illness | 1 | Customer is ill |
| negotiating_with_others | 1 | Negotiating with other creditors |
| collection_effort | 1 | Collection activity reference |
| debtor_delay | 1 | Debtor causing delays |
| external_debt | 1 | Debt with external parties |
| urgency | 1 | Urgency of situation |
| interest_accumulation | 1 | Interest accruing |
| repayment_capacity | 1 | Capacity to repay |
| special_circumstance | 1 | Special circumstances claimed |
| account_frozen | 1 | Account frozen |
| unresolved_issue | 1 | Unresolved matter |
| missed_contact_explanation | 1 | Explains missed contact |
| debt_amount | 1 | References debt amount |
| previous_agreement | 1 | Prior agreement exists |
| unemployment | 1 | Customer is unemployed |
| unemployment_duration | 1 | Duration of unemployment |

### All 23 Emotion Keywords (by frequency)

| Keyword | Frequency | Description |
|---------|-----------|-------------|
| frustration | 4 | Most common emotion |
| anger | 2 | |
| skepticism | 2 | |
| anxiety | 2 | |
| defensive | 2 | |
| disappointment | 1 | |
| difficulty | 1 | |
| distress | 1 | |
| confusion | 1 | |
| agreement | 1 | |
| pleading | 1 | |
| exhaustion | 1 | |
| defensiveness | 1 | |
| rejection | 1 | |
| stress | 1 | |
| threat | 1 | |
| insistence | 1 | |
| accusation | 1 | |
| impatience | 1 | |
| urgency | 1 | |
| hesitation | 1 | |
| helplessness | 1 | |
| relief | 1 | |

### All 57 Unique Branch Key Combinations

Every branch key combination is unique (no duplicates) — the deduplication ensures that identical `(facts, emotions)` states always map to the same node. Examples of the most complex composite keys:

- `f:ability_to_pay,financial_hardship,income_statement,payment_history | e:difficulty` — 4 facts + 1 emotion
- `f:collection_effort,debtor_delay,external_debt,urgency | e:anxiety` — 4 facts + 1 emotion
- `f:external_debt_uncollected,financial_hardship,negotiating_with_others | e:anxiety` — 3 facts + 1 emotion
- `f:financial_hardship,interest_accumulation,repayment_capacity | e:frustration` — 3 facts + 1 emotion

Full list of all 57 branch keys:

```
e:accusation
e:agreement
e:anger
e:anger,skepticism
e:confusion
e:defensiveness
e:disappointment
e:distress
e:exhaustion
e:hesitation
e:impatience
e:insistence
e:pleading
e:rejection
e:relief
e:skepticism
e:stress
e:threat
e:urgency
empty (root/terminals)
f:ability_to_pay,financial_hardship
f:ability_to_pay,financial_hardship,income_statement,payment_history|e:difficulty
f:ability_to_pay,financial_hardship,request_installment
f:account_frozen
f:acknowledge_debt
f:bank_account_frozen
f:bankruptcy
f:billing_dispute
f:collection_effort,debtor_delay,external_debt,urgency|e:anxiety
f:debt_amount
f:debt_priority
f:external_debt_uncollected
f:external_debt_uncollected,financial_hardship,negotiating_with_others|e:anxiety
f:family_illness
f:financial_hardship
f:financial_hardship,interest_accumulation,repayment_capacity|e:frustration
f:financial_hardship,multiple_debts
f:financial_hardship,prior_contact_attempt,unresolved_issue|e:frustration
f:financial_hardship|e:helplessness
f:illness
f:income_timing
f:legal_procedure_pending,legal_resolution|e:frustration
f:missed_contact_explanation,prior_contact_attempt|e:defensive
f:multiple_debts
f:other_bank_policy
f:other_bank_refund
f:previous_agreement
f:previous_offer
f:promise_date
f:repayment_intent
f:request_installment
f:request_installment|e:frustration
f:salary_delay
f:self_employed
f:special_circumstance|e:defensive
f:unemployment
f:unemployment_duration
f:wage_garnishment
```

## 5. Terminal Nodes

The tree has exactly **2 terminal nodes** as direct children of the root (created by `_consolidate_endpoints`):

### `normal_end`
- **54 sentences** from **14 conversations** — these are all the closing/goodbye scripts collected from dialogs that ended properly
- Action breakdown: closure (22), pressure (12), information (7), empathy (7), plan_proposal (5), legal_threat (1)

### `abrupt_end`
- **1 sentence**: `[对话未正常结束]` — a marker for conversations that terminated without a proper closing gesture

All original terminal nodes throughout the tree were stripped during consolidation, their ending sentences harvested into `normal_end`, and unterminated leaves were given an `abrupt_end` child before consolidation.

## 6. Globally Deduplicated Nodes (Cross-Conversation Merging)

These are nodes where **different conversations produced the same customer state**, so their sentence pools were merged. This is the core value of the tree — it reveals which states are shared across conversations:

| Node | Pool Size | Contributing Calls | Interpretation |
|------|-----------|-------------------|----------------|
| `initial_contact` | 106 | 31 calls (all) | Every conversation starts here |
| `normal_end` | 54 | 14 calls | 45% of conversations share closing states |
| `f:financial_hardship` | 23 | 6 calls | Financial hardship is a common mid-dialog state |
| `f:financial_hardship\|e:helplessness` | 10 | 2 calls | Helplessness + hardship is a recognizable pattern |
| `f:salary_delay` | 8 | 2 calls | Salary delay triggers similar scripts |
| `e:confusion` | 7 | 2 calls | Confused customers get similar responses |
| `e:skepticism` | 6 | 2 calls | Skeptical customers share scripts |
| `e:pleading` | 4 | 3 calls | Pleading appears in 3 different conversations |
| `f:financial_hardship,multiple_debts` | 5 | 3 calls | Multi-debt hardship is a shared state |
| `e:anger` | 2 | 2 calls | Anger appears in 2 conversations |
| `f:multiple_debts` | 2 | 2 calls | Multiple debts referenced in 2 conversations |

## 7. Longest Paths (Deepest Dialog Flows)

### Path 1 — Depth 13 (the deepest)
```
initial_contact
 → f:request_installment
 → e:disappointment
 → f:ability_to_pay,financial_hardship,income_statement,payment_history|e:difficulty
 → e:distress
 → f:request_installment|e:frustration
 → f:ability_to_pay,financial_hardship,request_installment
 → f:ability_to_pay,financial_hardship
 → e:confusion
 → e:pleading
 → f:salary_delay
 → e:anger
 → e:anger,skepticism
 → e:exhaustion
```
This path traces a customer who: requests installment → expresses disappointment → reveals financial details with difficulty → becomes distressed → gets frustrated about installment → confusion → pleading → cites salary delay → anger → anger+skepticism → exhaustion. A 14-state emotional escalation.

### Path 2 — Depth 10
Same as Path 1 but branches at `e:pleading` → `f:other_bank_policy` (customer cites other bank's policy instead of salary delay).

### Path 3 — Depth 9
Same as Path 1 but branches at `e:confusion` → `e:agreement` (customer agrees instead of pleading).

### Path 4 — Depth 9
Same as Path 1 but branches at `e:confusion` → `e:defensiveness` (customer becomes defensive instead of pleading).

### Path 5 — Depth 7
```
initial_contact
 → f:financial_hardship,multiple_debts
 → f:repayment_intent
 → f:multiple_debts
 → e:rejection
 → e:stress
 → e:skepticism
 → e:threat
```
A customer with financial hardship + multiple debts who expresses intent to repay but then rejects → stress → skepticism → threats.

## 8. Full Tree Topology

```
initial_contact [106 sentences: greeting×24, pressure×24, information×21, plan_proposal×16, closure×11, empathy×4, legal_threat×6]
 ├── f:request_installment [1: information]
 │   └── e:disappointment [1: plan_proposal]
 │       └── f:ability_to_pay,financial_hardship,income_statement,payment_history|e:difficulty [1: empathy]
 │           └── e:distress [1: pressure]
 │               └── f:request_installment|e:frustration [1: plan_proposal]
 │                   └── f:ability_to_pay,financial_hardship,request_installment [1: pressure]
 │                       └── f:ability_to_pay,financial_hardship [6: plan_proposal×2, information×4]
 │                           └── e:confusion [7: plan_proposal×1, information×6]
 │                               ├── e:agreement [1: empathy]
 │                               ├── e:pleading [4: pressure×1, empathy×1, plan_proposal×2]
 │                               │   ├── f:other_bank_policy [1: pressure]
 │                               │   └── f:salary_delay [8: plan_proposal×3, empathy×1, information×2, pressure×2]
 │                               │       └── e:anger [2: legal_threat×1, information×1]
 │                               │           └── e:anger,skepticism [1: pressure]
 │                               │               └── e:exhaustion [1: pressure]
 │                               └── e:defensiveness [2: information×2]
 ├── f:bankruptcy [6: empathy×2, information×2, plan_proposal×2]
 │   └── f:self_employed [5: empathy×2, plan_proposal×3]
 │       └── f:financial_hardship [23: pressure×2, empathy×12, closure×4, plan_proposal×3, information×2]
 │           ├── f:previous_offer [3: pressure×1, plan_proposal×1, information×1]
 │           └── f:external_debt_uncollected [2: information×1, plan_proposal×1]
 ├── f:financial_hardship,multiple_debts [5: information×2, plan_proposal×2, empathy×1]
 │   ├── f:repayment_intent [1: plan_proposal]
 │   │   └── f:multiple_debts [2: plan_proposal×1, information×1]
 │   │       └── e:rejection [1: plan_proposal]
 │   │           └── e:stress [1: plan_proposal]
 │   │               └── e:skepticism [6: plan_proposal×2, pressure×3, information×1]
 │   │                   ├── e:threat [6: pressure×2, plan_proposal×4]
 │   │                   └── f:other_bank_refund [2: plan_proposal×2]
 │   └── f:income_timing [1: plan_proposal]
 ├── e:insistence [1: pressure]
 │   └── e:accusation [1: information]
 ├── f:bank_account_frozen [2: empathy×2]
 │   └── f:legal_procedure_pending,legal_resolution|e:frustration [2: empathy×1, plan_proposal×1]
 ├── f:debt_priority [1: plan_proposal]
 ├── f:billing_dispute [4: information×4]
 │   └── e:impatience [1: information]
 ├── e:urgency [1: plan_proposal]
 │   └── f:family_illness [3: information×1, plan_proposal×2]
 ├── f:promise_date [1: empathy]
 ├── f:acknowledge_debt [1: information]
 ├── e:hesitation [1: pressure]
 ├── f:wage_garnishment [6: plan_proposal×3, pressure×1, information×2]
 ├── f:illness [1: legal_threat]
 ├── f:external_debt_uncollected,financial_hardship,negotiating_with_others|e:anxiety [3: empathy×1, plan_proposal×1, information×1]
 │   └── f:collection_effort,debtor_delay,external_debt,urgency|e:anxiety [1: plan_proposal]
 │       └── f:financial_hardship,interest_accumulation,repayment_capacity|e:frustration [2: information×1, pressure×1]
 │           └── f:special_circumstance|e:defensive [1: plan_proposal]
 ├── f:financial_hardship|e:helplessness [10: plan_proposal×4, empathy×1, pressure×3, information×2]
 ├── f:account_frozen [1: plan_proposal]
 ├── f:financial_hardship,prior_contact_attempt,unresolved_issue|e:frustration [3: information×3]
 │   └── f:missed_contact_explanation,prior_contact_attempt|e:defensive [2: information×1, plan_proposal×1]
 ├── f:debt_amount [1: closure]
 ├── e:relief [2: pressure×1, information×1]
 │   └── f:previous_agreement [2: information×2]
 ├── f:unemployment [1: empathy]
 │   └── f:unemployment_duration [1: pressure]
 ├── normal_end [54: closure×22, pressure×12, information×7, empathy×7, plan_proposal×5, legal_threat×1]
 └── abrupt_end [1: marker]
```

## 9. Sentence Pool Distribution

| Metric | Value |
|--------|-------|
| Min pool size | 1 (most nodes) |
| Max pool size | 106 (root) |
| Average pool size | 5.3 |
| Total sentences | 320 |

### Top 10 Nodes by Pool Size

| Node | Sentences | Why Large |
|------|-----------|-----------|
| `initial_contact` | 106 | All 31 conversations contribute greetings + first responses |
| `normal_end` | 54 | All closing scripts from 14 completed conversations |
| `f:financial_hardship` | 23 | 6 conversations hit this state; empathy-heavy (12/23) |
| `f:financial_hardship\|e:helplessness` | 10 | 2 conversations; plan_proposal-heavy (4/10) |
| `f:salary_delay` | 8 | 2 conversations; mixed plan_proposal/empathy/information |
| `e:confusion` | 7 | 2 conversations; information-heavy (6/7) |
| `f:ability_to_pay,financial_hardship` | 6 | information-heavy (4/6) |
| `f:bankruptcy` | 6 | 1 conversation; balanced empathy/info/plan |
| `e:skepticism` | 6 | 2 conversations; pressure-heavy (3/6) |
| `e:threat` | 6 | 1 conversation; plan_proposal-heavy (4/6) |

## 10. Collector Action Distribution (All 320 Sentences)

| Action | Count | Share | When Used |
|--------|-------|-------|-----------|
| information | 75 | 23% | Explaining policies, amounts, options |
| plan_proposal | 73 | 23% | Offering installment plans, repayment schedules |
| pressure | 61 | 19% | Urging payment, deadlines, consequences |
| empathy | 39 | 12% | Acknowledging difficulty, showing understanding |
| closure | 38 | 12% | Confirming agreement, wrapping up |
| greeting | 24 | 8% | Opening the call |
| legal_threat | 9 | 3% | Warning about legal action |

## 11. Customer Willingness Distribution

| Willingness | Count | Share |
|-------------|-------|-------|
| conditional | 82 | 39% |
| weak | 62 | 30% |
| negotiating | 32 | 15% |
| resistant | 22 | 11% |
| strong | 14 | 7% |

Most customers are **conditional** or **weak** — they'll pay under certain conditions or with reluctance. Only 7% show strong willingness.

## 12. How the Tree Is Built (Algorithm)

Source: `src/f004_decision_tree/build_decision_tree.py:105-173`

```
build_tree(records):
  1. Create root: state_id="initial_contact", branch_key={}, sentence_pool=[], children=[]

  2. For each conversation record:
     a. Extract greeting → merge into root.sentence_pool
     b. Extract segments (contiguous runs of customer state + collector responses)
     c. Walk the tree segment by segment:
        - Try local match: find child of current_node with same branch_key
        - If no local match → GLOBAL DEDUP: DFS search entire tree for branch_key
        - If no match anywhere → create new node, append as child
        - Merge segment sentences into matched node's sentence_pool
        - Advance current_node to matched node
     d. If dialog has no closing action → attach abrupt_end

  3. Post-processing (4 passes):
     a. _propagate_sentences: fill empty pools by inheriting from parent
     b. _sort_keywords: lexicographic sort of facts/emotions at every node
     c. _ensure_leaf_termination: attach abrupt_end to any unterminated leaf
     d. _consolidate_endpoints: harvest all ending sentences, strip terminal
        nodes, attach exactly one normal_end + one abrupt_end as root children
```

**Key design decisions:**
- **Global dedup** (line 147): same `(facts, emotions)` key always maps to the same node, even from different conversation paths. This is what makes the tree a *decision* tree rather than a *conversation* tree.
- **No rebalancing**: nodes are appended in encounter order. The tree shape reflects the order records were processed.
- **Sentence merging** (lines 85-102): deduplicates by `(script_text, customer_willingness, collector_action)` and merges `source_call_ids` lists.

## 13. How the Tree Is Searched (Retrieval)

Source: `src/f004_decision_tree/build_decision_tree.py:396-412`

The `find_node(tree, state_key)` function uses a **4-level fallback strategy**:

1. **Exact match**: DFS for node where `branch_key == target_key`
2. **Fallback level 1**: Strip emotions from key, retry exact
3. **Fallback level 2**: Strip last fact, retry exact
4. **Fallback level 3**: Strip all facts, retry exact

At each fallback level, it also tries **subset matching** — where the target key is a subset of the node's key. This handles partial state observations where not all facts/emotions were detected.

## 14. Structural Properties Summary

| Property | Value | Implication |
|----------|-------|-------------|
| Shape | Wide fan-out at root, then mostly chains | Most conversations diverge at the first customer state, then follow linear emotional/factual progressions |
| Chain ratio | 81.2% single-child | The tree is more "broom" than "tree" — wide at top, narrow below |
| Dedup ratio | 60 nodes from 31 records (~1.9:1) | Significant state reuse — conversations share many states |
| Fact dominance | 47% fact-only nodes | The tree primarily branches on factual circumstances, not emotions |
| Deepest path | 13 levels | Some conversations go through 14 distinct states before terminating |
| Pool concentration | 50% of sentences in 2 nodes (root + normal_end) | Most script diversity is at the beginning and end of conversations |
