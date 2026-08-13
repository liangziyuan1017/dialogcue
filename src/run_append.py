"""Automation entrypoint for incremental record append.

Mode selection (auto by default):
  - full          read data/data_input/new_data.jsonl, run all phases (clean → tree → DB)
  - skip-cleaning read src/f003_reward_labeling/data/new_rewarded.py, skip cleaning,
                  run tree build + DB populate only

In `auto` mode:
  - new_data.jsonl non-empty  → full
  - otherwise                  → skip-cleaning

Warnings are printed for any per-phase error instead of dumping a raw traceback.
"""

import argparse
import os
import sys
from pathlib import Path

from f007_infrastructure.jsonl_utils import load_jsonl

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
INPUT_DIR = DATA_DIR / "data_input"
NEW_DATA_DEFAULT = INPUT_DIR / "new_data.jsonl"
NEW_REWARDED_DEFAULT = BASE_DIR / "f003_reward_labeling" / "data" / "new_rewarded.jsonl"
EXISTING_REWARDED = BASE_DIR / "f003_reward_labeling" / "data" / "output_rewarded.jsonl"


def _warn(msg):
    print(f"WARNING: {msg}", file=sys.stderr)


def _new_data_nonempty(path: Path) -> bool:
    if not path.exists():
        return False
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                return True
    return False


def _detect_mode(args) -> str:
    if args.mode != "auto":
        return args.mode
    if _new_data_nonempty(Path(args.new_input)):
        return "full"
    return "skip-cleaning"


def run_full(args):
    import add_records

    new_input = Path(args.new_input).resolve()
    if not new_input.exists() or not _new_data_nonempty(new_input):
        _warn(f"full mode selected but {new_input} is missing or empty")
        return 1

    phases = [
        ("Phase 0: pre-check", lambda: add_records._phase0_check(new_input)),
    ]
    state = {}

    def p1a():
        state["new_ids"] = phases[0][1]()
        add_records._phase1a_clean(new_input)

    def p1b():
        state["new_merged"] = add_records._phase1b_merge(new_input, state["new_ids"])

    def p1c():
        add_records._phase1c_label(state["new_merged"])

    def p1d():
        state["new_aligned"] = add_records._phase1d_align_relabel(state["new_merged"], state["new_ids"])

    def p1e():
        state["new_rewarded"] = add_records._phase1e_reward(state["new_aligned"])

    def p2():
        state["tree"] = add_records._phase2_tree(state["new_rewarded"])

    def p34():
        state["counts"] = add_records._phase3_4_score_db(state["tree"], state["new_ids"], args.dsn)

    def p5():
        add_records._append_to_matched_data(new_input)

    steps = [
        ("Phase 0+1a: pre-check + clean", p1a),
        ("Phase 1b: merge", p1b),
        ("Phase 1c: label", p1c),
        ("Phase 1d: align/relabel", p1d),
        ("Phase 1e: reward", p1e),
        ("Phase 2: incremental tree", p2),
        ("Phase 3+4: score + DB upsert", p34),
        ("Phase 5: append to matched_data", p5),
    ]

    for label, fn in steps:
        try:
            print(f"[full] {label} ...")
            fn()
            print(f"[full] {label} OK")
        except Exception as e:
            _warn(f"{label} failed: {e}")
            return 1

    n_nodes, n_sents, n_affected = state["counts"]
    _print_summary(state["new_ids"], n_nodes, n_sents, n_affected, appended=len(state["new_ids"]))
    return 0


def run_skip_cleaning(args):
    import add_records

    rewarded_path = Path(args.rewarded_input).resolve()
    if not rewarded_path.exists():
        _warn(f"skip-cleaning mode but {rewarded_path} is missing")
        return 1

    new_rewarded = load_jsonl(rewarded_path)
    if not new_rewarded:
        _warn(f"{rewarded_path} contains no records (results = [])")
        return 1

    existing_ids = set()
    if EXISTING_REWARDED.exists():
        try:
            existing_ids = {r["call_id"] for r in load_jsonl(EXISTING_REWARDED)}
        except Exception as e:
            _warn(f"could not load existing output_rewarded.jsonl: {e}")

    new_records = [r for r in new_rewarded if r.get("call_id") not in existing_ids]
    if not new_records:
        _warn("all records in new_rewarded.jsonl already exist in output_rewarded.jsonl — nothing to append")
        return 0
    new_ids = {r["call_id"] for r in new_records}

    state = {"new_rewarded": new_records, "new_ids": new_ids}
    steps = [
        ("Phase 2: incremental tree", lambda: state.update(
            tree=add_records._phase2_tree(state["new_rewarded"]))),
        ("Phase 3+4: score + DB upsert", lambda: state.update(
            counts=add_records._phase3_4_score_db(state["tree"], state["new_ids"], args.dsn))),
    ]

    for label, fn in steps:
        try:
            print(f"[skip-cleaning] {label} ...")
            fn()
            print(f"[skip-cleaning] {label} OK")
        except Exception as e:
            _warn(f"{label} failed: {e}")
            return 1

    _warn("skip-cleaning mode: matched_data.jsonl append hook skipped (no raw input records)")
    n_nodes, n_sents, n_affected = state["counts"]
    _print_summary(new_ids, n_nodes, n_sents, n_affected, appended=0)
    return 0


def _print_summary(new_ids, n_nodes, n_sents, n_affected, appended):
    print(f"\n{'='*60}")
    print("Incremental append complete:")
    print(f"  New call_ids: {sorted(new_ids)}")
    print(f"  New nodes: {n_nodes}")
    print(f"  New sentences (embedded): {n_sents}")
    print(f"  Affected existing sentences (score update): {n_affected}")
    print(f"  Records appended to matched_data.jsonl: {appended}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="Incremental record append automation")
    parser.add_argument("--mode", choices=["auto", "full", "skip-cleaning"], default="auto")
    parser.add_argument("--new-input", default=str(NEW_DATA_DEFAULT))
    parser.add_argument("--rewarded-input", default=str(NEW_REWARDED_DEFAULT))
    parser.add_argument("--dsn", default=os.environ.get("PG_DSN", ""))
    args = parser.parse_args()

    if not args.dsn:
        _warn("PG_DSN not set")
        return 1

    sys.path.insert(0, str(BASE_DIR))

    mode = _detect_mode(args)
    print(f"Mode: {mode}")

    if mode == "full":
        return run_full(args)
    return run_skip_cleaning(args)


if __name__ == "__main__":
    sys.exit(main())
