import importlib.util
import tempfile
from pathlib import Path

from f005_context_scoring.build_and_score_tree import _write_py_results as _write_bst
from whole_pipeline import _write_py_results as _write_wp


def _load_py_results(path: Path) -> list[dict]:
    spec = importlib.util.spec_from_file_location("results_mod", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.results


def _round_trip(write_fn, original):
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        path = Path(f.name)
    try:
        write_fn(original, path)
        return _load_py_results(path)
    finally:
        path.unlink()


def test_whole_pipeline_round_trip_preserves_null_literal_in_string():
    original = [{"script_text": 'value with ": null" inside', "score": 0.5, "flag": True, "nothing": None}]
    assert _round_trip(_write_wp, original) == original


def test_build_and_score_round_trip_preserves_null_literal_in_string():
    original = [{"script_text": 'value with ": null" inside', "score": 0.5, "flag": True, "nothing": None}]
    assert _round_trip(_write_bst, original) == original


def test_whole_pipeline_round_trip_nested_and_unicode():
    original = [
        {"facts": ["a", "b"], "nested": {"x": None, "y": [True, False]}, "text": "客户说：我没钱还"},
        {"empty": "", "num": 42},
    ]
    assert _round_trip(_write_wp, original) == original


def test_build_and_score_round_trip_nested_and_unicode():
    original = [
        {"facts": ["a", "b"], "nested": {"x": None, "y": [True, False]}, "text": "客户说：我没钱还"},
        {"empty": "", "num": 42},
    ]
    assert _round_trip(_write_bst, original) == original
