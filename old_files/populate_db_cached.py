"""
Populate PostgreSQL DB from scored tree with embedding cache.
Reuses cached embeddings when script_id + script_text match, only calls
the embedding API for new or changed sentences.

Usage:
    python3 src/populate_db_cached.py
    python3 src/populate_db_cached.py --no-cache   # force re-embed all
"""
import argparse
import json
import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
SCORED_PATH = _PROJECT_ROOT / "f005_context_scoring" / "data" / "decision_tree_scored.json"
KEYWORDS_PATH = _PROJECT_ROOT / "f000_keyword_discovery" / "data" / "state_keywords.json"
CACHE_DIR = _PROJECT_ROOT / "f007_infrastructure" / "data"
CACHE_FILE = CACHE_DIR / "embedding_cache.json"


def _load_cache() -> dict:
    if not CACHE_FILE.exists():
        return {}
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_cache(cache: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f)
    print(f"  Saved embedding cache ({len(cache)} entries) to {CACHE_FILE}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-cache", action="store_true", help="Force re-embed all sentences")
    parser.add_argument("--dsn", type=str, default=None, help="PostgreSQL DSN")
    args = parser.parse_args()

    from f007_infrastructure.db import SentenceDB
    from f007_infrastructure.embeddings import EMBEDDING_DIM, embed_single, embed_texts
    import f005_context_scoring.score_tree as st

    dsn = args.dsn or os.environ.get("PG_DSN", "dbname=icbc user=postgres")
    db = SentenceDB(dsn)
    db.create_tables()
    print("Tables created/verified.")

    with open(SCORED_PATH, "r", encoding="utf-8") as f:
        scored = json.load(f)

    # --- Nodes ---
    all_nodes = st._collect_tree_nodes(scored)
    db.upsert_nodes(all_nodes)
    print(f"Upserted {len(all_nodes)} nodes.")

    node_sig_to_id = {}
    for n in all_nodes:
        row = db.get_node_by_signature(n["path_signature"])
        if row:
            node_sig_to_id[n["path_signature"]] = row["id"]

    # --- Sentences with cached embeddings ---
    all_sentences = st._collect_tree_sentences(scored)
    cache = {} if args.no_cache else _load_cache()
    print(f"Embedding cache: {len(cache)} entries loaded.")

    hits = 0
    misses = 0
    miss_indices = []
    texts_to_embed = []

    for i, s in enumerate(all_sentences):
        sid = s.get("script_id", "")
        text = s.get("conversation_context", "") or s.get("script_text", "")
        cached = cache.get(sid)
        if cached and cached.get("script_text") == text:
            hits += 1
        else:
            misses += 1
            miss_indices.append(i)
            texts_to_embed.append(text)

    print(f"Sentences: {len(all_sentences)} total, {hits} cache hits, {misses} cache misses")

    if texts_to_embed:
        print(f"Embedding {len(texts_to_embed)} new/changed sentences...")
        new_vecs = embed_texts(texts_to_embed)
    else:
        new_vecs = []

    # Build final sentence list with embeddings
    miss_vec_idx = 0
    db_sentences = []
    orphan_sigs: set[str] = set()

    for i, s in enumerate(all_sentences):
        sid = s.get("script_id", "")
        text = s.get("conversation_context", "") or s.get("script_text", "")
        node_sig = s.get("_node_path_sig", "")
        node_id = node_sig_to_id.get(node_sig)
        if node_id is None:
            orphan_sigs.add(node_sig)
            continue

        cached = cache.get(sid)
        if cached and cached.get("script_text") == text:
            vec = cached["embedding"]
        else:
            vec = new_vecs[miss_vec_idx]
            miss_vec_idx += 1
            cache[sid] = {"script_text": text, "embedding": vec}

        db_sentences.append({
            "script_id": sid,
            "node_id": node_id,
            "script_text": s.get("script_text", ""),
            "bg_bitmask_int": s.get("bg_bitmask_int", 0),
            "win_rate": s.get("win_rate", 0),
            "sas": s.get("sas", 0),
            "bg_background": s.get("bg_background"),
            "conversation_context": s.get("conversation_context", ""),
            "embedding": vec or [0.0] * EMBEDDING_DIM,
        })

    if orphan_sigs:
        raise ValueError(
            f"build failed: {len(orphan_sigs)} orphan node signature(s): "
            f"{sorted(orphan_sigs)[:10]}"
        )

    db.upsert_sentences(db_sentences)
    print(f"Upserted {len(db_sentences)} sentences with embeddings.")

    # --- Taxonomy keywords ---
    if KEYWORDS_PATH.exists():
        with open(KEYWORDS_PATH, "r", encoding="utf-8") as f:
            keywords = json.load(f)
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
            print(f"Upserted {len(kw_rows)} taxonomy keywords.")

    _save_cache(cache)
    db.close()
    print("Database build complete.")


if __name__ == "__main__":
    main()
