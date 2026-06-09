"""
Common utilities shared across agent-memory scripts.
Do NOT import host-specific libraries here.
"""
import os
import hashlib
import json
import sys
from pathlib import Path
from typing import Optional

MODULE_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = MODULE_ROOT / "schemas"
LOCKS_DIR = Path("src/.agent-memory/locks")


def load_yaml_frontmatter(filepath: Path) -> tuple[dict, str]:
    """Parse YAML frontmatter from a Markdown file.

    Returns (frontmatter_dict, body_text).
    Frontmatter is between the first and second '---' lines.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, content

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return {}, content

    # Simple YAML parsing (no PyYAML dependency by design)
    frontmatter_lines = lines[1:end_idx]
    fm = _parse_simple_yaml(frontmatter_lines)
    body = "\n".join(lines[end_idx + 1:])
    return fm, body


def _parse_simple_yaml(lines: list[str]) -> dict:
    """Parse a minimal YAML subset: key: value, lists [a, b], and nested objects."""
    result = {}
    current_key = None
    current_list = []
    in_list = False
    in_nested = False
    nested_key = None
    nested_dict = {}

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Nested key (indented)
        if line.startswith("  ") and ":" in stripped and not stripped.startswith("-"):
            if in_list:
                result[current_key] = current_list
                in_list = False
                current_list = []

            nk, nv = stripped.split(":", 1)
            nk = nk.strip()
            nv = nv.strip().strip('"').strip("'")
            if nv == "":
                in_nested = True
                nested_key = nk
                nested_dict = {}
            else:
                if current_key:
                    if not isinstance(result.get(current_key), dict):
                        result[current_key] = {}
                    result[current_key][nk] = _parse_value(nv)
            continue

        # List item
        if stripped.startswith("- "):
            in_list = True
            current_list.append(stripped[2:].strip().strip('"').strip("'"))
            continue

        # Top-level key
        if ":" in stripped:
            if in_list:
                result[current_key] = current_list
                in_list = False
                current_list = []

            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if value.startswith("[") and value.endswith("]"):
                inner = value[1:-1]
                if inner.strip():
                    result[key] = [x.strip().strip('"').strip("'") for x in inner.split(",")]
                else:
                    result[key] = []
            elif value == "":
                current_key = key
                result[key] = {}
            else:
                result[key] = _parse_value(value)

    if in_list and current_key:
        result[current_key] = current_list

    return result


def _parse_value(v: str):
    """Parse a YAML scalar value."""
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    if v.lower() in ("null", "~", ""):
        return None
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v


def compute_content_hash(filepath: Path) -> str:
    """Compute SHA-256 hash of file content."""
    with open(filepath, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def ensure_dir(path: Path) -> None:
    """Create directory if it doesn't exist."""
    path.mkdir(parents=True, exist_ok=True)


def write_json(data: dict, filepath: Path) -> None:
    """Write JSON to file with deterministic key ordering."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def read_json(filepath: Path) -> dict:
    """Read JSON from file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def fail(msg: str, code: int = 1) -> None:
    """Print error and exit."""
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)
