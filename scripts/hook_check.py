#!/usr/bin/env python3
"""
Hook compliance checker. Run after each chain step.
Verifies that required memory hooks were actually invoked.

Usage:
  python3 scripts/hook_check.py --step <skill>.<step> --feature Fxxx

Exit 0 = compliant, Exit 1 = violation
"""

import argparse
import json
import os
import sys
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(ROOT, "registry", "capabilities.yaml")
DECISIONS_DIR = os.path.join(ROOT, "docs", "decisions")
LESSONS_DIR = os.path.join(ROOT, "docs", "lessons")
MEMORY_INDEX = os.path.join(ROOT, ".agent-memory", "index.json")


def load_registry():
    with open(REGISTRY) as f:
        return yaml.safe_load(f)


def get_required_hooks(registry, step):
    caps = registry.get("capabilities", {})
    hooks = caps.get("clowder_dev_workflows", {}).get("memory_hooks", {})
    if step in hooks:
        return hooks[step]
    return None


def check_decisions_exist(feature_id):
    if not os.path.isdir(DECISIONS_DIR):
        return []
    found = []
    for fname in os.listdir(DECISIONS_DIR):
        if not fname.endswith(".md"):
            continue
        path = os.path.join(DECISIONS_DIR, fname)
        with open(path) as f:
            content = f.read()
        if f"feature_ids: [{feature_id}]" in content or f"[{feature_id}]" in content:
            found.append(fname)
    return found


def check_memory_index_fresh():
    if not os.path.exists(MEMORY_INDEX):
        return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", required=True, help="e.g. feat-lifecycle.design_gate")
    parser.add_argument("--feature", required=True, help="e.g. F000")
    args = parser.parse_args()

    registry = load_registry()
    required_hook = get_required_hooks(registry, args.step)

    if required_hook is None:
        print(f"PASS: no memory hook defined for {args.step}")
        return 0

    print(f"CHECK: {args.step} requires hook → {required_hook}")

    violations = []

    if required_hook == "decision-record":
        decisions = check_decisions_exist(args.feature)
        if not decisions:
            violations.append(f"No ADR found for {args.feature} — decision-record hook was skipped")
        else:
            print(f"  Found ADRs: {decisions}")

    elif required_hook == "memory-search":
        if not check_memory_index_fresh():
            violations.append("Memory index does not exist — memory-search hook was skipped")
        else:
            print("  Memory index exists")

    elif required_hook == "lesson-capture":
        if os.path.isdir(LESSONS_DIR) and os.listdir(LESSONS_DIR):
            print("  Lessons exist")
        else:
            print("  No lessons (may be correct if no bugs found)")

    elif required_hook == "memory-index":
        if not check_memory_index_fresh():
            violations.append("Memory index missing — memory-index hook was skipped")
        else:
            print("  Memory index exists")

    elif required_hook == "governance-review":
        print("  Governance review is informational — no artifact check")

    if violations:
        print(f"\nVIOLATION: {args.step}")
        for v in violations:
            print(f"  ❌ {v}")
        print(f"\nSTOP: Do not proceed to next chain step. Run the missing hook first.")
        return 1

    print(f"PASS: {args.step} hook compliance verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
