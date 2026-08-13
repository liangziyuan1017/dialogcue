import os
from pathlib import Path

from f007_infrastructure.jsonl_utils import load_jsonl


def load_records():
    data_path = os.path.join(os.path.dirname(__file__), "data", "output_labeled.jsonl")
    return load_jsonl(Path(data_path))


def get_turns_by_role(records, role):
    turns = []
    for record in records:
        dialog = record["response"]["dialog"]
        for i, turn in enumerate(dialog):
            if turn["role"] == role:
                meta = {"call_id": record["call_id"], "turn_index": i}
                turns.append((turn, meta))
    return turns
