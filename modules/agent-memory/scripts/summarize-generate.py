#!/usr/bin/env python3
"""
summarize-generate — Generate a durable summary segment from source material.

Purpose: Produce L1 summary with key decisions, lessons, resolved actions, open questions.
Invoker: memory-summarize workflow.
Related tests: tests/test_summarize_conversation.py

Input:  --source <PATH>          Source material file
        --layer <L1>             Summary layer (only L1 allowed)
        --output <PATH>          Output path for generated summary
        --now <ISO_TIMESTAMP>    Override current timestamp for deterministic replay

Output: Summary segment written to output path; JSON confirmation to stdout.
Exit:   0 on success, 1 on error.
"""
import argparse
import sys
import json
import re
from pathlib import Path
from datetime import datetime


def extract_key_items(content: str) -> dict:
    """Extract key decisions, lessons, actions, and questions from conversation text."""
    decisions = []
    lessons = []
    actions = []
    questions = []

    lines = content.split("\n")
    for line in lines:
        line_lower = line.lower()
        if any(w in line_lower for w in ["decided", "decision:", "adr", "we will use", "we chose"]):
            decisions.append(line.strip())
        elif any(w in line_lower for w in ["lesson", "learned", "pitfall", "don't repeat"]):
            lessons.append(line.strip())
        elif any(w in line_lower for w in ["action:", "todo:", "next step", "will do"]):
            actions.append(line.strip())
        elif "?" in line and len(line) > 20:
            questions.append(line.strip())

    return {
        "decisions": decisions[:5],
        "lessons": lessons[:5],
        "actions_resolved": actions[:5],
        "open_questions": questions[:5],
    }


def generate_summary(source_path: str, layer: str, now: datetime) -> str:
    """Generate a summary segment."""
    if layer != "L1":
        raise ValueError(f"Only L1 summarization is supported (rules.md §7 — no summary-of-summary); got: {layer}")

    with open(source_path, "r", encoding="utf-8") as f:
        content = f.read()

    items = extract_key_items(content)

    now_iso = now.isoformat()
    slug = Path(source_path).stem

    summary = f"""---
id: SUM-{now_iso[:10].replace('-', '')}-{now_iso[11:16].replace(':', '')}-{slug}
title: "Conversation Summary: {slug}"
doc_kind: summary
status: draft
created: {now_iso[:10]}
schema_version: 1
source_ids: ["{source_path}"]
layer: L1
is_summary_of_summary: false
---

# Conversation Summary: {slug}

## Key Decisions Referenced
"""
    for d in items["decisions"]:
        summary += f"- {d}\n"
    if not items["decisions"]:
        summary += "- None identified\n"

    summary += "\n## Key Lessons Referenced\n"
    for l in items["lessons"]:
        summary += f"- {l}\n"
    if not items["lessons"]:
        summary += "- None identified\n"

    summary += "\n## Actions Resolved\n"
    for a in items["actions_resolved"]:
        summary += f"- {a}\n"
    if not items["actions_resolved"]:
        summary += "- None identified\n"

    summary += "\n## Open Questions\n"
    for q in items["open_questions"]:
        summary += f"- {q}\n"
    if not items["open_questions"]:
        summary += "- None identified\n"

    summary += f"\n---\nGenerated: {now_iso}\nSource: {source_path}\nLayer: {layer}\n"

    return summary


def main():
    parser = argparse.ArgumentParser(description="Generate conversation summary")
    parser.add_argument("--source", required=True, help="Source material file")
    parser.add_argument("--layer", required=True, choices=["L1"], help="Summary layer (only L1)")
    parser.add_argument("--output", required=True, help="Output path for summary")
    parser.add_argument("--now", default=None, help="Override current timestamp (ISO format) for deterministic replay")
    args = parser.parse_args()

    now = datetime.fromisoformat(args.now) if args.now else datetime.now()

    try:
        summary = generate_summary(args.source, args.layer, now)
    except ValueError as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(summary)

    print(json.dumps({
        "result": "generated",
        "layer": args.layer,
        "output": str(output_path),
        "is_summary_of_summary": False,
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
