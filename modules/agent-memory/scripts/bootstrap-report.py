#!/usr/bin/env python3
"""
bootstrap-report — Produce a human-readable bootstrap summary.

Purpose: Summarize bootstrap results.
Invoker: memory-bootstrap workflow.
Related tests: tests/test_bootstrap_memory.py

Input:  --discovered <N> --validated <N> --indexed <N>

Output: Formatted bootstrap report to stdout.
Exit:   0 always.
"""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Format bootstrap report")
    parser.add_argument("--discovered", type=int, required=True, help="Docs discovered")
    parser.add_argument("--validated", type=int, required=True, help="Docs validated")
    parser.add_argument("--indexed", type=int, required=True, help="Docs indexed")
    args = parser.parse_args()

    if args.discovered == 0:
        print("No structured durable docs found. Index is empty but valid.")
    else:
        status = "complete" if args.validated == args.discovered else "partial"
        print(f"Bootstrap {status}. {args.discovered} durable docs discovered, "
              f"{args.validated} validated, {args.indexed} indexed, index ready.")

    sys.exit(0)


if __name__ == "__main__":
    main()
