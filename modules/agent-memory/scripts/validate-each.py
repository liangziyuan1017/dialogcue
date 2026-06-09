#!/usr/bin/env python3
"""
validate-each — Validate a single document's frontmatter.

Purpose: Single-file validation. The workflow iterates over files and calls this per file.
         No batch orchestration — orchestration belongs in the workflow layer.
Invoker: memory-bootstrap workflow (called per file in a loop).
Related tests: tests/test_bootstrap_memory.py, tests/test_schemas.py

Input:  --file <PATH>              Single file to validate
        --lint-script <PATH>       Path to frontmatter-lint script (default: sibling script)
        --schema <NAME>            (optional) Additional schema to validate

Output: JSON validation result to stdout.
Exit:   0 if valid, 1 if violations found.
"""
import argparse
import sys
import json
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Validate a single document's frontmatter")
    parser.add_argument("--file", required=True, help="File path to validate")
    parser.add_argument("--lint-script", default=str(Path(__file__).parent / "frontmatter-lint.py"),
                        help="Path to frontmatter-lint script")
    parser.add_argument("--schema", default=None, choices=["lesson"], help="Additional schema to validate")
    args = parser.parse_args()

    cmd = [sys.executable, str(args.lint_script), "--file", args.file]
    if args.schema:
        cmd.extend(["--schema", args.schema])

    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        output = json.loads(result.stdout)
        output["file"] = args.file
        print(json.dumps(output, indent=2))
        sys.exit(0 if output.get("valid", False) else 1)
    except json.JSONDecodeError:
        print(json.dumps({"file": args.file, "valid": False, "violations": [f"parse error: {result.stderr}"]}))
        sys.exit(1)


if __name__ == "__main__":
    main()
