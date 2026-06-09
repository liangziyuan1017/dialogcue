import json
import os
from src.load_data import load_records
from src.analyze_customer_turns import analyze_customer_turns
from src.analyze_collector_turns import analyze_collector_turns
from src.define_willingness_levels import define_willingness_levels


def discover_keywords(output_path: str = None) -> dict:
    records = load_records()

    customer_result = analyze_customer_turns(records)
    collector_result = analyze_collector_turns(records)
    willingness_levels = define_willingness_levels(records)

    taxonomy = {
        "facts": customer_result["facts"],
        "emotions": customer_result["emotions"],
        "willingness_levels": willingness_levels,
        "collector_actions": collector_result["collector_actions"],
    }

    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), "state_keywords.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(taxonomy, f, ensure_ascii=False, indent=2)

    return taxonomy
