# F016 Fix Plan: Unique call_id + LLM Diversity

> **Status**: planned | **Priority**: P0

## Problem

Two bugs found during end-to-end testing:

1. **call_id collision** (`augment_sentences.py:108`): `generate_fake_call_id()` is called once with no collision check. With `--seed N`, the first `random` call is deterministic → same call_id every run → silently overwrites existing DB rows via `ON CONFLICT DO UPDATE`. Even without `--seed`, two concurrent runs can collide (unlikely but unguarded). Plan §7 specifies "Regenerate if script_id already in overlay or DB" — never implemented.

2. **Low diversity** (`augment_sentences.py:116`): `temperature=0.7` produces templated, robotic sentences. User wants higher temperature + prompt changes for natural, human-like phrasing.

## Fix 1: Guaranteed-unique call_id

### Root cause
`generate_fake_call_id()` returns `"9999" + 15 random digits`. No check against existing IDs.

### Solution
Add a `generate_unique_call_id()` wrapper that retries until no collision, checking against overlay + DB.

**`random_profile.py`** — add:
```python
def generate_unique_call_id(
    existing_script_ids: set[str],
    count: int,
    max_retries: int = 100,
) -> str:
    """Generate a fake call_id guaranteed not to collide with existing script_ids."""
    for _ in range(max_retries):
        call_id = generate_fake_call_id()
        # Check all turn indices we'll generate
        if not any(f"{call_id}_t{i}" in existing_script_ids for i in range(1, count + 1)):
            return call_id
    raise RuntimeError(f"Could not generate unique call_id after {max_retries} retries")
```

**`augment_sentences.py`** — in `run_augmentation()`, replace line 108:
```python
# Collect existing script_ids from overlay + DB
existing_script_ids = set()
if not no_overlay:
    overlay = load_overlay(overlay_path)
    for aug in overlay.get("augmentations", {}).values():
        for s in aug.get("sentences", []):
            existing_script_ids.add(s["script_id"])
if not no_db and dsn:
    try:
        import psycopg2
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute("SELECT script_id FROM sentences WHERE script_id LIKE '9999%'")
        existing_script_ids.update(row[0] for row in cur.fetchall())
        cur.close()
        conn.close()
    except Exception:
        pass  # graceful: skip DB check if unavailable

fake_call_id = generate_unique_call_id(existing_script_ids, count)
```

### Files changed
- `random_profile.py` — add `generate_unique_call_id()`
- `augment_sentences.py` — replace `generate_fake_call_id()` call with collision-checked version

### Tests
- `test_random_profile.py` — add `TestGenerateUniqueId`:
  - `test_no_collision_when_ids_clear` — empty set → returns 19-digit 9999-prefixed ID
  - `test_retries_on_collision` — pre-populate set with the first call_id → returns a different one
  - `test_raises_after_max_retries` — fill all possible IDs → raises RuntimeError (use small mock)
  - `test_checks_all_turn_indices` — put `{call_id}_t1` in set, count=2 → returns different call_id

---

## Fix 2: Higher LLM temperature + human-like prompt

### 2a. Temperature: 0.7 → 1.1

**`augment_sentences.py:116`**:
```python
# Before
response = call_deepseek_json(prompt, temperature=0.7)
# After
response = call_deepseek_json(prompt, temperature=1.1)
```

Rationale: DeepSeek supports temperature up to 2.0. 1.1 gives strong diversity without losing coherence. 0.7 was too conservative — sentences came out formulaic ("您好，我是XX机构的...").

### 2b. Prompt: add natural-language instructions

**`generate_prompts.py`** — update the `## 要求` section:

```
## 要求
- 生成{n}条不同的催收员话术
- 话术要符合上述节点类型和客户背景
- 语气专业、合规，不得有威胁性语言
- 每条话术长度50-200字
- 像真人说话，不要用模板化句式，每条开头、措辞、节奏都要不同
- 可以有口语化表达、停顿词（如"嗯"、"那个"），但保持专业
- 根据客户背景调整语气：高风险客户更谨慎，老客户更亲切
- 不要每条都以"您好"开头，变化开场方式
- 返回JSON格式: {{"sentences": ["话术1", "话术2", ...]}}
```

Key additions:
- "像真人说话，不要用模板化句式" — anti-template guard
- "可以有口语化表达、停顿词" — permits natural filler
- "根据客户背景调整语气" — context-sensitive tone
- "不要每条都以'您好'开头" — forces opening variety

### Files changed
- `augment_sentences.py` — line 116: `temperature=0.7` → `temperature=1.1`
- `generate_prompts.py` — expand `## 要求` section with 4 new instructions

### Tests
- `test_generate_prompts.py` — add:
  - `test_prompt_contains_human_like_instruction` — assert "真人" in prompt
  - `test_prompt_contains_no_template_instruction` — assert "模板" in prompt
  - `test_prompt_contains_opening_variety_instruction` — assert "您好" in prompt (the instruction about not always starting with it)

---

## Execution Order

| Step | File | Change | Verify |
|------|------|--------|--------|
| 1 | `random_profile.py` | Add `generate_unique_call_id()` | Unit tests pass |
| 2 | `augment_sentences.py:108` | Replace with collision-checked call | Overlay+DB IDs checked before generation |
| 3 | `augment_sentences.py:116` | `temperature=0.7` → `1.1` | LLM output more diverse |
| 4 | `generate_prompts.py` | Add 4 human-like instructions to `## 要求` | Prompt contains new instructions |
| 5 | tests | Add tests for both fixes | `pytest tests/f016_sentence_augmentation/ -v` all pass |
| 6 | e2e | Run `--seed 42` twice → different call_ids, no collision | No DB row overwrite |

## What this does NOT change
- `score_sentences.py` — untouched
- `cleanup_db.py` — untouched
- `augment_overlay.js` — untouched
- `tree_explorer.html` — untouched
- DB schema — untouched
- Overlay JSON format — untouched
