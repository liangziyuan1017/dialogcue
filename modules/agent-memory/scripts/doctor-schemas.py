#!/usr/bin/env python3
"""
doctor-schemas — Check for schema version drift.

Purpose: Verify all schema files use the same schema_version.
Invoker: memory-doctor (dispatcher).
"""
import argparse
import sys
from pathlib import Path

SCHEMAS_DIR = "modules/agent-memory/schemas"


def main():
    parser = argparse.ArgumentParser(description="Check schema version consistency")
    parser.add_argument("--root", default=".", help="Repo root")
    args = parser.parse_args()

    schemas_path = Path(args.root) / SCHEMAS_DIR
    if not schemas_path.exists():
        print("Schemas directory not found")
        sys.exit(1)

    versions = {}
    for schema_file in schemas_path.glob("*.yaml"):
        with open(schema_file) as f:
            for line in f:
                if "schema_version:" in line and not line.strip().startswith("#"):
                    versions[schema_file.name] = line.split(":", 1)[1].strip()
                    break

    unique = set(versions.values())
    if len(unique) > 1:
        print(f"Schema version drift: {versions}")
        sys.exit(1)
    print(f"All schemas at version {list(unique)[0]}")
    sys.exit(0)


if __name__ == "__main__":
    main()
