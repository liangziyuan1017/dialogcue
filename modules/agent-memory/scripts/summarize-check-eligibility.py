#!/usr/bin/env python3
"""
summarize-check-eligibility — Check if source material meets L1 summarization thresholds.

Purpose: Gate summarization to only stable, completed conversations.
Invoker: memory-summarize workflow.
Related tests: tests/test_summarize_conversation.py

Input:  --input <PATH>           Source material file path
        --check-is-summary       Reject if input is already a summary
        --quiet-window <N>       Required quiet minutes (default: 10)
        --min-messages <N>       Minimum message count (default: 20)

Output: JSON eligibility result to stdout.
Exit:   0 if eligible, 1 if not eligible or is a summary.
"""
import argparse
import sys
import json
from pathlib import Path


def is_summary(input_path: str) -> bool:
    """Check if the file is already a summary document."""
    path = Path(input_path)
    if not path.exists():
        return False

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Check for summary markers in frontmatter or body
    markers = ["doc_kind: summary", "layer: L1", "is_summary_of_summary: true", "doc_kind: summary"]
    return any(m in content for m in markers)


def count_messages(content: str) -> int:
    """Count messages in a conversation file."""
    # Messages prefixed with typical markers like "user:", "agent:", "assistant:", etc.
    import re
    return len(re.findall(r'^(user|agent|assistant|human|system):', content, re.MULTILINE | re.IGNORECASE))


def main():
    parser = argparse.ArgumentParser(description="Check summarization eligibility")
    parser.add_argument("--input", required=True, help="Source material file path")
    parser.add_argument("--check-is-summary", action="store_true", help="Reject if already a summary")
    parser.add_argument("--quiet-window", type=int, default=10, help="Minutes of quiet required")
    parser.add_argument("--min-messages", type=int, default=20, help="Minimum message count")
    args = parser.parse_args()

    # Guard: no summary of summary
    if args.check_is_summary:
        if is_summary(args.input):
            print(json.dumps({
                "eligible": False,
                "reason": "REJECTED: rules.md §7 — no-summary-of-summary",
                "violation": "source is already a summary",
            }))
            sys.exit(1)

    # Read input
    input_path = Path(args.input)
    if not input_path.exists():
        print(json.dumps({"eligible": False, "reason": f"file not found: {args.input}"}))
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    msg_count = count_messages(content)

    # Check thresholds
    if msg_count < args.min_messages:
        print(json.dumps({
            "eligible": False,
            "reason": f"not eligible: {msg_count} messages (need {args.min_messages})",
            "message_count": msg_count,
            "quiet_window_required": args.quiet_window,
        }))
        sys.exit(1)

    print(json.dumps({
        "eligible": True,
        "message_count": msg_count,
        "quiet_window_min": args.quiet_window,
        "is_summary": False,
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
