# F016: Sentence Pool Augmentation — Implementation Plan

> **Status**: review | **Owner**: agent | **Priority**: P1
>
> **Worktree**: `../ICBC-f016-sentence-pool-augmentation` | **Branch**: `feat/f016-sentence-pool-augmentation`
>
> **Tests**: 68 passed | **Commit**: `f3eaf73`
>
> **Goal**: Given a tree node, generate new collector sentences via LLM that match the node's background constraints and a random customer profile, then insert them into the tree UI display and the PostgreSQL database — without modifying any existing code or data.

---

## 0. Key Findings from DB & Tree Inspection

Before writing this plan, I inspected the actual database and tree data. Here's what the real system stores:

### DB state (queried directly)
- **`nodes` table**: 5,528 rows (more than the tree's ~1,395 — accumulated from multiple pipeline runs)
- **`sentences` table**: 2,518 rows (vs 1,716 in the scored tree JSON — DB has older data too)
- **All 2,518 DB sentences have embeddings** (0 null)
- **`bg_background` has 3 different schemas** in the DB (from different pipeline versions):
  - Current pipeline: `{"business_loan_digits": 0, "mortgage_balance_digits": 0, ...}` (10 keys)
  - Older v1: `{"age": "49", "gender": "男", "industry": "...", ...}` (12 keys, Chinese values)
  - Older v2: `{"education": "本科", "risk_level": "", ...}` (8 keys, string values)
- **`sentences` table DDL**: columns are `id, script_id (UNIQUE), node_id (FK), script_text, bg_bitmask_int, win_rate, sas, bg_background (JSONB), conversation_context, embedding (vector(1024)), script_tsv (generated)`

### Tree JSON (`decision_tree_scored.json`)
- **1,716 sentences** across **105 unique call_ids**
- **`call_id`**: always 19-digit numeric string (e.g., `2346089320444241687`)
- **`script_id`**: format `{call_id}_t{turn_index}` (e.g., `2346089320444241687_t1`), or `{call_id}_t{turn_index}_merged` for merged sentences
- **`source_call_ids`**: list, almost always 1 element; `[0]` always matches the call_id in `script_id`
- **`win_rate`**: range 0.3333–0.8148 (never 0.0 in real data)
- **`win_rate_node`**: range 0.3333–0.8889 (node-level aggregate, shared by all sentences in a node)
- **`sas`**: range 0.0–1.0
- **`deferred`**: always `true`
- **`uplift_score`**: always `0`
- **`csi`**: always `0`
- **`conversation_context`**: prior utterances joined by `" "`, empty `""` for first turn
- **`gesture_type`**: `"opening"` / `"ending"` / **absent** (not null — key is omitted when N/A)
- **`bg_background`** (current pipeline schema, 10 keys):
  ```
  business_loan_digits, mortgage_balance_digits, other_loan_digits, wealth_digits,
  current_balance_digits, education, days_delinquent, recent_contact_count,
  risk_level, complaint_score
  ```
- **`bg_constraints` / `bg_bitmask`**: 10 boolean/int keys in fixed order:
  ```
  has_business_loan (bit 0), has_mortgage (bit 1), has_other_loan (bit 2),
  recent_repayment (bit 3), is_high_risk_proxy_complaint (bit 4),
  is_proxy_intermediary_complaint (bit 5), has_social_insurance (bit 6),
  has_risk_flag (bit 7), has_complaint (bit 8), has_vehicle (bit 9)
  ```

### Design implications
1. **Fake `call_id` must be 19-digit numeric** to match real format. Use prefix `9999` + 15 random digits → distinguishable but format-identical.
2. **`script_id` must be `{fake_call_id}_t{turn_index}`** — not `aug_timestamp_seq`.
3. **`source_call_ids` must be `["{fake_call_id}"]`** — not `["augmented"]`.
4. **`win_rate` should use the node's `win_rate_node`** — not 0.0 (which would stand out as fake).
5. **`deferred` must be `true`** — not `false`.
6. **`gesture_type` should be absent** (key omitted) for non-greeting/non-ending sentences.
7. **`bg_background` must use the current pipeline's 10-key schema** — not a custom format.

---

## 1. Overview

```
User picks a node (CLI arg: --node-id or --path-signature)
        │
        ▼
Script reads decision_tree_scored.json → finds target node
        │
        ▼
Script generates a random customer background profile (context dict, 17 fields)
        │
        ▼
Script generates a fake 19-digit call_id (prefix "9999" + 15 random digits)
        │
        ▼
LLM (DeepSeek, temperature=0.7) generates N collector utterances matching:
  - node's inherited_facts / inherited_emotions / collector_action
  - the random customer profile (debt situation, risk level, etc.)
  - existing sentence style (few-shot examples from the node's pool)
        │
        ▼
Script scores each new sentence (mimicking real data exactly):
  - script_id = "{fake_call_id}_t{turn_index}"  (real format)
  - source_call_ids = ["{fake_call_id}"]         (real format)
  - bg_constraints / bg_bitmask / bg_bitmask_int (from random profile, BITMASK_FIELDS order)
  - bg_background (10-key dict, current pipeline schema, from random profile)
  - win_rate = node's win_rate_node               (real range 0.333–0.889)
  - win_rate_node = node's win_rate_node          (same as existing sentences in node)
  - sas = 0.0                                     (valid, low end of real range)
  - deferred = true                               (matches all real data)
  - uplift_score = 0, csi = 0                     (matches all real data)
  - conversation_context = ""                     (standalone, like first turns)
  - gesture_type omitted                          (key absent, matches non-gesture sentences)
  - embedding via Ollama bge-m3 (1024-dim)
        │
        ├──► Write overlay JSON (augmented_sentences.json)
        │      — keyed by node_id, list of new sentence entries
        │      — UI merges via a one-line <script> tag
        │
        └──► Insert into PostgreSQL sentences table
               — via existing SentenceDB.upsert_sentences()
               — node looked up by path_signature → nodes.id
               — ON CONFLICT (script_id) DO UPDATE (idempotent)
```

---

## 2. Design Constraints

| Constraint | How satisfied |
|---|---|
| No existing code modified | All new code in `src/f016_sentence_augmentation/`. Existing modules imported read-only. |
| No existing data modified | Original `decision_tree_scored.json` untouched. New sentences go to a separate overlay file + DB only. |
| New sentences match real format | `call_id` = 19-digit numeric (prefix `9999`), `script_id` = `{call_id}_t{turn}`, `source_call_ids` = `["{call_id}"]` |
| New sentences distinguishable | `call_id` prefix `9999` (real call_ids start with `2317`–`2347`); no collision possible |
| New sentences mimic real scoring | `win_rate` = node's `win_rate_node` (not 0.0); `deferred` = `true`; `bg_background` uses current 10-key schema |
| UI shows new sentences | Overlay JS snippet merges `augmented_sentences.json` into `treeData` at load time. One `<script>` tag added to `tree_explorer.html`. |
| DB stores new sentences | Inserted via `SentenceDB.upsert_sentences()` with proper `node_id` FK. Idempotent via `ON CONFLICT (script_id) DO UPDATE`. |

---

## 3. File Structure

```
src/f016_sentence_augmentation/
├── __init__.py
├── augment_sentences.py      # Main CLI script
├── generate_prompts.py       # LLM prompt construction
├── random_profile.py         # Random customer background + fake call_id generator
├── score_sentences.py        # Score new sentences (bitmask, bg_background, embedding)
├── cleanup_db.py             # Delete extra DB sentences/nodes not in current tree
├── data/
│   └── augmented_sentences.json   # Overlay file (written by script, read by UI)
└── ui/
    └── augment_overlay.js         # UI merge snippet (loaded by tree_explorer.html)
```

**Existing files touched (minimal):**
- `src/f004_decision_tree/ui/tree_explorer.html` — add one `<script src="../../f016_sentence_augmentation/ui/augment_overlay.js"></script>` tag before `</body>`. This is the only existing file modified.

---

## 4. Detailed Design

### 4.1 Fake call_id Generator (`random_profile.py`)

Real call_ids are 19-digit numeric strings (e.g., `2346089320444241687`). To generate distinguishable but format-matching fake call_ids:

```python
def generate_fake_call_id() -> str:
    """Generate a 19-digit numeric call_id with prefix '9999' for distinguishability."""
    # Real call_ids start with 2317-2347; '9999' prefix guarantees no collision
    return "9999" + "".join(str(random.randint(0, 9)) for _ in range(15))
```

### 4.2 Random Customer Profile Generator (`random_profile.py`)

Generates a `context` dict with the same 17 fields as `output_aligned.py`:

```python
def generate_random_profile() -> dict:
    """Return a context dict matching the schema in output_aligned.py."""
    return {
        "business_loan_balance": random.choice([0, 0, 0, 50000, 200000]),
        "complaint_score": random.randint(0, 30),
        "current_balance": random.randint(1000, 5_000_000),
        "days_delinquent": 30,  # all real data has days_delinquent=30
        "education": random.choice(["bachelor", "college", "other", "unknown"]),
        "has_business_loan": random.choice([False, False, True]),
        "has_mortgage": random.choice([False, False, True]),
        "has_other_loan": random.choice([False, True, True]),
        "has_social_insurance": random.choice([True, False]),
        "is_high_risk_proxy_complaint": random.choice([False, False, True]),
        "is_proxy_intermediary_complaint": random.choice([False, True]),
        "mortgage_balance": random.choice([0, 0, 300000, 800000]),
        "other_loan_balance": random.randint(0, 200000),
        "recent_contact_count": random.randint(0, 13),
        "recent_repayment": random.choice([False, False, True]),
        "risk_level": random.randint(0, 4),
        "vehicle_count": random.randint(0, 3),
        "wealth_value": random.randint(0, 500000),
    }
```

Design choices:
- `days_delinquent` hardcoded to 30 (all 1,716 real sentences have this value)
- `education` uses the 4 values seen in current-pipeline `bg_background`: `bachelor`, `college`, `other`, `unknown`
- `risk_level` range 0–4 (matches real data)
- `recent_contact_count` range 0–13 (matches real data)
- Boolean fields biased toward `False` (realistic)

### 4.3 LLM Prompt Construction (`generate_prompts.py`)

```python
def build_augmentation_prompt(
    node: dict,
    profile: dict,
    existing_sentences: list[dict],
    n: int,
) -> str:
    """Build the DeepSeek prompt for generating new collector sentences."""
```

The prompt structure:

```
你是一位专业的催收话术专家。请根据以下信息生成{N}条催收员话术。

## 节点信息
- 节点类型: {role} (opening/decision/action)
- 客户事实标签: {inherited_facts}
- 客户情绪标签: {inherited_emotions}
- 催收员动作: {collector_action}
- 分支键: {branch_key}

## 客户背景
- 逾期天数: {days_delinquent}
- 风险等级: {risk_level}
- 当前余额: {current_balance}
- 是否有房贷: {has_mortgage}
- 是否有经营贷: {has_business_loan}
- 是否有其他贷款: {has_other_loan}
- 学历: {education}
- 投诉分数: {complaint_score}
- 近期联系次数: {recent_contact_count}

## 现有话术示例（参考风格，不要重复）
1. {existing_sentence_1}
2. {existing_sentence_2}
3. {existing_sentence_3}

## 要求
- 生成{N}条不同的催收员话术
- 话术要符合上述节点类型和客户背景
- 语气专业、合规，不得有威胁性语言
- 每条话术长度50-200字
- 返回JSON格式: {"sentences": ["话术1", "话术2", ...]}
```

Key design decisions:
- **Few-shot examples**: Use up to 3 existing sentences from the node's pool to guide style/tone
- **Customer profile in Chinese**: The real data is Mandarin, so the prompt is in Chinese
- **JSON response**: Use `call_deepseek_json()` for structured output
- **Compliance guard**: Explicit instruction against threatening language
- **Length constraint**: 50-200 chars matches observed sentence lengths

### 4.4 Sentence Scoring (`score_sentences.py`)

For each generated sentence, compute all fields to **exactly match the scored tree schema**:

```python
from f005_context_scoring.scoring_metrics import (
    encode_bitmask,
    encode_bitmask_int,
)
from f007_infrastructure.embeddings import embed_single

# Replicate _extract_bg_constraints for a single profile (10 lines)
def _extract_bg_constraints_single(profile: dict) -> dict:
    return {
        "has_business_loan": bool(profile.get("has_business_loan")),
        "has_mortgage": bool(profile.get("has_mortgage")),
        "has_other_loan": bool(profile.get("has_other_loan")),
        "recent_repayment": bool(profile.get("recent_repayment")),
        "is_high_risk_proxy_complaint": bool(profile.get("is_high_risk_proxy_complaint")),
        "is_proxy_intermediary_complaint": bool(profile.get("is_proxy_intermediary_complaint")),
        "has_social_insurance": bool(profile.get("has_social_insurance")),
        "has_risk_flag": int(profile.get("risk_level", 0)) > 0,
        "has_complaint": int(profile.get("complaint_score", 0)) > 0,
        "has_vehicle": int(profile.get("vehicle_count", 0)) > 0,
    }

# Replicate _extract_bg_background for a single profile (10-key dict)
def _extract_bg_background_single(profile: dict) -> dict:
    def _digit_count(n):
        n = abs(int(n or 0))
        return len(str(n)) if n > 0 else 0
    return {
        "business_loan_digits": _digit_count(profile.get("business_loan_balance")),
        "mortgage_balance_digits": _digit_count(profile.get("mortgage_balance")),
        "other_loan_digits": _digit_count(profile.get("other_loan_balance")),
        "wealth_digits": _digit_count(profile.get("wealth_value")),
        "current_balance_digits": _digit_count(profile.get("current_balance")),
        "education": profile.get("education", "unknown"),
        "days_delinquent": int(profile.get("days_delinquent", 0)),
        "recent_contact_count": int(profile.get("recent_contact_count", 0)),
        "risk_level": int(profile.get("risk_level", 0)),
        "complaint_score": int(profile.get("complaint_score", 0)),
    }

def score_new_sentence(
    text: str,
    profile: dict,          # the random context dict
    fake_call_id: str,      # 19-digit numeric, prefix "9999"
    turn_index: int,        # e.g., 1
    node: dict,             # the target tree node
) -> dict:
    # 1. script_id in real format: {call_id}_t{turn_index}
    script_id = f"{fake_call_id}_t{turn_index}"

    # 2. Background constraints (single profile, no aggregation)
    bg_constraints = _extract_bg_constraints_single(profile)
    bg_bitmask = encode_bitmask(bg_constraints)
    bg_bitmask_int = encode_bitmask_int(bg_bitmask)

    # 3. Background profile (10-key dict, current pipeline schema)
    bg_background = _extract_bg_background_single(profile)

    # 4. Embedding (1024-dim via bge-m3)
    embedding = embed_single(text)

    # 5. win_rate: use node's existing win_rate_node (realistic, not 0.0)
    existing_pool = node.get("sentence_pool", [])
    win_rate_node = existing_pool[0].get("win_rate_node", 0.5) if existing_pool else 0.5

    # 6. collector_action: from node's branch_key or existing sentences
    collector_action = node.get("branch_key", {}).get("action")
    if not collector_action and existing_pool:
        collector_action = existing_pool[0].get("collector_action")

    # 7. Build sentence entry — matches scored tree schema exactly
    sentence = {
        "script_text": text,
        "script_id": script_id,
        "source_call_ids": [fake_call_id],     # real format: list of call_id strings
        "customer_willingness": None,           # collector turn
        "collector_action": collector_action,
        "fact_context": node.get("inherited_facts", []),
        "bg_constraints": bg_constraints,
        "bg_bitmask": bg_bitmask,
        "bg_bitmask_int": bg_bitmask_int,
        "bg_background": bg_background,
        "win_rate": win_rate_node,              # node's historical win rate (0.333–0.889)
        "win_rate_node": win_rate_node,         # same as existing sentences in node
        "uplift_score": 0,                      # matches all real data
        "csi": 0,                               # matches all real data
        "deferred": True,                       # matches all real data
        "conversation_context": "",             # standalone, like first turns
        "sas": 0.0,                             # valid low end of real range
    }

    # gesture_type: omit key entirely (matches non-gesture real sentences)
    # Only add if node is opening (gesture_type="opening") or ending (gesture_type="ending")
    if node.get("role") == "opening" and collector_action == "greeting":
        sentence["gesture_type"] = "opening"
    # For ending nodes, could add gesture_type="ending" — but omit for simplicity

    # embedding stored separately for DB insert (not in scored tree JSON)
    sentence["_embedding"] = embedding

    return sentence
```

### 4.5 Overlay JSON Format (`data/augmented_sentences.json`)

```json
{
  "version": 1,
  "generated_at": "2026-07-10T12:00:00",
  "augmentations": {
    "n_b8e3ecee405b": {
      "path_signature": "initial_contact",
      "sentences": [
        {
          "script_text": "先生您好，我们看到您名下账户...",
          "script_id": "9999384726105938472_t1",
          "source_call_ids": ["9999384726105938472"],
          "customer_willingness": null,
          "collector_action": "greeting",
          "fact_context": [],
          "bg_constraints": {"has_business_loan": false, "has_mortgage": false, ...},
          "bg_bitmask": {"has_business_loan": 0, "has_mortgage": 0, ...},
          "bg_bitmask_int": 388,
          "bg_background": {"business_loan_digits": 0, "mortgage_balance_digits": 0, ...},
          "win_rate": 0.7383,
          "win_rate_node": 0.7383,
          "uplift_score": 0,
          "csi": 0,
          "deferred": true,
          "conversation_context": "",
          "sas": 0.0
        }
      ]
    }
  }
}
```

Key differences from v1 plan:
- `script_id` = `9999384726105938472_t1` (real format, not `aug_...`)
- `source_call_ids` = `["9999384726105938472"]` (real call_id, not `["augmented"]`)
- `win_rate` = 0.7383 (node's win_rate_node, not 0.0)
- `deferred` = true (not false)
- `gesture_type` omitted (not null)
- `bg_background` uses current 10-key schema

The script **appends** to this file — if it already exists, load it, add sentences for the target node, and write back.

### 4.6 UI Overlay Script (`ui/augment_overlay.js`)

```javascript
(function() {
  fetch('../../f016_sentence_augmentation/data/augmented_sentences.json?_=' + Date.now())
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if (!data || !data.augmentations) return;
      function walk(node) {
        var aug = data.augmentations[node.node_id];
        if (aug && aug.sentences) {
          aug.sentences.forEach(function(s) { s._augmented = true; });
          node.sentence_pool = (node.sentence_pool || []).concat(aug.sentences);
        }
        if (node.children) node.children.forEach(walk);
      }
      walk(treeData);
    })
    .catch(function(e) { console.warn('augment overlay failed:', e); });
})();
```

**One line added to `tree_explorer.html`** (before `</body>`, after existing scripts):
```html
<script src="../../f016_sentence_augmentation/ui/augment_overlay.js"></script>
```

### 4.7 Database Insertion

Uses the existing `SentenceDB` class (sync, psycopg2) — no modifications:

```python
from f007_infrastructure.db import SentenceDB

def insert_into_db(sentences: list[dict], path_signature: str, dsn: str):
    db = SentenceDB(dsn)
    try:
        node_row = db.get_node_by_signature(path_signature)
        if not node_row:
            raise ValueError(f"Node not found in DB: {path_signature}")

        db_sentences = []
        for s in sentences:
            db_sentences.append({
                "script_id": s["script_id"],
                "node_id": node_row["id"],
                "script_text": s["script_text"],
                "bg_bitmask_int": s["bg_bitmask_int"],
                "win_rate": s["win_rate"],
                "sas": s["sas"],
                "bg_background": json.dumps(s["bg_background"]),
                "conversation_context": s["conversation_context"],
                "embedding": s["_embedding"],
            })

        db.upsert_sentences(db_sentences)
    finally:
        db.close()
```

The DB `sentences` table columns mapped:
| DB column | Source | Notes |
|---|---|---|
| `script_id` | `{fake_call_id}_t{turn_index}` | UNIQUE, ON CONFLICT DO UPDATE |
| `node_id` | `nodes.id` (looked up by `path_signature`) | FK |
| `script_text` | LLM-generated text | |
| `bg_bitmask_int` | computed from random profile | |
| `win_rate` | node's `win_rate_node` | real range 0.333–0.889 |
| `sas` | 0.0 | |
| `bg_background` | 10-key dict as JSONB | current pipeline schema |
| `conversation_context` | `""` | |
| `embedding` | 1024-dim float vector from bge-m3 | |
| `script_tsv` | auto-generated by DB | (not inserted) |

### 4.8 Main CLI Script (`augment_sentences.py`)

```bash
python3 -m f016_sentence_augmentation.augment_sentences \
    --node-id n_b8e3ecee405b \
    --count 5 \
    --dsn "dbname=icbc user=jiani" \
    [--no-db]      # skip DB insert (overlay only)
    [--no-overlay] # skip overlay file (DB only)
    [--seed 42]    # reproducible random profile
```

Or by path_signature:
```bash
python3 -m f016_sentence_augmentation.augment_sentences \
    --path-signature "initial_contact/f:repayment_inability" \
    --count 10
```

Execution flow:
1. Parse args (node_id or path_signature, count, dsn, flags)
2. Load `decision_tree_scored.json`
3. Find target node by node_id or path_signature (recursive walk)
4. Generate fake call_id (19-digit, prefix `9999`)
5. Generate random customer profile (`random_profile.py`)
6. Build LLM prompt (`generate_prompts.py`)
7. Call `call_deepseek_json(prompt, temperature=0.7)` → get N sentence texts
8. Score each sentence (`score_sentences.py`) — script_id, bitmask, bg_background, win_rate, embedding
9. Write/append to `augmented_sentences.json` overlay (without `_embedding` key)
10. If not `--no-db`: insert into PostgreSQL via `SentenceDB.upsert_sentences()`
11. Print summary: node, fake_call_id, count, script_ids, overlay path, DB status

### 4.9 DB Cleanup Script (`cleanup_db.py`)

The DB has accumulated data from multiple pipeline runs and is out of sync with the current scored tree:

| | Tree (`decision_tree_scored.json`) | DB | Extra in DB |
|---|---|---|---|
| Sentences | 1,716 | 2,518 | **802** (from older pipeline runs) |
| Nodes | 1,395 | 5,528 | **4,133** (from older pipeline runs) |

All 1,716 tree sentences and all 1,395 tree nodes exist in the DB (0 missing). The extras are from older pipeline versions (call_ids starting `2317...`, `2320...`, etc.).

**Complication found during inspection**: 58 tree sentences (by `script_id`) are linked to extra (non-tree) nodes in the DB — the sentence exists but its `node_id` points to an old node. These must be **re-linked** to the correct tree node before deleting extra nodes. Additionally, 272 extra sentences sit on tree nodes — these are simply deleted.

**FK constraints** (verified safe):
- `sentences.node_id → nodes.id`: handled by re-linking + deletion order
- `nodes.parent_id → nodes.id`: all 4,133 extra nodes have `parent_id = NULL` (no references to or from tree nodes) — safe to delete directly

#### CLI

```bash
python3 -m f016_sentence_augmentation.cleanup_db \
    --dsn "dbname=icbc user=jiani" \
    [--dry-run]         # print what would be deleted, don't actually delete
    [--keep-augmented]  # preserve sentences with script_id LIKE '9999%' (default: true)
    [--no-keep-augmented]  # also delete augmented sentences
```

#### Execution flow

```
Step 1: Load decision_tree_scored.json → build two mappings:
  - tree_script_ids: set of 1,716 script_id strings
  - tree_sid_to_psig: {script_id → path_signature} (which tree node each sentence belongs to)

Step 2: Query DB → build:
  - db_psig_to_node_id: {path_signature → nodes.id} (for tree path_signatures only)
  - db_sid_to_node_psig: {script_id → path_signature} (current DB sentence→node mapping)

Step 3: Identify misplaced tree sentences (58 expected):
  - For each script_id in tree_script_ids:
    - If DB has it AND its DB path_signature NOT in tree → it's misplaced
  - For each misplaced sentence:
    - Correct path_signature = tree_sid_to_psig[script_id]
    - Correct node_id = db_psig_to_node_id[correct path_signature]

Step 4: Identify extra sentences to delete (802 expected):
  - DB script_ids NOT IN tree_script_ids
  - Minus augmented sentences (LIKE '9999%') if --keep-augmented

Step 5: Identify extra nodes to delete (4,133 expected):
  - DB path_signatures NOT IN tree path_signatures

Step 6: Execute (unless --dry-run):
  BEGIN TRANSACTION
    -- 6a. Re-link misplaced tree sentences to correct tree nodes
    UPDATE sentences SET node_id = {correct_node_id}
    WHERE script_id = '{misplaced_script_id}';   -- ×58

    -- 6b. Delete extra sentences
    DELETE FROM sentences
    WHERE script_id NOT IN ({tree_script_ids})
    AND script_id NOT LIKE '9999%';              -- ×802

    -- 6c. Delete extra nodes (safe: parent_id all NULL, no sentences remaining)
    DELETE FROM nodes
    WHERE path_signature NOT IN ({tree_path_signatures});  -- ×4,133
  COMMIT

Step 7: Verify and print summary:
  - SELECT count(*) FROM sentences  → should be 1,716 + N_augmented
  - SELECT count(*) FROM nodes      → should be 1,395
  - SELECT count(*) FROM sentences s JOIN nodes n ON s.node_id=n.id
    WHERE n.path_signature NOT IN ({tree_path_signatures})  → should be 0
```

#### Output example

```
DB Cleanup Summary
══════════════════════════════════════════════════
Tree sentences:     1,716
Tree nodes:         1,395
DB sentences (before): 2,518
DB nodes (before):     5,528

Misplaced tree sentences re-linked:  58
Extra sentences deleted:             802
Extra nodes deleted:               4,133
Augmented sentences preserved:        0  (none in DB yet)

DB sentences (after):  1,716
DB nodes (after):      1,395
✅ DB aligns with tree
```

#### `--dry-run` output

Same summary but prefixed with `DRY RUN —` and no actual SQL executed. Prints the SQL statements that would run.

---

## 5. Data Flow Summary

```
                    EXISTING (read-only)
                    ─────────────────
decision_tree_scored.json ──────► augment_sentences.py (reads to find node + win_rate_node)
                                        │
                                        │ generates fake call_id (9999+15 digits)
                                        │ generates random profile (17 fields)
                                        │ calls DeepSeek LLM (temperature=0.7)
                                        │ scores sentences (bitmask, bg_background, embed)
                                        │   win_rate = node's win_rate_node
                                        │   deferred = true, uplift=0, csi=0
                                        │   script_id = {call_id}_t{turn}
                                        │   source_call_ids = [{call_id}]
                                        │
                              ┌─────────┴─────────┐
                              ▼                   ▼
                    NEW (written)           EXISTING (used read-only)
                    ────────────            ──────────────────────
                    augmented_sentences.json  SentenceDB.upsert_sentences()
                    (no _embedding key)       (with _embedding → embedding col)
                              │                   │
                              ▼                   ▼
                    augment_overlay.js      PostgreSQL sentences table
                    (merged into treeData)  (2518 → 2518+N rows)
                              │                   │
                              ▼                   ▼
                    tree_explorer.html      cleanup_db.py (optional)
                    (one <script> tag added)  (2518→1716 sentences, 5528→1395 nodes)
                                              re-links 58 misplaced, deletes 802+4133 extra
```

---

## 6. Step-by-Step Implementation Order

| Step | File | What | Verify |
|------|------|------|--------|
| 1 | `src/f016_sentence_augmentation/__init__.py` | Empty package marker | `python3 -c "import f016_sentence_augmentation"` |
| 2 | `random_profile.py` | Fake call_id + random profile generator | call_id is 19 digits, starts with `9999`; profile has all 17 fields with correct types |
| 3 | `generate_prompts.py` | LLM prompt builder | Prompt includes node info, profile, few-shot examples |
| 4 | `score_sentences.py` | Sentence scorer | Output dict has all scored-tree fields; `script_id` matches `{call_id}_t{turn}` format; `bg_bitmask_int` matches manual calculation; `win_rate` = node's `win_rate_node`; `deferred` = true; `gesture_type` absent |
| 5 | `augment_sentences.py` | Main CLI | `--help` works; `--node-id` finds node; dry run with `--no-db --no-overlay` prints generated sentences with correct format |
| 6 | `data/augmented_sentences.json` | (auto-generated) | JSON valid; keyed by node_id; sentences have all fields matching scored tree schema |
| 7 | `ui/augment_overlay.js` | UI merge snippet | Fetches overlay, merges into treeData, no console errors |
| 8 | `tree_explorer.html` | Add `<script>` tag | One line added; UI loads; augmented sentences appear in node info panel with scores |
| 9 | DB insert | End-to-end | `SELECT * FROM sentences WHERE script_id LIKE '9999%'` returns N rows; `embedding IS NOT NULL` for all; `node_id` matches `nodes.id` for the target path_signature |
| 10 | UI verify | Reload tree explorer | Click target node → new sentences visible in info panel → HWR bar shows win_rate → CTX shows bg_bitmask_int → script_id shows `9999..._t1` format |
| 11 | `cleanup_db.py` | DB cleanup script | `--dry-run` prints 58 re-links + 802 sentence deletes + 4,133 node deletes; actual run leaves DB at 1,716 sentences / 1,395 nodes |

---

## 7. Edge Cases & Safeguards

| Case | Handling |
|------|----------|
| Node not found in tree | Print available nodes (state_id + node_id + pool size), exit 1 |
| Node not found in DB | Warn: "Node exists in tree but not in DB. Skipping DB insert. Overlay only." |
| Node has empty sentence_pool | Use `win_rate_node=0.5` as fallback; skip few-shot examples in prompt |
| LLM returns fewer than N sentences | Use what we get; warn if 0 |
| LLM returns duplicate texts | Dedup within batch; skip dups |
| Fake call_id collision (extremely unlikely) | Regenerate if `script_id` already in overlay or DB |
| Overlay file already has sentences for this node | Append new ones (don't replace) |
| DB connection fails | Print error, still write overlay (graceful degradation) |
| Embedding service (Ollama) down | Set embedding=None, warn; sentence still inserted (search_similar skips null embeddings) |
| `--no-db` flag | Skip DB entirely, overlay only |
| `--no-overlay` flag | Skip overlay, DB only |
| Reproducibility | `--seed` controls `random` module; LLM temperature 0.7 |

---

## 8. LLM Temperature

Use `temperature=0.7` for sentence generation (higher than the 0.1 used for extraction/labeling). We want creative, diverse sentences — not deterministic extraction. Passed explicitly to `call_deepseek_json(prompt, temperature=0.7)`.

---

## 9. Fake call_id & script_id Scheme

### call_id
```
9999{15 random digits}  →  19-digit numeric string
```
Example: `9999384726105938472`

- Prefix `9999` distinguishes from real call_ids (which start with `2317`–`2347`)
- 19 digits matches real format exactly
- No collision possible (real call_ids never start with `9999`)

### script_id
```
{fake_call_id}_t{turn_index}
```
Example: `9999384726105938472_t1`

- Matches real format exactly (`{call_id}_t{turn_index}`)
- `ON CONFLICT (script_id) DO UPDATE` in DB upsert is safe
- Globally unique (fake call_id is unique, turn_index is unique within batch)

### source_call_ids
```
["{fake_call_id}"]
```
Example: `["9999384726105938472"]`

- Single-element list, matching 99.94% of real data (1715 of 1716 entries)
- `[0]` matches the call_id in `script_id` (consistent with real data invariant)

---

## 10. What This Does NOT Touch

| Existing file/dir | Why it's safe |
|---|---|
| `src/f004_decision_tree/data/decision_tree.json` | Read-only (not used — we read the scored tree) |
| `src/f005_context_scoring/data/decision_tree_scored.json` | Read-only (loaded to find node + win_rate_node, never written) |
| `src/f003_reward_labeling/data/output_rewarded.py` | Not touched |
| `src/f001_schema_alignment/data/output_aligned.py` | Not touched |
| `src/f006_retrieval_engine/` | Not modified (reads from DB at runtime — new sentences appear automatically in `/recommend`) |
| `src/f009_api_server/` | Not modified (recommend endpoint queries DB — new sentences appear automatically) |
| `src/f007_infrastructure/` | Imported read-only (SentenceDB, embeddings, llm_client, config, scoring_metrics) |
| `data/` | Not touched |
| `config.md` | Not modified (all config read via existing `get()` function) |

**The only existing file modified**: `src/f004_decision_tree/ui/tree_explorer.html` — one `<script>` tag added before `</body>`.

**`cleanup_db.py`**: Only deletes DB rows that are NOT in the current tree (802 extra sentences, 4,133 extra nodes from older pipeline runs). It re-links 58 misplaced tree sentences to their correct tree nodes. It does NOT delete any sentence or node that exists in the current scored tree. Augmented sentences (`9999%`) are preserved by default.

---

## 11. Verification Queries

After running the script, verify with:

```sql
-- New sentences in DB
SELECT script_id, node_id, bg_bitmask_int, win_rate, sas
FROM sentences
WHERE script_id LIKE '9999%'
ORDER BY script_id;

-- Embeddings present
SELECT count(*) FROM sentences WHERE script_id LIKE '9999%' AND embedding IS NOT NULL;

-- Node FK correct
SELECT s.script_id, n.path_signature
FROM sentences s
JOIN nodes n ON s.node_id = n.id
WHERE s.script_id LIKE '9999%';

-- bg_background schema correct (should have 10 keys with *_digits)
SELECT script_id, jsonb_object_keys(bg_background)
FROM sentences
WHERE script_id LIKE '9999%'
LIMIT 10;
```

### After running `cleanup_db.py`

```sql
-- DB aligns with tree
SELECT count(*) as sentence_count FROM sentences;  -- should be 1716 + N_augmented
SELECT count(*) as node_count FROM nodes;          -- should be 1395

-- No sentences on extra nodes
SELECT count(*) as orphaned
FROM sentences s
JOIN nodes n ON s.node_id = n.id
WHERE n.path_signature NOT IN (
  -- paste tree path_signatures here, or compare programmatically
  'initial_contact'
);

-- All tree sentences present
-- (run from Python: compare tree script_ids vs DB script_ids)
```

---

## 12. Future Extensions (out of scope)

- **Batch augmentation**: augment multiple nodes in one run (`--nodes n1,n2,n3`)
- **Profile templates**: use real customer profiles from `output_aligned.py` instead of random
- **Quality scoring**: run SAS against the node's existing pool post-insertion
- **Win rate estimation**: use LLM to estimate likely win rate for the generated sentence
- **A/B testing**: mark augmented sentences for comparison against real ones in production
- **Remove augmented**: `--remove-augmented` flag to delete only `9999%` sentences from DB + overlay
- **UI panel**: dedicated panel showing all augmented sentences across nodes, with delete buttons
- **CSS styling**: add `.ni-script[data-augmented]` CSS for green border or "AUG" badge on augmented sentences in the tree explorer
