import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

CLI_ENTRYPOINTS = {
    "whole_pipeline.py",
    "build_tree_and_db.py",
    "launch_ui.py",
    "check_data_format.py",
    "serve_tree.py",
}


def _library_prints():
    result = subprocess.run(
        ["grep", "-rn", "print(", str(ROOT / "src"), "--include=*.py"],
        capture_output=True, text=True,
    )
    offending = []
    for line in result.stdout.splitlines():
        if "/tests/" in line:
            continue
        if "logging.py" in line:
            continue
        rel = line.split(":", 1)[0]
        if Path(rel).name in CLI_ENTRYPOINTS:
            continue
        offending.append(line)
    return offending


def test_no_print_in_library_modules():
    offending = _library_prints()
    assert not offending, f"print() found in library modules:\n" + "\n".join(offending)
