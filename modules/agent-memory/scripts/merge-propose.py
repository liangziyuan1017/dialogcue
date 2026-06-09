#!/usr/bin/env python3
"""
merge-propose — Propose a merge of two duplicate knowledge entries.

Purpose: Combine two entries into one, preserving source_ids from both.
         ID allocation is done by the workflow, passed via --new-id.
         No cross-script orchestration — the workflow handles ID allocation.
Invoker: memory-prune workflow.
Related tests: tests/test_prune_memory.py

Input:  --source1 <ID>         First entry ID
        --source2 <ID>         Second entry ID
        --root <PATH>          Root directory for docs/
        --new-id <ID>          Pre-allocated ID for merged document (workflow provides this)
        --now <ISO_TIMESTAMP>  Override current timestamp for deterministic replay

Output: JSON merge proposal with merged doc content.
Exit:   0 on success, 1 on error.
"""
import argparse
import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_utilities import load_yaml_frontmatter


def find_doc(doc_id: str, root: str) -> Path | None:
    """Find a document by ID in docs/."""
    root_path = Path(root)
    for subdir in ["docs/decisions", "docs/lessons", "docs/summaries"]:
        full = root_path / subdir
        if full.is_dir():
            for f in full.rglob("*.md"):
                with open(f, "r", encoding="utf-8") as fh:
                    content = fh.read()
                if any(doc_id in line for line in content.split("\n")[0:10]):
                    return f
    return None


def propose_merge(source1: str, source2: str, root: str, new_id: str, now: datetime) -> dict:
    """Propose merging two entries. new_id is provided by the workflow."""
    doc1 = find_doc(source1, root)
    doc2 = find_doc(source2, root)

    if not doc1:
        return {"error": f"document not found: {source1}"}
    if not doc2:
        return {"error": f"document not found: {source2}"}

    fm1, _ = load_yaml_frontmatter(doc1)
    fm2, _ = load_yaml_frontmatter(doc2)

    source_ids = []
    for fm in [fm1, fm2]:
        sid_str = fm.get("source_ids", "")
        if sid_str:
            if isinstance(sid_str, str) and sid_str.startswith("["):
                try:
                    source_ids.extend(json.loads(sid_str))
                except json.JSONDecodeError:
                    source_ids.append(sid_str)
            else:
                source_ids.append(sid_str)
    source_ids.extend([source1, source2])

    today = now.strftime("%Y-%m-%d")

    merged_doc = f"""---
id: {new_id}
title: "Merged: {fm1.get('title', source1)} + {fm2.get('title', source2)}"
doc_kind: decision
status: draft
created: {today}
schema_version: 1
source_ids: {json.dumps(source_ids)}
merged_from: ["{source1}", "{source2}"]
---

# {new_id}: Merged Decision

## Originals Merged
- {source1}: {fm1.get('title', 'Untitled')}
- {source2}: {fm2.get('title', 'Untitled')}

## Combined Rationale

Original documents preserved with status: superseded and replaced_by: {new_id}.
All source_ids preserved: {source_ids}
"""

    return {
        "new_id": new_id,
        "merged_from": [source1, source2],
        "source_ids_preserved": source_ids,
        "merged_content": merged_doc,
    }


def main():
    parser = argparse.ArgumentParser(description="Propose merge of two entries (ID allocated by workflow)")
    parser.add_argument("--source1", required=True, help="First entry ID")
    parser.add_argument("--source2", required=True, help="Second entry ID")
    parser.add_argument("--root", required=True, help="Root directory")
    parser.add_argument("--new-id", required=True, help="Pre-allocated merged document ID (workflow provides)")
    parser.add_argument("--now", default=None, help="ISO timestamp for deterministic replay")
    args = parser.parse_args()

    now = datetime.fromisoformat(args.now) if args.now else datetime.now()
    result = propose_merge(args.source1, args.source2, args.root, args.new_id, now)
    print(json.dumps(result, indent=2))
    if "error" in result:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
