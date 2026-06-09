#!/usr/bin/env python3
"""
memory-doctor — Thin dispatcher for agent-memory diagnostics.

Purpose: Dispatch to doctor-index, doctor-locks, doctor-schemas, doctor-tombstones.
         Each sub-check is a separate tiny script. This file only dispatches.
Invoker: manual diagnostics, CI health checks.
Related tests: tests/test_migration.py

Input:  --check <all|index|locks|schemas|tombstones>   What to diagnose (default: all)
        --root <PATH>                                   Repo root (default: .)

Output: Aggregated diagnostic report to stdout.
Exit:   0 if healthy, 1 if issues found.
"""
import argparse
import sys
import subprocess
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent

CHECKS = {
    "index": "doctor-index",
    "locks": "doctor-locks",
    "schemas": "doctor-schemas",
    "tombstones": "doctor-tombstones",
}


def run_check(name: str, root: str) -> tuple[str, bool, str]:
    """Run a single diagnostic check. Returns (name, healthy, output)."""
    script = SCRIPTS_DIR / CHECKS[name]
    result = subprocess.run(
        [sys.executable, str(script), "--root", root],
        capture_output=True, text=True,
    )
    return name, result.returncode == 0, result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description="Dispatch agent-memory diagnostics")
    parser.add_argument("--check", default="all", choices=["all", "index", "locks", "schemas", "tombstones"])
    parser.add_argument("--root", default=".", help="Repo root")
    args = parser.parse_args()

    to_check = list(CHECKS.keys()) if args.check == "all" else [args.check]
    results = []
    errors = 0

    for check_name in to_check:
        name, healthy, output = run_check(check_name, args.root)
        status = "PASS" if healthy else "FAIL"
        results.append((name, status, output))
        if not healthy:
            errors += 1

    print("=== Memory Doctor Report ===")
    for name, status, output in results:
        print(f"[{status}] {name}: {output}")

    print(f"\nChecks: {len(results)} run, {errors} failed")
    sys.exit(1 if errors > 0 else 0)


if __name__ == "__main__":
    main()
