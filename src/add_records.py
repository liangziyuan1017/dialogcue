import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

from check_new_records import check_new_records
from f007_infrastructure.embeddings import EMBEDDING_DIM, embed_texts
from f007_infrastructure.logging import get_logger as _get_logger
from whole_pipeline import LLM_STEPS, _load_py_results, _write_py_results

_log = _get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
INPUT_DIR = DATA_DIR / "data_input"
OUTPUT_DIR = DATA_DIR / "data_output"


def _run_cleaning_step(script_path, data_file, output_file):
    infra_path = str(BASE_DIR / "f007_infrastructure")
    env = {**os.environ, "DATA_FILE": str(data_file), "OUTPUT_FILE": str(output_file),
           "PYTHONPATH": f"{str(BASE_DIR)}:{os.environ.get('PYTHONPATH', '')}"}
    wrapper = f"import sys; sys.path.append({infra_path!r}); import runpy; runpy.run_path({str(script_path)!r}, run_name='__main__')"
    result = subprocess.run([sys.executable, "-c", wrapper], env=env, cwd=str(DATA_DIR))
    if result.returncode != 0:
        raise RuntimeError(f"{script_path.name} failed with exit code {result.returncode}")


def _phase0_check(new_input):
    _log.info("Phase 0: Pre-check")
    new_ids, errors = check_new_records(new_input)
    if errors:
        for e in errors:
            _log.error(e)
        sys.exit(1)
    _log.info("Pre-check passed: %d new records", len(new_ids))
    return set(new_ids)


def _phase1a_clean(new_input):
    _log.info("Phase 1a: Cleaning stages 1-3")
    prev_output = new_input
    for step in LLM_STEPS[:3]:
        output_file = OUTPUT_DIR / step["default_output"]
        _run_cleaning_step(step["script"], prev_output, output_file)
        prev_output = output_file


def _phase1b_merge(new_input, new_ids):
    _log.info("Phase 1b: Merge extra fields")
    complete = _load_py_results(OUTPUT_DIR / "output_complete.py")
    merged_path = OUTPUT_DIR / "output_merged.py"
    merged = _load_py_results(merged_path) if merged_path.exists() else []
    existing_ids = {r["call_id"] for r in merged}

    with open(new_input, encoding="utf-8") as f:
        new_raw = {json.loads(line)["call_id"]: json.loads(line) for line in f if line.strip()}

    EXTRA_FIELDS = ["custInfo", "dialDate", "connectDate", "dialType", "ringTime", "collUserId",
                    "collId", "collArea", "collGroupId", "acNo", "isRecorded", "result", "talkTime",
                    "channel", "corpCode", "calledNo", "mobTyp", "phoneRoute", "agentTalkTime"]
    for r in complete:
        cid = r.get("call_id")
        if cid in existing_ids or cid not in new_ids:
            continue
        src = new_raw.get(cid, {})
        for field in EXTRA_FIELDS:
            if field in src:
                r[field] = src[field]
        merged.append(r)
        existing_ids.add(cid)
    _write_py_results(merged, merged_path)
    _log.info("Merged: %d records total", len(merged))
    return [r for r in merged if r["call_id"] in new_ids]


def _phase1c_label(new_merged_records):
    _log.info("Phase 1c: Keyword labeling (new records only)")
    from f000_keyword_discovery.discover_keywords import label_new_records
    taxonomy = label_new_records(new_merged_records)
    _log.info("Taxonomy: %d facts, %d emotions, %d actions",
              len(taxonomy.get("facts", [])), len(taxonomy.get("emotions", [])),
              len(taxonomy.get("collector_actions", [])))


def _phase1d_align_relabel(new_merged_records, new_ids):
    _log.info("Phase 1d: Schema alignment + relabel (new records only)")
    from f001_schema_alignment.align_schema import align_record, _load_output_labeled
    from f001_schema_alignment.relabel_state import relabel_record, load_fact_map, load_emotion_map

    labeled_lookup = _load_output_labeled()
    fact_map = load_fact_map()
    emotion_map = load_emotion_map()

    aligned_path = BASE_DIR / "f001_schema_alignment" / "data" / "output_aligned.py"
    existing_aligned = _load_py_results(aligned_path)
    existing_ids = {r["call_id"] for r in existing_aligned}

    new_aligned = []
    for r in new_merged_records:
        if r["call_id"] in existing_ids:
            continue
        aligned = align_record(r, labeled_lookup)
        aligned = relabel_record(aligned, fact_map, emotion_map)
        existing_aligned.append(aligned)
        new_aligned.append(aligned)
    _write_py_results(existing_aligned, aligned_path)
    _log.info("Aligned: %d records total", len(existing_aligned))
    return new_aligned


def _phase1e_reward(new_aligned):
    _log.info("Phase 1e: Reward labeling (new records only)")
    from f003_reward_labeling.reward_label import label_reward

    rewarded_path = BASE_DIR / "f003_reward_labeling" / "data" / "output_rewarded.py"
    existing_rewarded = _load_py_results(rewarded_path)
    existing_ids = {r["call_id"] for r in existing_rewarded}

    new_rewarded = []
    for r in new_aligned:
        if r["call_id"] in existing_ids:
            continue
        rewarded = label_reward(r)
        existing_rewarded.append(rewarded)
        new_rewarded.append(rewarded)
    _write_py_results(existing_rewarded, rewarded_path)
    _log.info("Rewarded: %d records total", len(existing_rewarded))
    return new_rewarded


def _phase2_tree(new_rewarded):
    _log.info("Phase 2: Incremental tree build")
    from f004_decision_tree.build_decision_tree import merge_dialogs, write_dialog_records_incremental, _load_merge_cache, _save_merge_cache
    tree_path = BASE_DIR / "f004_decision_tree" / "data" / "decision_tree.json"
    merge_cache = _load_merge_cache()
    tree = merge_dialogs(str(tree_path), new_rewarded, merge_decisions=merge_cache)
    _save_merge_cache(merge_cache)
    write_dialog_records_incremental(new_rewarded)
    node_count = _count_tree_nodes(tree)
    _log.info("Tree: %d nodes", node_count)
    return tree


def _count_tree_nodes(node, visited=None):
    if visited is None:
        visited = set()
    nid = id(node)
    if nid in visited:
        return 0
    visited.add(nid)
    return 1 + sum(_count_tree_nodes(c, visited) for c in node.get("children", []))


def _phase3_4_score_db(tree, new_ids, dsn):
    _log.info("Phase 3+4: Score tree + targeted DB upsert")
    from f005_context_scoring.score_tree import (score_tree, build_context_lookup, build_reward_lookup,
        build_turns_lookup, build_conversation_context_lookup, _collect_tree_nodes, _collect_tree_sentences)
    from f007_infrastructure.db import SentenceDB

    context_lookup = build_context_lookup()
    reward_lookup = build_reward_lookup()
    turns_lookup = build_turns_lookup()
    conv_ctx_lookup = build_conversation_context_lookup(tree, turns_lookup)
    scored = score_tree(tree, context_lookup, reward_lookup, conv_ctx_lookup, embed_fn=None)

    all_nodes = _collect_tree_nodes(scored)
    all_sentences = _collect_tree_sentences(scored)

    db = SentenceDB(dsn)
    db.create_tables()
    db.dedup_taxonomy_keywords()
    db.create_taxonomy_unique_index()

    existing_sigs = db.get_existing_path_signatures()
    existing_script_ids = db.get_existing_script_ids()

    new_nodes = [n for n in all_nodes if n["path_signature"] not in existing_sigs]
    if new_nodes:
        db.upsert_nodes(new_nodes)
    _log.info("Nodes: %d new / %d total", len(new_nodes), len(all_nodes))

    node_sig_to_id = db.get_node_ids_by_signatures([n["path_signature"] for n in all_nodes])

    affected_sigs = set()
    for s in all_sentences:
        if any(cid in new_ids for cid in s.get("source_call_ids", [])):
            affected_sigs.add(s.get("_node_path_sig", ""))

    new_sentences = []
    affected_existing = []
    for s in all_sentences:
        node_sig = s.get("_node_path_sig", "")
        node_id = node_sig_to_id.get(node_sig, 1)
        row = {
            "script_id": s.get("script_id", ""), "node_id": node_id,
            "script_text": s.get("script_text", ""), "bg_bitmask_int": s.get("bg_bitmask_int", 0),
            "win_rate": s.get("win_rate", 0), "sas": s.get("sas", 0),
            "bg_background": s.get("bg_background"), "conversation_context": s.get("conversation_context", ""),
        }
        if s["script_id"] not in existing_script_ids:
            new_sentences.append((s, row))
        elif node_sig in affected_sigs:
            affected_existing.append(row)

    if new_sentences:
        texts = [s.get("conversation_context", "") or s.get("script_text", "") for s, _ in new_sentences]
        vecs = embed_texts(texts)
        db_rows = []
        for (_, row), vec in zip(new_sentences, vecs, strict=False):
            row["embedding"] = vec or [0.0] * EMBEDDING_DIM
            db_rows.append(row)
        db.upsert_sentences(db_rows)
    _log.info("Sentences: %d new (embedded), %d affected-existing (score update)",
              len(new_sentences), len(affected_existing))

    if affected_existing:
        db.update_sentence_scores(affected_existing)

    tree_script_ids = {s.get("script_id", "") for s in all_sentences
                       if any(cid in new_ids for cid in s.get("source_call_ids", []))}
    db_script_ids = {sid for sid in existing_script_ids
                     if any(cid in sid for cid in new_ids)}
    db_script_ids |= {s.get("script_id", "") for s, _ in new_sentences}
    orphans = db_script_ids - tree_script_ids
    if orphans:
        db.delete_sentences(list(orphans))
    _log.info("Orphan cleanup: %d removed", len(orphans))

    from f005_context_scoring.score_tree import _load_state_keywords
    keywords = _load_state_keywords()
    if keywords:
        kw_rows = []
        for category in ["facts", "emotions", "collector_actions"]:
            for group in keywords.get(category, []):
                for kw in group.get("keywords", []):
                    kw_rows.append({"group_name": group.get("group_name") or "", "category": category,
                                    "keyword": kw, "frequency": group.get("frequency", 0)})
        db.upsert_taxonomy_keywords(kw_rows)

    scored_path = BASE_DIR / "f005_context_scoring" / "data" / "decision_tree_scored.json"
    for s in all_sentences:
        s.pop("_context_vec", None)
        s.pop("_node_path_sig", None)
    with open(scored_path, "w", encoding="utf-8") as f:
        json.dump(scored, f, indent=2, ensure_ascii=False)

    db.close()
    return len(new_nodes), len(new_sentences), len(affected_existing)


def _append_to_matched_data(new_input):
    matched_path = INPUT_DIR / "matched_data.jsonl"
    with open(new_input, encoding="utf-8") as f:
        new_lines = [line for line in f if line.strip()]
    with open(matched_path, "a", encoding="utf-8") as f:
        for line in new_lines:
            if not line.endswith("\n"):
                line += "\n"
            f.write(line)
    _log.info("Appended %d records to %s", len(new_lines), matched_path)


def main():
    parser = argparse.ArgumentParser(description="Incremental record append")
    parser.add_argument("--new-input", default="data/data_input/new_data.jsonl")
    parser.add_argument("--dsn", default=os.environ.get("PG_DSN", ""))
    args = parser.parse_args()
    if not args.dsn:
        _log.error("PG_DSN not set")
        sys.exit(1)

    new_input = Path(args.new_input).resolve()
    new_ids = _phase0_check(new_input)
    _phase1a_clean(new_input)
    new_merged = _phase1b_merge(new_input, new_ids)
    _phase1c_label(new_merged)
    new_aligned = _phase1d_align_relabel(new_merged, new_ids)
    new_rewarded = _phase1e_reward(new_aligned)
    tree = _phase2_tree(new_rewarded)
    n_nodes, n_sents, n_affected = _phase3_4_score_db(tree, new_ids, args.dsn)
    _append_to_matched_data(new_input)

    print(f"\n{'='*60}")
    print(f"Incremental append complete:")
    print(f"  New call_ids: {sorted(new_ids)}")
    print(f"  New nodes: {n_nodes}")
    print(f"  New sentences (embedded): {n_sents}")
    print(f"  Affected existing sentences (score update): {n_affected}")
    print(f"  Records appended to matched_data.jsonl: {len(new_ids)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
