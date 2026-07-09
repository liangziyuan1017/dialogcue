import argparse
import json
import os
import sys

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_TESTS_DIR = os.path.join(os.path.dirname(__file__), "..", "tests", "f004_decision_tree")

if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from tree_checks import CheckResult, Report, check_tree as _check_tree, load_rewarded  # noqa: E402


def check_tree(tree, records=None, scored=False, scored_tree=None):
    return _check_tree(tree, records=records, scored=scored, scored_tree=scored_tree)


def main():
    parser = argparse.ArgumentParser(description="Check decision tree invariants")
    parser.add_argument("--scored", action="store_true", help="Also check F005 scoring invariants")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument("--only", default=None, help="Run only specific checks (comma-separated IDs)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show passing checks")
    parser.add_argument("--tree-path", default=None, help="Path to decision_tree.json")
    parser.add_argument("--scored-path", default=None, help="Path to decision_tree_scored.json")
    parser.add_argument("--no-records", action="store_true", help="Skip record-dependent checks")
    args = parser.parse_args()

    tree_path = args.tree_path or os.path.join(_DATA_DIR, "decision_tree.json")
    with open(tree_path, encoding="utf-8") as f:
        tree = json.load(f)

    scored_tree = None
    if args.scored:
        scored_path = args.scored_path or os.path.join(os.path.dirname(__file__), "..", "f005_context_scoring", "data", "decision_tree_scored.json")
        with open(scored_path, encoding="utf-8") as f:
            scored_tree = json.load(f)

    records = None
    if not args.no_records:
        try:
            records = load_rewarded()
        except Exception:
            records = None

    report = check_tree(tree, records=records, scored=args.scored, scored_tree=scored_tree)

    if args.only:
        only_ids = set(args.only.split(","))
        report.checks = [c for c in report.checks if c.id in only_ids]

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        for c in report.checks:
            if c.status == "pass" and not args.verbose:
                continue
            prefix = {"pass": "✓", "fail": "✗", "warn": "⚠", "skip": "○"}.get(c.status, "?")
            print(f"  {prefix} {c.id} [{c.severity}] {c.message}")
            for d in c.details[:5]:
                print(f"      - {d}")
        print(f"\n{report.summary()}")

    sys.exit(report.exit_code())


if __name__ == "__main__":
    main()
