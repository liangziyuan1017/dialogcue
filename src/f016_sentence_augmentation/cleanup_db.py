import argparse
import json
import os
import sys

from f016_sentence_augmentation.augment_sentences import load_scored_tree

SCORED_TREE_PATH = os.path.join(
    os.path.dirname(__file__), "..",
    "f005_context_scoring", "data", "decision_tree_scored.json",
)


def build_tree_mappings(tree: dict) -> dict:
    tree_script_ids = set()
    tree_sid_to_psig = {}
    tree_path_signatures = set()

    def walk(node):
        psig = node.get("path_signature")
        if psig:
            tree_path_signatures.add(psig)
        for s in node.get("sentence_pool", []):
            sid = s.get("script_id")
            if sid:
                tree_script_ids.add(sid)
                if psig:
                    tree_sid_to_psig[sid] = psig
        for child in node.get("children", []):
            walk(child)

    walk(tree)
    return {
        "tree_script_ids": tree_script_ids,
        "tree_sid_to_psig": tree_sid_to_psig,
        "tree_path_signatures": tree_path_signatures,
    }


def identify_misplaced_sentences(
    tree_script_ids: set,
    tree_sid_to_psig: dict,
    tree_path_signatures: set,
    db_psig_to_node_id: dict,
    db_sid_to_node_psig: dict,
) -> dict:
    misplaced = {}
    for sid in tree_script_ids:
        db_psig = db_sid_to_node_psig.get(sid)
        if db_psig is None:
            continue
        if db_psig not in tree_path_signatures:
            correct_psig = tree_sid_to_psig.get(sid)
            if correct_psig is None:
                continue
            correct_node_id = db_psig_to_node_id.get(correct_psig)
            if correct_node_id is None:
                continue
            misplaced[sid] = {
                "correct_psig": correct_psig,
                "correct_node_id": correct_node_id,
            }
    return misplaced


def identify_extra_sentences(
    tree_script_ids: set,
    db_script_ids: set,
    keep_augmented: bool = True,
) -> set:
    extras = db_script_ids - tree_script_ids
    if keep_augmented:
        extras = {sid for sid in extras if not sid.startswith("9999")}
    return extras


def identify_extra_nodes(
    tree_path_signatures: set,
    db_path_signatures: set,
) -> set:
    return db_path_signatures - tree_path_signatures


def query_db_state(dsn: str) -> dict:
    import psycopg2
    import psycopg2.extras
    conn = psycopg2.connect(dsn)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("SELECT id, path_signature FROM nodes")
        db_nodes = cur.fetchall()

        cur.execute("SELECT script_id, node_id FROM sentences")
        db_sentences = cur.fetchall()

        cur.close()
    finally:
        conn.close()

    db_psig_to_node_id = {row["path_signature"]: row["id"] for row in db_nodes if row["path_signature"]}
    db_node_id_to_psig = {row["id"]: row["path_signature"] for row in db_nodes if row["path_signature"]}
    db_script_ids = {row["script_id"] for row in db_sentences}
    db_sid_to_node_psig = {}
    for row in db_sentences:
        psig = db_node_id_to_psig.get(row["node_id"])
        if psig:
            db_sid_to_node_psig[row["script_id"]] = psig
    db_path_signatures = set(db_psig_to_node_id.keys())

    return {
        "db_psig_to_node_id": db_psig_to_node_id,
        "db_script_ids": db_script_ids,
        "db_sid_to_node_psig": db_sid_to_node_psig,
        "db_path_signatures": db_path_signatures,
        "db_sentence_count": len(db_sentences),
        "db_node_count": len(db_nodes),
    }


def execute_cleanup(
    dsn: str,
    misplaced: dict,
    extra_sentence_ids: set,
    extra_node_ids: set,
    dry_run: bool = False,
):
    import psycopg2
    conn = psycopg2.connect(dsn)
    try:
        cur = conn.cursor()

        if dry_run:
            print(f"\nDRY RUN — would execute:")
            print(f"  Re-link {len(misplaced)} misplaced sentences")
            print(f"  Delete {len(extra_sentence_ids)} extra sentences")
            print(f"  Delete {len(extra_node_ids)} extra nodes")
            return

        for sid, info in misplaced.items():
            cur.execute(
                "UPDATE sentences SET node_id = %s WHERE script_id = %s",
                (info["correct_node_id"], sid),
            )

        if extra_sentence_ids:
            cur.execute(
                "DELETE FROM sentences WHERE script_id = ANY(%s)",
                (list(extra_sentence_ids),),
            )

        if extra_node_ids:
            cur.execute(
                "DELETE FROM nodes WHERE path_signature = ANY(%s)",
                (list(extra_node_ids),),
            )

        conn.commit()
        cur.close()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def run_cleanup(
    dsn: str,
    dry_run: bool = False,
    keep_augmented: bool = True,
    tree_path: str = SCORED_TREE_PATH,
):
    tree = load_scored_tree(tree_path)
    tree_mappings = build_tree_mappings(tree)
    tree_script_ids = tree_mappings["tree_script_ids"]
    tree_sid_to_psig = tree_mappings["tree_sid_to_psig"]
    tree_path_signatures = tree_mappings["tree_path_signatures"]

    db_state = query_db_state(dsn)

    misplaced = identify_misplaced_sentences(
        tree_script_ids, tree_sid_to_psig, tree_path_signatures,
        db_state["db_psig_to_node_id"], db_state["db_sid_to_node_psig"],
    )
    extra_sids = identify_extra_sentences(
        tree_script_ids, db_state["db_script_ids"], keep_augmented,
    )
    extra_psigs = identify_extra_nodes(
        tree_path_signatures, db_state["db_path_signatures"],
    )

    print(f"\nDB Cleanup Summary")
    print(f"{'=' * 50}")
    print(f"Tree sentences:     {len(tree_script_ids):,}")
    print(f"Tree nodes:         {len(tree_path_signatures):,}")
    print(f"DB sentences (before): {db_state['db_sentence_count']:,}")
    print(f"DB nodes (before):     {db_state['db_node_count']:,}")
    print()
    print(f"Misplaced tree sentences re-linked:  {len(misplaced)}")
    print(f"Extra sentences deleted:             {len(extra_sids)}")
    print(f"Extra nodes deleted:               {len(extra_psigs)}")
    augmented_count = len(db_state["db_script_ids"] & {s for s in db_state["db_script_ids"] if s.startswith("9999")})
    print(f"Augmented sentences preserved:        {augmented_count}")

    execute_cleanup(dsn, misplaced, extra_sids, extra_psigs, dry_run=dry_run)

    if not dry_run:
        print()
        print(f"DB sentences (after):  {len(tree_script_ids) + augmented_count:,}")
        print(f"DB nodes (after):      {len(tree_path_signatures):,}")
        print(f"✅ DB aligns with tree")


def main():
    parser = argparse.ArgumentParser(description="Clean up DB to align with current scored tree")
    parser.add_argument("--dsn", required=True, help="PostgreSQL DSN")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be deleted, don't execute")
    parser.add_argument("--keep-augmented", action="store_true", default=True, help="Preserve 9999%% sentences")
    parser.add_argument("--no-keep-augmented", dest="keep_augmented", action="store_false", help="Also delete augmented sentences")
    parser.add_argument("--tree-path", default=SCORED_TREE_PATH, help="Path to scored tree JSON")
    args = parser.parse_args()

    run_cleanup(
        dsn=args.dsn,
        dry_run=args.dry_run,
        keep_augmented=args.keep_augmented,
        tree_path=args.tree_path,
    )


if __name__ == "__main__":
    main()
