#!/usr/bin/env python3
"""
write-durable — Write a durable document to the host project's docs/ directory.

Purpose: Append-first write with optimistic concurrency check.
Invoker: decision-record, lesson-capture, memory-summarize, memory-prune workflows.
Related tests: tests/test_write_decision.py, tests/test_write_lesson.py, tests/test_prune_memory.py

Input:  --path <PATH>                  Target file path (relative to host project root)
        --content <STRING|FILE>        Document content, or --content-file <PATH>
        --content-file <PATH>          Read content from a file
        --if-unmodified-since <TS>     (optional) Reject if file modified since ISO timestamp
        --update-frontmatter <JSON>    (optional) Merge these frontmatter updates
        --update-knowledge <JSON>      (optional) Merge these knowledge block updates

Output: JSON confirmation to stdout.
Exit:   0 on success, 1 on error, 2 on optimistic concurrency rejection.
"""
import argparse
import sys
import json
import os
from pathlib import Path
from datetime import datetime


def read_file_content(filepath: str) -> str:
    """Read file content."""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def write_file(filepath: str, content: str) -> None:
    """Write content to file, creating directories as needed."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def check_if_modified_since(filepath: str, since_ts: str) -> bool:
    """Check if file was modified since the given timestamp."""
    path = Path(filepath)
    if not path.exists():
        return False  # New file, no conflict
    try:
        mtime = os.path.getmtime(path)
        since = datetime.fromisoformat(since_ts).timestamp()
        return mtime > since
    except (ValueError, OSError):
        return False


def merge_frontmatter(existing_content: str, updates: dict) -> str:
    """Merge frontmatter updates into existing markdown content."""
    lines = existing_content.split("\n")
    if not lines or lines[0].strip() != "---":
        # No existing frontmatter, prepend
        fm_lines = ["---"]
        for k, v in updates.items():
            fm_lines.append(f"{k}: {v}")
        fm_lines.append("---")
        return "\n".join(fm_lines) + "\n" + existing_content

    # Find frontmatter boundaries
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return existing_content

    # Parse existing frontmatter
    existing_fm = {}
    for line in lines[1:end_idx]:
        line = line.strip()
        if ":" in line and not line.startswith("#"):
            k, v = line.split(":", 1)
            existing_fm[k.strip()] = v.strip().strip('"').strip("'")

    # Merge updates
    existing_fm.update(updates)

    # Rebuild frontmatter
    new_fm = ["---"]
    for k, v in existing_fm.items():
        if isinstance(v, str) and (" " in v or v == ""):
            new_fm.append(f'{k}: "{v}"')
        else:
            new_fm.append(f"{k}: {v}")
    new_fm.append("---")

    return "\n".join(new_fm) + "\n" + "\n".join(lines[end_idx + 1:])


def main():
    parser = argparse.ArgumentParser(description="Write durable document")
    parser.add_argument("--path", required=True, help="Target file path")
    parser.add_argument("--content", default=None, help="Document content string")
    parser.add_argument("--content-file", default=None, help="Read content from file")
    parser.add_argument("--if-unmodified-since", default=None, help="Reject if modified since ISO timestamp")
    parser.add_argument("--update-frontmatter", default=None, help="JSON frontmatter updates to merge")
    parser.add_argument("--update-knowledge", default=None, help="JSON knowledge block updates")
    args = parser.parse_args()

    # Optimistic concurrency check
    if args.if_unmodified_since:
        if check_if_modified_since(args.path, args.if_unmodified_since):
            print(json.dumps({
                "result": "rejected",
                "reason": f"document modified since {args.if_unmodified_since}; re-read and retry",
                "path": args.path,
            }))
            sys.exit(2)

    # Determine content
    if args.content_file:
        content = read_file_content(args.content_file)
    elif args.content:
        content = args.content
    elif args.update_frontmatter:
        # Update existing file's frontmatter
        try:
            existing = read_file_content(args.path)
        except FileNotFoundError:
            print(json.dumps({"error": f"file not found: {args.path}; cannot update frontmatter"}))
            sys.exit(1)
        updates = json.loads(args.update_frontmatter)
        content = merge_frontmatter(existing, updates)
    elif args.update_knowledge:
        try:
            existing = read_file_content(args.path)
        except FileNotFoundError:
            print(json.dumps({"error": f"file not found: {args.path}; cannot update knowledge"}))
            sys.exit(1)
        updates = json.loads(args.update_knowledge)
        # Knowledge block is in frontmatter; treat as frontmatter update
        content = merge_frontmatter(existing, {"knowledge": str(updates)})
    else:
        print(json.dumps({"error": "One of --content, --content-file, --update-frontmatter, or --update-knowledge is required"}))
        sys.exit(1)

    write_file(args.path, content)

    print(json.dumps({
        "result": "written",
        "path": args.path,
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
