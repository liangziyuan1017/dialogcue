import json
import tempfile
from pathlib import Path

from f007_infrastructure.jsonl_utils import load_jsonl, write_jsonl


def test_write_then_load_round_trip():
    records = [
        {"acNo": "001", "dialog": [{"role": "customer", "text": "你好"}], "score": 0.5},
        {"acNo": "002", "dialog": [], "score": None},
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    try:
        write_jsonl(path, records)
        loaded = load_jsonl(path)
        assert loaded == records
    finally:
        path.unlink()


def test_load_jsonl_returns_list_of_dict():
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps({"a": 1}) + "\n")
        f.write(json.dumps({"b": 2}) + "\n")
        path = Path(f.name)
    try:
        loaded = load_jsonl(path)
        assert isinstance(loaded, list)
        assert len(loaded) == 2
        assert loaded[0] == {"a": 1}
        assert loaded[1] == {"b": 2}
    finally:
        path.unlink()


def test_write_jsonl_append_mode():
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    try:
        write_jsonl(path, [{"a": 1}])
        write_jsonl(path, [{"b": 2}], append=True)
        loaded = load_jsonl(path)
        assert loaded == [{"a": 1}, {"b": 2}]
    finally:
        path.unlink()


def test_load_jsonl_empty_file():
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    try:
        loaded = load_jsonl(path)
        assert loaded == []
    finally:
        path.unlink()


def test_round_trip_unicode_and_nested():
    records = [
        {"facts": ["a", "b"], "nested": {"x": None, "y": [True, False]}, "text": "客户说：我没钱还"},
        {"empty": "", "num": 42},
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    try:
        write_jsonl(path, records)
        loaded = load_jsonl(path)
        assert loaded == records
    finally:
        path.unlink()
