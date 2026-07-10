# F016: remove_call_id.py — Implementation Plan

> **Status**: planned | **Owner**: agent | **Priority**: P2
>
> **Goal**: A CLI script that removes all traces of a given call_id (real or augmented) from every data source in the project — DB, tree JSON, overlay JSON, dialog records, merge decisions, raw JSONL, embedding cache, and ids.md.

---

## 1. Overview

```
User provides a call_id (19-digit numeric string)
        │
        ▼
Script scans all 14 data sources (skipping .py files)
        │
        ├──► DB sentences table
        ├──► augmented_sentences.json (F016 overlay)
        ├──► decision_tree_scored.json (F005 scored tree)
        ├──► decision_tree.json (F004 tree)
        ├──► dialog_records.json (F004 dialog records)
        ├──► merge_decisions.json (F004 merge decisions)
        ├──► matched_data.jsonl (raw input data)
        ├──► embedding_cache.json (old_files)
        └──► ids.md (old_files)
        │
        ▼
For each source: identify entries, optionally delete, report count
        │
        ▼
Print summary table
```

---

## 2. CLI Interface

```bash
python3 -m f016_sentence_augmentation.remove_call_id \
    --call-id 9999104332181960013 \
    --dsn "dbname=icbc user=jiani" \
    [--dry-run]         # preview only, no modifications
    [--no-db]           # skip DB removal
    [--no-files]        # skip file removals (DB only)
```

### Arguments

| Arg | Required | Default | Description |
|-----|----------|---------|-------------|
| `--call-id` | Yes | — | 19-digit numeric call_id (real `2346…` or augmented `9999…`) |
| `--dsn` | No | `""` | PostgreSQL DSN. If empty, skip DB. |
| `--dry-run` | No | `False` | Print what would be removed, don't modify anything. |
| `--no-db` | No | `False` | Skip DB removal. |
| `--no-files` | No | `False` | Skip file removals (DB only). |

### Validation

- `--call-id` must be a string of exactly 19 digits. Otherwise: error + exit 1.
- If `--dsn` is empty and not `--no-db`: warn "No DSN provided, skipping DB".

---

## 3. Data Sources (14 total)

`.py` data files are **skipped** (pipeline intermediates, regenerable).

### 3.1 PostgreSQL DB (`sentences` table)

- **call_id form**: `script_id` prefix (`{call_id}_t{turn}`)
- **Identify**: `SELECT id, script_id, node_id FROM sentences WHERE script_id LIKE '{call_id}_t%'`
- **Remove**: `DELETE FROM sentences WHERE script_id LIKE '{call_id}_t%'`
- **Transaction**: yes (rollback on error)
- **Does NOT delete nodes** — nodes are tree structure, not call-specific. But reports any nodes whose sentence count drops to 0 after removal.

### 3.2 `augmented_sentences.json` (F016 overlay)

- **Path**: `src/f016_sentence_augmentation/data/augmented_sentences.json`
- **call_id form**: `script_id` prefix + `source_call_ids` list entries
- **Identify**: walk `augmentations[*].sentences`, find entries where `script_id.startswith("{call_id}_t")` or `call_id in source_call_ids`
- **Remove**: filter out matching entries. If a node block's `sentences` list becomes empty, remove the node key from `augmentations`.
- **Write**: atomic (write temp → rename)

### 3.3 `decision_tree_scored.json` (F005 scored tree)

- **Path**: `src/f005_context_scoring/data/decision_tree_scored.json`
- **call_id form**: `script_id` prefix + `source_call_ids` list entries in `sentence_pool` arrays
- **Identify**: recursive walk of tree nodes, check each `sentence_pool` entry
- **Remove**: filter matching entries from each node's `sentence_pool`
- **Write**: atomic; preserve `ensure_ascii=False, indent=2`

### 3.4 `decision_tree.json` (F004 tree)

- **Path**: `src/f004_decision_tree/data/decision_tree.json`
- **call_id form**: same as 3.3
- **Identify + Remove**: same recursive walk
- **Write**: atomic

### 3.5 `dialog_records.json` (F004 dialog records)

- **Path**: `src/f004_decision_tree/data/dialog_records.json`
- **call_id form**: top-level `call_id` field per record
- **Structure**: list of dicts, each with `call_id` key
- **Identify**: `record["call_id"] == call_id`
- **Remove**: filter out matching records
- **Write**: atomic

### 3.6 `merge_decisions.json` (F004 merge decisions)

- **Path**: `src/f004_decision_tree/data/merge_decisions.json`
- **call_id form**: key prefix `{call_id}:`
- **Structure**: dict keyed by `"{call_id}:{turns}"`
- **Identify**: keys starting with `"{call_id}:"`
- **Remove**: drop matching keys
- **Write**: atomic

### 3.7 `matched_data.jsonl` (raw input)

- **Path**: `data/data_input/matched_data.jsonl`
- **call_id form**: `call_id` JSON key per line
- **Identify**: `json.loads(line)["call_id"] == call_id`
- **Remove**: filter out matching lines
- **Write**: atomic; one JSON per line, `ensure_ascii=False`

### 3.8 `embedding_cache.json` (old_files)

- **Path**: `old_files/embedding_cache.json`
- **call_id form**: key = `{call_id}_t{turn}`
- **Structure**: dict keyed by `script_id`
- **Identify**: keys starting with `"{call_id}_t"`
- **Remove**: drop matching keys
- **Write**: atomic

### 3.9 `ids.md` (old_files)

- **Path**: `old_files/ids.md`
- **call_id form**: bare call_id per line
- **Identify**: line.strip() == call_id
- **Remove**: drop matching lines
- **Write**: atomic

---

## 4. File Structure

```
src/f016_sentence_augmentation/
├── remove_call_id.py          # NEW — the removal CLI script
```

No new directories. Script lives alongside `cleanup_db.py` and `augment_sentences.py`.

---

## 5. Detailed Design

### 5.1 Entry Point

```python
def main():
    args = parse_args()
    validate_call_id(args.call_id)

    results = {}
    if not args.no_db and args.dsn:
        results["DB sentences"] = remove_from_db(args.call_id, args.dsn, args.dry_run)
    if not args.no_files:
        for name, path, remover in FILE_SOURCES:
            results[name] = remover(args.call_id, path, args.dry_run)

    print_summary(args.call_id, results, args.dry_run)
```

### 5.2 Call ID Validation

```python
def validate_call_id(call_id: str):
    if not call_id.isdigit() or len(call_id) != 19:
        print(f"ERROR: call_id must be exactly 19 digits, got: {call_id}")
        sys.exit(1)
```

### 5.3 DB Removal

```python
def remove_from_db(call_id: str, dsn: str, dry_run: bool) -> int:
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()
    pattern = f"{call_id}_t%"
    cur.execute("SELECT count(*) FROM sentences WHERE script_id LIKE %s", (pattern,))
    count = cur.fetchone()[0]
    if not dry_run and count > 0:
        cur.execute("DELETE FROM sentences WHERE script_id LIKE %s", (pattern,))
        conn.commit()
    cur.close()
    conn.close()
    return count
```

### 5.4 Tree JSON Removal (recursive)

```python
def remove_from_tree(tree: dict, call_id: str) -> int:
    removed = 0
    pool = tree.get("sentence_pool", [])
    new_pool = []
    for s in pool:
        sid = s.get("script_id", "")
        src_ids = s.get("source_call_ids", [])
        if sid.startswith(f"{call_id}_t") or call_id in src_ids:
            removed += 1
        else:
            new_pool.append(s)
    tree["sentence_pool"] = new_pool
    for child in tree.get("children", []):
        removed += remove_from_tree(child, call_id)
    return removed
```

### 5.5 Overlay JSON Removal

```python
def remove_from_overlay(data: dict, call_id: str) -> int:
    removed = 0
    for node_id in list(data.get("augmentations", {}).keys()):
        node_aug = data["augmentations"][node_id]
        sentences = node_aug.get("sentences", [])
        new_sentences = []
        for s in sentences:
            sid = s.get("script_id", "")
            src_ids = s.get("source_call_ids", [])
            if sid.startswith(f"{call_id}_t") or call_id in src_ids:
                removed += 1
            else:
                new_sentences.append(s)
        if new_sentences:
            node_aug["sentences"] = new_sentences
        else:
            del data["augmentations"][node_id]
    return removed
```

### 5.6 Atomic File Write

```python
def atomic_write_json(path: str, data: dict):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.rename(tmp, path)
```

### 5.7 JSONL Removal

```python
def remove_from_jsonl(path: str, call_id: str, dry_run: bool) -> int:
    removed = 0
    kept_lines = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if obj.get("call_id") == call_id:
                    removed += 1
                    continue
            except json.JSONDecodeError:
                pass
            kept_lines.append(line)
    if not dry_run and removed > 0:
        with open(path, "w", encoding="utf-8") as f:
            for line in kept_lines:
                f.write(line + "\n")
    return removed
```

### 5.8 Summary Output

```
Removing call_id 9999104332181960013
══════════════════════════════════════════════════
Source                                    Removed
──────────────────────────────────────────────────
DB sentences                                  3
augmented_sentences.json                      3
decision_tree_scored.json                     0
decision_tree.json                            0
dialog_records.json                           0
merge_decisions.json                          0
matched_data.jsonl                            0
embedding_cache.json                          0
ids.md                                        0
──────────────────────────────────────────────────
Total removed:                                6

✅ Done (dry-run — no files modified)
```

---

## 6. Data Source Registry

```python
FILE_SOURCES = [
    ("augmented_sentences.json", "src/f016_sentence_augmentation/data/augmented_sentences.json", remove_from_overlay_file),
    ("decision_tree_scored.json", "src/f005_context_scoring/data/decision_tree_scored.json", remove_from_tree_file),
    ("decision_tree.json", "src/f004_decision_tree/data/decision_tree.json", remove_from_tree_file),
    ("dialog_records.json", "src/f004_decision_tree/data/dialog_records.json", remove_from_dialog_records_file),
    ("merge_decisions.json", "src/f004_decision_tree/data/merge_decisions.json", remove_from_merge_decisions_file),
    ("matched_data.jsonl", "data/data_input/matched_data.jsonl", remove_from_jsonl_file),
    ("embedding_cache.json", "old_files/embedding_cache.json", remove_from_embedding_cache_file),
    ("ids.md", "old_files/ids.md", remove_from_ids_file),
]
```

All paths are relative to the project root (parent of `src/`).

---

## 7. Edge Cases & Safeguards

| Case | Handling |
|------|----------|
| call_id not 19 digits | Error, exit 1 |
| File not found | Warn, skip, count = 0 |
| DB connection fails | Warn, skip, count = 0 |
| No matches anywhere | Print "No entries found for call_id {C}" |
| `--dry-run` | Read all sources, report counts, write nothing |
| Overlay node block becomes empty | Remove the node key from `augmentations` |
| Tree node pool becomes empty | Leave the node in place (it's still a valid tree node) |
| DB transaction fails | Rollback, report error, continue with files |
| Atomic write | Write to `.tmp` file, then `os.rename()` for atomicity |

---

## 8. What This Does NOT Touch

| Source | Why skipped |
|--------|-------------|
| `.py` data files (7 files) | Pipeline intermediates, regenerable from raw data |
| DB `nodes` table | Nodes are tree structure, not call-specific |
| `config.md` | No call_id references |
| `*.csv` label files | No call_id column |

---

## 9. Step-by-Step Implementation Order

| Step | What | Verify |
|------|------|--------|
| 1 | Write `test_remove_call_id.py` with tests for each remover function | Tests fail (RED) |
| 2 | Implement `remove_call_id.py` | Tests pass (GREEN) |
| 3 | `--dry-run` on existing augmented call_id | Shows 3 DB + 3 overlay = 6 |
| 4 | `--dry-run` on existing real call_id | Shows counts in tree JSON + DB |
| 5 | `--dry-run` on non-existent call_id | Shows 0 everywhere |
| 6 | Actual removal of augmented call_id | DB drops to 1719, overlay drops to 3 sentences |
| 7 | Re-insert and verify roundtrip | DB back to 1722, overlay back to 6 |

---

## 10. Test Plan

### Unit Tests (`test_remove_call_id.py`)

- `validate_call_id`: accepts 19-digit string, rejects wrong length / non-digit
- `remove_from_tree`: removes entries by `script_id` prefix and `source_call_ids`, recursive
- `remove_from_overlay`: removes entries, drops empty node blocks
- `remove_from_dialog_records`: removes by `call_id` field
- `remove_from_merge_decisions`: removes by key prefix
- `remove_from_jsonl`: removes by `call_id` JSON key
- `remove_from_embedding_cache`: removes by key prefix
- `remove_from_ids`: removes matching lines
- `remove_from_db`: mock psycopg2, verify SQL pattern

### Integration Tests

- `--dry-run` on `9999104332181960013` → 3 DB + 3 overlay
- `--dry-run` on `2346089320444241687` → counts in DB + tree JSONs + dialog records + merge decisions + matched_data.jsonl
- `--dry-run` on `9999999999999999999` (non-existent) → 0 everywhere
