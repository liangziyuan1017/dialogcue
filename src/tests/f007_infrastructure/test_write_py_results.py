import tempfile
from pathlib import Path

from f005_context_scoring.build_and_score_tree import write_jsonl as _write_bst
from f007_infrastructure.jsonl_utils import load_jsonl, write_jsonl as _write_wp


def _round_trip(write_fn, original):
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    try:
        write_fn(path, original)
        return load_jsonl(path)
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
