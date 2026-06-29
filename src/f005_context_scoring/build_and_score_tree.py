import argparse
import importlib.util
import json
import os
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR.parent / "data"
OUTPUT_DIR = DATA_DIR / "data_output"


def _load_py_results(path: Path) -> list[dict]:
    spec = importlib.util.spec_from_file_location("results_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.results


def _write_py_results(results: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("results = ")
        text = json.dumps(results, ensure_ascii=False, indent=2)
        text = text.replace(": null", ": None").replace(": true", ": True").replace(": false", ": False")
        f.write(text)
        f.write("\n")


def run(args) -> None:
    ts = lambda: f"[{datetime.now():%Y-%m-%d %H:%M:%S}]"

    if args.merged_file:
        merged = args.merged_file.resolve()
    else:
        merged = OUTPUT_DIR / "output_merged.py"
    if not merged.exists():
        print(f"Merged file not found: {merged}")
        return

    records = _load_py_results(merged)
    print(f"{ts()} Loaded {len(records)} records from {merged.name}")

    # ── F000: analyze_collector_turns ──────────────────────────────────────
    print(f"\n{ts()} F000: analyze_collector_turns")
    import f003_reward_labeling.analyze_collector_turns as act
    collector_result = act.analyze_collector_turns(records)
    collector_out = BASE_DIR / "f003_reward_labeling" / "data" / "collector_analysis.json"
    with open(collector_out, "w", encoding="utf-8") as f:
        json.dump(collector_result, f, ensure_ascii=False, indent=2)
    print(f"  → {collector_out.name}  ({len(collector_result.get('collector_actions', []))} action groups)")

    # ── F000: analyze_customer_turns ───────────────────────────────────────
    print(f"\n{ts()} F000: analyze_customer_turns")
    import f003_reward_labeling.analyze_customer_turns as acust
    customer_result = acust.analyze_customer_turns(records)
    customer_out = BASE_DIR / "f003_reward_labeling" / "data" / "customer_analysis.json"
    with open(customer_out, "w", encoding="utf-8") as f:
        json.dump(customer_result, f, ensure_ascii=False, indent=2)
    print(f"  → {customer_out.name}  (facts: {len(customer_result.get('facts', []))}, emotions: {len(customer_result.get('emotions', []))})")

    # ── F001: align_schema ─────────────────────────────────────────────────
    print(f"\n{ts()} F001: align_schema")
    import f001_schema_alignment.align_schema as als
    aligned = als.align_all(records)
    aligned_out = BASE_DIR / "f001_schema_alignment" / "data" / "output_aligned.py"
    _write_py_results(aligned, aligned_out)
    print(f"  → {aligned_out.name}  ({len(aligned)} records)")

    # ── F003: reward_label ─────────────────────────────────────────────────
    print(f"\n{ts()} F003: reward_label")
    import f003_reward_labeling.reward_label as rl
    rewarded = rl.label_all(aligned)
    reward_out = BASE_DIR / "f003_reward_labeling" / "data" / "output_rewarded.py"
    _write_py_results(rewarded, reward_out)
    reward_count = sum(1 for r in rewarded if r.get("reward") == 1)
    print(f"  → {reward_out.name}  (R=1: {reward_count}/{len(rewarded)})")

    # ── F004: build_decision_tree ──────────────────────────────────────────
    print(f"\n{ts()} F004: build_decision_tree")
    import f004_decision_tree.build_decision_tree as bdt
    tree_path = BASE_DIR / "f004_decision_tree" / "data" / "decision_tree.json"
    node_count = bdt.write_decision_tree(rewarded, output_path=str(tree_path))
    print(f"  → {tree_path.name}  ({node_count} nodes)")

    # ── F005: score_tree ───────────────────────────────────────────────────
    print(f"\n{ts()} F005: score_tree")
    import f005_context_scoring.score_tree as st
    with open(tree_path, encoding="utf-8") as f:
        tree = json.load(f)
    context_lookup = st.build_context_lookup(aligned)
    reward_lookup = st.build_reward_lookup(rewarded)
    customer_info_lookup = st.build_customer_info_lookup(rewarded)
    turns_lookup = st.build_turns_lookup()
    conv_ctx_lookup = st.build_conversation_context_lookup(tree, turns_lookup)
    scored = st.score_tree(tree, context_lookup, reward_lookup, customer_info_lookup, conv_ctx_lookup)
    scored_path = BASE_DIR / "f005_context_scoring" / "data" / "decision_tree_scored.json"
    with open(scored_path, "w", encoding="utf-8") as f:
        json.dump(scored, f, indent=2, ensure_ascii=False)
    sentence_count = 0
    def _count(node):
        nonlocal sentence_count
        sentence_count += len(node.get("sentence_pool", []))
        for c in node.get("children", []):
            _count(c)
    _count(scored)
    print(f"  → {scored_path.name}  ({sentence_count} scored sentences)")

    print(f"\n{ts()} Done.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run analysis → align → reward → decision tree → score pipeline"
    )
    parser.add_argument(
        "--merged-file", type=Path, default=None,
        help="Path to merged output (default: data/data_output/output_merged.py)",
    )
    run(parser.parse_args())


if __name__ == "__main__":
    main()
