import re
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[3] / "pyproject.toml"


def _requires_python():
    text = PYPROJECT.read_text()
    m = re.search(r'requires-python\s*=\s*"([^"]+)"', text)
    return m.group(1)


def test_requires_python_allows_3_11():
    spec = _requires_python()
    assert "3.11" in spec or "3.12" in spec, f"requires-python={spec} does not allow 3.11+"


def test_requires_python_not_pinned_to_3_14_only():
    spec = _requires_python()
    assert "<3.15" not in spec, f"requires-python={spec} over-pinned to <3.15"
