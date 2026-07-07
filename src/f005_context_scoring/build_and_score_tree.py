import argparse
import importlib.util
import json
import pprint
from datetime import datetime
from pathlib import Path

from f007_infrastructure.logging import get_logger as _get_logger

_log = _get_logger(__name__)

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
        f.write(pprint.pformat(results, width=120))
        f.write("\n")


def run(args) -> None:
    def ts():
        return f"[{datetime.now():%Y-%m-%d %H:%M:%S}]"

    if args.merged_file:
        merged = args.merged_file.resolve()
    else:
        merged = OUTPUT_DIR / "output_merged.py"
    if not merged.exists():
        _log.info(f"Merged file not found: {merged}")
        return

    records = _load_py_results(merged)
    seen_call_ids = set()
    deduped = []
    for r in records:
        cid = r.get("call_id")
        if cid in seen_call_ids:
            continue
        seen_call_ids.add(cid)
        deduped.append(r)
    if len(deduped) < len(records):
        _log.info(f"{ts()} Deduped {len(records)} -> {len(deduped)} records by call_id")
    records = deduped
    _log.info(f"{ts()} Loaded {len(records)} records from {merged.name}")

    # ── F000: discover_keywords (single LLM pass) ─────────────────────────
    _log.info(f"\n{ts()} F000: discover_keywords")
    import f000_keyword_discovery.discover_keywords as dk
    taxonomy = dk.discover_keywords(records)
    _log.info(f"  → facts: {len(taxonomy.get('facts', []))}, emotions: {len(taxonomy.get('emotions', []))}, actions: {len(taxonomy.get('collector_actions', []))}")

    # ── F000: aggregation from taxonomy ────────────────────────────────────
    collector_result = {"collector_actions": taxonomy.get("collector_actions", [])}
    collector_out = BASE_DIR / "f003_reward_labeling" / "data" / "collector_analysis.json"
    with open(collector_out, "w", encoding="utf-8") as f:
        json.dump(collector_result, f, ensure_ascii=False, indent=2)
    _log.info(f"  → {collector_out.name}  ({len(collector_result.get('collector_actions', []))} action groups)")

    customer_result = {"facts": taxonomy.get("facts", []), "emotions": taxonomy.get("emotions", [])}
    customer_out = BASE_DIR / "f003_reward_labeling" / "data" / "customer_analysis.json"
    with open(customer_out, "w", encoding="utf-8") as f:
        json.dump(customer_result, f, ensure_ascii=False, indent=2)
    _log.info(f"  → {customer_out.name}  (facts: {len(customer_result.get('facts', []))}, emotions: {len(customer_result.get('emotions', []))})")

    # ── F001: align_schema ─────────────────────────────────────────────────
    _log.info(f"\n{ts()} F001: align_schema")
    import f001_schema_alignment.align_schema as als
    aligned = als.align_all(records)
    aligned_out = BASE_DIR / "f001_schema_alignment" / "data" / "output_aligned.py"
    _write_py_results(aligned, aligned_out)
    _log.info(f"  → {aligned_out.name}  ({len(aligned)} records)")

    # ── F004: write_dialog_records ─────────────────────────────────────────
    import f004_decision_tree.build_decision_tree as bdt
    dialog_path = BASE_DIR / "f004_decision_tree" / "data" / "dialog_records.json"
    dialog_count = bdt.write_dialog_records(aligned, output_path=str(dialog_path))
    _log.info(f"  → {dialog_path.name}  ({dialog_count} records)")

    # ── F003: reward_label ─────────────────────────────────────────────────
    _log.info(f"\n{ts()} F003: reward_label")
    import f003_reward_labeling.reward_label as rl
    rewarded = rl.label_all(aligned)
    reward_out = BASE_DIR / "f003_reward_labeling" / "data" / "output_rewarded.py"
    _write_py_results(rewarded, reward_out)
    reward_count = sum(1 for r in rewarded if r.get("reward") == 1)
    _log.info(f"  → {reward_out.name}  (R=1: {reward_count}/{len(rewarded)})")

    # ── F004: build_decision_tree ──────────────────────────────────────────
    _log.info(f"\n{ts()} F004: build_decision_tree")
    import f004_decision_tree.build_decision_tree as bdt
    tree_path = BASE_DIR / "f004_decision_tree" / "data" / "decision_tree.json"
    if args.rebuild or not tree_path.exists():
        node_count = bdt.write_decision_tree(rewarded, output_path=str(tree_path))
    else:
        node_count = bdt.merge_dialogs(str(tree_path), rewarded)
        node_count = bdt._count_nodes(node_count) if isinstance(node_count, dict) else node_count
    _log.info(f"  → {tree_path.name}  ({node_count} nodes)")

    # ── F005: score_tree ───────────────────────────────────────────────────
    _log.info(f"\n{ts()} F005: score_tree")
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
    _log.info(f"  → {scored_path.name}  ({sentence_count} scored sentences)")

    _log.info(f"\n{ts()} Done.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run analysis → align → reward → decision tree → score pipeline"
    )
    parser.add_argument(
        "--merged-file", type=Path, default=None,
        help="Path to merged output (default: data/data_output/output_merged.py)",
    )
    parser.add_argument(
        "--rebuild", action="store_true", default=False,
        help="Force full rebuild of decision tree from scratch",
    )
    run(parser.parse_args())


if __name__ == "__main__":
    main()
