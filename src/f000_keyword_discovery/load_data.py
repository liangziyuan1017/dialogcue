import importlib.util
import os


def load_records():
    data_path = os.path.join(os.path.dirname(__file__), "data", "output_labeled.py")
    spec = importlib.util.spec_from_file_location("output_labeled", data_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.results


def get_turns_by_role(records, role):
    turns = []
    for record in records:
        dialog = record["response"]["dialog"]
        for i, turn in enumerate(dialog):
            if turn["role"] == role:
                meta = {"call_id": record["call_id"], "turn_index": i}
                turns.append((turn, meta))
    return turns
