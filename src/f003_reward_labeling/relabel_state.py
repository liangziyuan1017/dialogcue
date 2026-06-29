import csv
import os
from pathlib import Path
from collections import Counter

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "data_labels"


def _load_relabel_map(csv_path: str) -> dict[str, str]:
    mapping = {}
    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            return mapping
        new_label_idx = None
        for i, col in enumerate(header):
            if col == "new_label":
                new_label_idx = i
                break
        if new_label_idx is None:
            new_label_idx = len(header) - 1
        tag_idx = 0
        for row in reader:
            tag = row[tag_idx]
            new_label = row[new_label_idx] if new_label_idx < len(row) else "unclassified"
            mapping[tag] = new_label
    return mapping


def load_fact_map(csv_path: str | None = None) -> dict[str, str]:
    path = csv_path or str(_DATA_DIR / "facts_relabeled.csv")
    return _load_relabel_map(path)


def load_emotion_map(csv_path: str | None = None) -> dict[str, str]:
    path = csv_path or str(_DATA_DIR / "emotions_relabeled.csv")
    return _load_relabel_map(path)


def _relabel_list(items: list[str], mapping: dict[str, str]) -> list[str]:
    result = []
    seen = set()
    for item in items:
        new = mapping.get(item, item)
        if new not in seen:
            result.append(new)
            seen.add(new)
    return result


def relabel_record(record: dict, fact_map: dict[str, str], emotion_map: dict[str, str]) -> dict:
    for turn in record.get("turns_annotated", []):
        state = turn.get("state", {})
        if "facts" in state:
            state["facts"] = _relabel_list(state["facts"], fact_map)
        if "emotions" in state:
            state["emotions"] = _relabel_list(state["emotions"], emotion_map)
    return record


def relabel_all(records: list[dict], fact_map: dict[str, str] | None = None,
                emotion_map: dict[str, str] | None = None) -> tuple[list[dict], dict]:
    if fact_map is None:
        fact_map = load_fact_map()
    if emotion_map is None:
        emotion_map = load_emotion_map()

    fact_relabel_count = Counter()
    emotion_relabel_count = Counter()
    fact_passthrough = Counter()
    emotion_passthrough = Counter()

    relabeled = []
    for record in records:
        for turn in record.get("turns_annotated", []):
            state = turn.get("state", {})
            for f in state.get("facts", []):
                new = fact_map.get(f)
                if new and new != f:
                    fact_relabel_count[f] += 1
                else:
                    fact_passthrough[f] += 1
            for e in state.get("emotions", []):
                new = emotion_map.get(e)
                if new and new != e:
                    emotion_relabel_count[e] += 1
                else:
                    emotion_passthrough[e] += 1
        relabeled.append(relabel_record(record, fact_map, emotion_map))

    stats = {
        "facts_relabeled": dict(fact_relabel_count),
        "facts_passthrough": dict(fact_passthrough),
        "emotions_relabeled": dict(emotion_relabel_count),
        "emotions_passthrough": dict(emotion_passthrough),
        "fact_map_size": len(fact_map),
        "emotion_map_size": len(emotion_map),
    }
    return relabeled, stats
