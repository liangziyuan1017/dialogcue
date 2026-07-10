import argparse
import json
import os
import random
import sys
from datetime import datetime

from f016_sentence_augmentation.generate_prompts import build_augmentation_prompt
from f016_sentence_augmentation.random_profile import generate_unique_call_id, generate_random_profile
from f016_sentence_augmentation.score_sentences import score_new_sentence

SCORED_TREE_PATH = os.path.join(
    os.path.dirname(__file__), "..",
    "f005_context_scoring", "data", "decision_tree_scored.json",
)
OVERLAY_PATH = os.path.join(os.path.dirname(__file__), "data", "augmented_sentences.json")


def load_scored_tree(path: str = SCORED_TREE_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def find_node_by_id(tree: dict, node_id: str) -> dict | None:
    if tree.get("node_id") == node_id:
        return tree
    for child in tree.get("children", []):
        result = find_node_by_id(child, node_id)
        if result is not None:
            return result
    return None


def find_node_by_path_signature(tree: dict, path_signature: str) -> dict | None:
    if tree.get("path_signature") == path_signature:
        return tree
    for child in tree.get("children", []):
        result = find_node_by_path_signature(child, path_signature)
        if result is not None:
            return result
    return None


def collect_existing_sentence_texts(node: dict) -> list[str]:
    pool = node.get("sentence_pool", [])
    return [s.get("script_text", "") for s in pool if s.get("script_text")]


def load_overlay(path: str = OVERLAY_PATH) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_overlay(path: str, data: dict, append: bool = False):
    if append and os.path.exists(path):
        existing = load_overlay(path)
        for node_id, aug in data.get("augmentations", {}).items():
            if node_id in existing.get("augmentations", {}):
                existing["augmentations"][node_id]["sentences"].extend(aug["sentences"])
            else:
                existing.setdefault("augmentations", {})[node_id] = aug
        existing["generated_at"] = data.get("generated_at", existing.get("generated_at"))
        data = existing
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def insert_into_db(sentences: list[dict], path_signature: str, dsn: str):
    from f007_infrastructure.db import SentenceDB
    db = SentenceDB(dsn)
    try:
        node_row = db.get_node_by_signature(path_signature)
        if not node_row:
            raise ValueError(f"Node not found in DB: {path_signature}")
        db_sentences = []
        for s in sentences:
            db_sentences.append({
                "script_id": s["script_id"],
                "node_id": node_row["id"],
                "script_text": s["script_text"],
                "bg_bitmask_int": s["bg_bitmask_int"],
                "win_rate": s["win_rate"],
                "sas": s["sas"],
                "bg_background": json.dumps(s["bg_background"]),
                "conversation_context": s["conversation_context"],
                "embedding": s.get("_embedding"),
            })
        db.upsert_sentences(db_sentences)
    finally:
        db.close()


def run_augmentation(
    node: dict,
    count: int,
    seed: int | None = None,
    no_db: bool = False,
    no_overlay: bool = False,
    dsn: str = "",
    overlay_path: str = OVERLAY_PATH,
):
    if seed is not None:
        random.seed(seed)

    existing_script_ids = set()
    if not no_overlay:
        overlay = load_overlay(overlay_path)
        for aug in overlay.get("augmentations", {}).values():
            for s in aug.get("sentences", []):
                existing_script_ids.add(s["script_id"])
    if not no_db and dsn:
        try:
            import psycopg2
            conn = psycopg2.connect(dsn)
            cur = conn.cursor()
            cur.execute("SELECT script_id FROM sentences WHERE script_id LIKE '9999%'")
            existing_script_ids.update(row[0] for row in cur.fetchall())
            cur.close()
            conn.close()
        except Exception:
            pass

    fake_call_id = generate_unique_call_id(existing_script_ids, count)
    profile = generate_random_profile()
    existing_texts = collect_existing_sentence_texts(node)
    existing_sentences = node.get("sentence_pool", [])

    prompt = build_augmentation_prompt(node, profile, existing_sentences, count)

    from f007_infrastructure.llm_client import call_deepseek_json
    response = call_deepseek_json(prompt, temperature=1.1)
    raw_texts = response.get("sentences", [])

    seen = set(existing_texts)
    generated_texts = []
    for text in raw_texts:
        if text and text not in seen:
            seen.add(text)
            generated_texts.append(text)
    if not generated_texts:
        print("WARNING: LLM returned no usable sentences")
        return []

    scored = []
    for i, text in enumerate(generated_texts, 1):
        sentence = score_new_sentence(text, profile, fake_call_id, i, node)
        scored.append(sentence)

    if not no_overlay:
        node_id = node.get("node_id", "unknown")
        path_sig = node.get("path_signature", "")
        overlay_data = {
            "version": 1,
            "generated_at": datetime.now().isoformat(),
            "augmentations": {
                node_id: {
                    "path_signature": path_sig,
                    "sentences": [
                        {k: v for k, v in s.items() if k != "_embedding"}
                        for s in scored
                    ],
                }
            },
        }
        write_overlay(overlay_path, overlay_data, append=True)

    if not no_db and dsn:
        try:
            insert_into_db(scored, node.get("path_signature", ""), dsn)
        except Exception as e:
            print(f"WARNING: DB insert failed: {e}")

    print(f"\nAugmentation Summary")
    print(f"{'=' * 50}")
    print(f"Node: {node.get('node_id')} ({node.get('path_signature')})")
    print(f"Fake call_id: {fake_call_id}")
    print(f"Generated: {len(scored)} sentences")
    for s in scored:
        print(f"  {s['script_id']}: {s['script_text'][:50]}...")
    if not no_overlay:
        print(f"Overlay: {overlay_path}")
    if not no_db and dsn:
        print(f"DB: inserted")

    return scored


def main():
    parser = argparse.ArgumentParser(description="Augment sentence pool for a tree node")
    parser.add_argument("--node-id", help="Target node ID (e.g., n_b8e3ecee405b)")
    parser.add_argument("--path-signature", help="Target path signature")
    parser.add_argument("--count", type=int, default=5, help="Number of sentences to generate")
    parser.add_argument("--dsn", default="", help="PostgreSQL DSN for DB insert")
    parser.add_argument("--no-db", action="store_true", help="Skip DB insert")
    parser.add_argument("--no-overlay", action="store_true", help="Skip overlay file")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--tree-path", default=SCORED_TREE_PATH, help="Path to scored tree JSON")
    parser.add_argument("--overlay-path", default=OVERLAY_PATH, help="Path to overlay JSON")
    args = parser.parse_args()

    if not args.node_id and not args.path_signature:
        parser.error("Either --node-id or --path-signature is required")

    tree = load_scored_tree(args.tree_path)

    if args.node_id:
        node = find_node_by_id(tree, args.node_id)
    else:
        node = find_node_by_path_signature(tree, args.path_signature)

    if not node:
        print(f"ERROR: Node not found")
        print(f"Available root: {tree.get('node_id')} ({tree.get('path_signature')})")
        sys.exit(1)

    run_augmentation(
        node=node,
        count=args.count,
        seed=args.seed,
        no_db=args.no_db,
        no_overlay=args.no_overlay,
        dsn=args.dsn,
        overlay_path=args.overlay_path,
    )


if __name__ == "__main__":
    main()
