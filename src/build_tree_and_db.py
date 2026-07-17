import argparse
import importlib.util
import json
import os
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

REWARDED_PATH = BASE_DIR / "f003_reward_labeling" / "data" / "output_rewarded.py"
ALIGNED_PATH = BASE_DIR / "f001_schema_alignment" / "data" / "output_aligned.py"
TREE_PATH = BASE_DIR / "f004_decision_tree" / "data" / "decision_tree.json"
SCORED_PATH = BASE_DIR / "f005_context_scoring" / "data" / "decision_tree_scored.json"
KEYWORDS_PATH = BASE_DIR / "f000_keyword_discovery" / "data" / "state_keywords.json"


def _ts():
    return f"[{datetime.now():%Y-%m-%d %H:%M:%S}]"


def _load_py_results(path: Path) -> list[dict]:
    spec = importlib.util.spec_from_file_location("results_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.results


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_json(data, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def run_build_tree(rewarded: list[dict]) -> dict:
    print(f"\n{'=' * 60}")
    print(f"{_ts()} PHASE 5: Build Decision Tree (F004)")
    print(f"{'=' * 60}")

    import f004_decision_tree.build_decision_tree as bdt

    node_count = bdt.write_decision_tree(rewarded, output_path=str(TREE_PATH))
    print(f"  → {Path(TREE_PATH).name}  ({node_count} nodes)")

    tree = _load_json(TREE_PATH)

    # Defensive: guarantee unique script_ids even if the build module was stale
    import f004_decision_tree.tree_transforms as tt
    seen = set()
    dup = 0
    _stack = [tree]
    _vis = set()
    while _stack:
        _n = _stack.pop()
        if id(_n) in _vis:
            continue
        _vis.add(id(_n))
        for _s in _n.get("sentence_pool", []):
            _sid = _s.get("script_id")
            if _sid is not None:
                if _sid in seen:
                    dup += 1
                seen.add(_sid)
        _stack.extend(_n.get("children", []))
    if dup:
        tt._dedup_script_ids_global(tree)
        _write_json(tree, TREE_PATH)
        print(f"  ⚠ removed {dup} duplicate script_ids (defensive pass)")

    return tree


def run_score_tree(tree: dict, aligned: list[dict], rewarded: list[dict], with_embeddings: bool = False) -> dict:
    print(f"\n{'=' * 60}")
    print(f"{_ts()} PHASE 6: Score Tree (F005)")
    print(f"{'=' * 60}")

    import f005_context_scoring.score_tree as st

    context_lookup = st.build_context_lookup(aligned)
    reward_lookup = st.build_reward_lookup(rewarded)
    customer_info_lookup = st.build_customer_info_lookup(rewarded)
    turns_lookup = st.build_turns_lookup(aligned)
    conv_ctx_lookup = st.build_conversation_context_lookup(tree, turns_lookup)

    scored = st.score_tree(tree, context_lookup, reward_lookup, customer_info_lookup, conv_ctx_lookup)

    sentence_count = 0
    def _count(node):
        nonlocal sentence_count
        sentence_count += len(node.get("sentence_pool", []))
        for c in node.get("children", []):
            _count(c)
    _count(scored)

    _write_json(scored, SCORED_PATH)
    print(f"  → {SCORED_PATH.name}  ({sentence_count} scored sentences)")

    return scored


def run_build_db(scored: dict, aligned: list[dict], rewarded: list[dict], dsn: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"{_ts()} PHASE 7: Build Database (PostgreSQL)")
    print(f"{'=' * 60}")

    from f007_infrastructure.db import SentenceDB
    from f007_infrastructure.embeddings import EMBEDDING_DIM, embed_texts

    db = SentenceDB(dsn)
    db.create_tables()
    print("  Tables created/verified.")

    import f005_context_scoring.score_tree as st

    all_nodes = st._collect_tree_nodes(scored)
    db.upsert_nodes(all_nodes)
    print(f"  Upserted {len(all_nodes)} nodes.")

    node_sig_to_id = {}
    for n in all_nodes:
        row = db.get_node_by_signature(n["path_signature"])
        if row:
            node_sig_to_id[n["path_signature"]] = row["id"]

    all_sentences = st._collect_tree_sentences(scored)

    orphan_sigs: set[str] = set()
    for s in all_sentences:
        node_sig = s.get("_node_path_sig", "")
        if node_sig_to_id.get(node_sig) is None:
            orphan_sigs.add(node_sig)

    if orphan_sigs:
        raise ValueError(
            f"build failed: {len(orphan_sigs)} orphan node signature(s) not found in nodes table: "
            f"{sorted(orphan_sigs)[:10]}"
        )

    EMBED_INSERT_BATCH = 128
    print(f"  Embedding + upserting {len(all_sentences)} sentences in batches of {EMBED_INSERT_BATCH}...")
    total_upserted = 0
    for i in range(0, len(all_sentences), EMBED_INSERT_BATCH):
        chunk = all_sentences[i : i + EMBED_INSERT_BATCH]
        texts = [s.get("conversation_context", "") or s.get("script_text", "") for s in chunk]
        vecs = embed_texts(texts)
        db_sentences = []
        for s, vec in zip(chunk, vecs, strict=True):
            db_sentences.append({
                "script_id": s.get("script_id", ""),
                "node_id": node_sig_to_id[s.get("_node_path_sig", "")],
                "script_text": s.get("script_text", ""),
                "bg_bitmask_int": s.get("bg_bitmask_int", 0),
                "win_rate": s.get("win_rate", 0),
                "sas": s.get("sas", 0),
                "bg_background": s.get("bg_background"),
                "conversation_context": s.get("conversation_context", ""),
                "embedding": vec or [0.0] * EMBEDDING_DIM,
            })
        if db_sentences:
            db.upsert_sentences(db_sentences)
            total_upserted += len(db_sentences)
    print(f"  Upserted {total_upserted} sentences with embeddings.")

    if KEYWORDS_PATH.exists():
        keywords = _load_json(KEYWORDS_PATH)
        kw_rows = []
        for category in ["facts", "emotions", "collector_actions"]:
            for group in keywords.get(category, []):
                for kw in group.get("keywords", []):
                    kw_rows.append({
                        "group_name": group.get("group_name") or "",
                        "category": category,
                        "keyword": kw,
                        "frequency": group.get("frequency", 0),
                    })
        if kw_rows:
            with db.connection() as conn:
                cur = conn.cursor()
                for kr in kw_rows:
                    cur.execute(
                        "INSERT INTO taxonomy_keywords (group_name, category, keyword, frequency) "
                        "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                        (kr["group_name"], kr["category"], kr["keyword"], kr["frequency"]),
                    )
                cur.close()
            print(f"  Upserted {len(kw_rows)} taxonomy keywords.")

    db.close()
    print("  Database build complete.")


def run(args) -> None:
    rewarded_path = args.rewarded_file or REWARDED_PATH
    aligned_path = args.aligned_file or ALIGNED_PATH

    if not rewarded_path.exists():
        print(f"Rewarded file not found: {rewarded_path}")
        print("Run whole_pipeline.py first, or provide --rewarded-file.")
        sys.exit(1)

    if not aligned_path.exists():
        print(f"Aligned file not found: {aligned_path}")
        print("Run whole_pipeline.py first, or provide --aligned-file.")
        sys.exit(1)

    print(f"{_ts()} Loading pre-computed data...")
    rewarded = _load_py_results(rewarded_path)
    aligned = _load_py_results(aligned_path)
    print(f"  Rewarded: {len(rewarded)} records from {rewarded_path.name}")
    print(f"  Aligned:  {len(aligned)} records from {aligned_path.name}")

    tree = run_build_tree(rewarded)
    with_embeddings = not args.skip_db
    scored = run_score_tree(tree, aligned, rewarded, with_embeddings=with_embeddings)

    import f004_decision_tree.build_decision_tree as bdt
    dialog_count = bdt.write_dialog_records(aligned)
    print(f"  → dialog_records.json  ({dialog_count} records)")

    if args.skip_db:
        print(f"\n{_ts()} Skipping database build (--skip-db).")
    else:
        dsn = args.dsn or os.environ.get("PG_DSN", "dbname=icbc user=postgres")
        run_build_db(scored, aligned, rewarded, dsn)

    print(f"\n{'=' * 60}")
    print(f"{_ts()} All done.")
    print(f"  Decision tree:  {TREE_PATH}")
    print(f"  Scored tree:    {SCORED_PATH}")
    if not args.skip_db:
        print("  Database:       populated")
    print(f"{'=' * 60}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Continue after whole_pipeline.py: build decision tree → score tree → populate database"
    )
    parser.add_argument(
        "--rewarded-file", type=Path, default=None,
        help="Path to output_rewarded.py (default: f003_reward_labeling/data/output_rewarded.py)",
    )
    parser.add_argument(
        "--aligned-file", type=Path, default=None,
        help="Path to output_aligned.py (default: f001_schema_alignment/data/output_aligned.py)",
    )
    parser.add_argument(
        "--dsn", type=str, default=None,
        help="PostgreSQL DSN (default: $PG_DSN or 'dbname=icbc user=postgres')",
    )
    parser.add_argument(
        "--skip-db", action="store_true",
        help="Skip the database population step",
    )
    run(parser.parse_args())


if __name__ == "__main__":
    main()
