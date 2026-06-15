import importlib.util
import os


def _load_output_manual():
    data_path = os.path.join(os.path.dirname(__file__), "output_manual.py")
    spec = importlib.util.spec_from_file_location("output_manual", data_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.results


def load_records():
    return _load_output_manual()


def get_turns_by_role(records, role):
    result = []
    for record in records:
        call_id = record.get("call_id", "")
        for i, turn in enumerate(record["response"]["dialog"]):
            if turn["role"] == role:
                result.append((turn, {"call_id": call_id, "turn_index": i}))
    return result
