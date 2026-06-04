"""
Pipeline orchestrator for Qwen-optimized ASR dialogue cleaning.

Usage:
    python pipeline.py                        # run all stages on all 31 records
    python pipeline.py --count 5              # run all stages on first 5 records
    python pipeline.py --start 1a --stop 1b   # run only stages 1a through 1b
    python pipeline.py --start 2a             # run from stage 2a to the end
    python pipeline.py --stop 2c              # run from the beginning through stage 2c
    python pipeline.py --list                 # list all stages and their data files
"""

import argparse
import importlib
import sys
from pathlib import Path

STAGES = [
    ("1a", "stage1a_classify", "Classify turns (clean/emotional/noise/corruption)"),
    ("1b", "stage1b_rewrite", "Rewrite noise/corruption turns"),
    ("2a", "stage2a_identify", "Identify corrupted spans in 催收员 turns"),
    ("2b", "stage2b_repair", "Repair identified corruptions"),
    ("2c", "stage2c_validate", "Validate repairs (catch over-formalization)"),
    ("3a", "stage3a_structure", "Identify structural issues (merge/split/insert)"),
    ("3b", "stage3b_apply", "Apply structural changes"),
    ("3c", "stage3c_clean", "Final ASR cleanup pass"),
    ("3d", "stage3d_validate", "Coherence validation (logic/emotion/facts)"),
]

DATA_FILES = {
    "1a": "data/stage1a_classifications.json",
    "1b": "data/stage1b_rewritten.json",
    "2a": "data/stage2a_corruptions.json",
    "2b": "data/stage2b_repaired.json",
    "2c": "data/stage2c_validated.json",
    "3a": "data/stage3a_structures.json",
    "3b": "data/stage3b_restructured.json",
    "3c": "data/stage3c_cleaned.json",
    "3d": "data/stage3d_final.json",
}


def resolve_stage_range(start: str | None, stop: str | None) -> list[tuple[str, str, str]]:
    stage_ids = [s[0] for s in STAGES]
    start_idx = 0
    stop_idx = len(STAGES) - 1

    if start:
        if start not in stage_ids:
            print(f"Error: unknown stage '{start}'. Valid: {', '.join(stage_ids)}")
            sys.exit(1)
        start_idx = stage_ids.index(start)

    if stop:
        if stop not in stage_ids:
            print(f"Error: unknown stage '{stop}'. Valid: {', '.join(stage_ids)}")
            sys.exit(1)
        stop_idx = stage_ids.index(stop)

    return STAGES[start_idx : stop_idx + 1]


def run_stage(module_name: str, count: int) -> None:
    mod = importlib.import_module(module_name)
    mod.main(count)


def list_stages() -> None:
    base = Path(__file__).resolve().parent
    print(f"{'Stage':<5} {'Module':<22} {'Description':<50} {'Output'}")
    print("-" * 110)
    for sid, module, desc in STAGES:
        data_file = DATA_FILES[sid]
        exists = "✓" if (base / data_file).exists() else " "
        print(f"{sid:<5} {module:<22} {desc:<50} {exists} {data_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Qwen-optimized ASR dialogue cleaning pipeline")
    parser.add_argument("--count", type=int, default=0, help="Number of records to process (0 = all)")
    parser.add_argument("--start", type=str, default=None, help="Start stage (e.g. 1a, 2b, 3d)")
    parser.add_argument("--stop", type=str, default=None, help="Stop stage (inclusive, e.g. 1b, 2c, 3d)")
    parser.add_argument("--list", action="store_true", help="List all stages and their data files")
    args = parser.parse_args()

    if args.list:
        list_stages()
        return

    stages = resolve_stage_range(args.start, args.stop)
    if not stages:
        print("No stages to run.")
        return

    print(f"Pipeline: {stages[0][0]} → {stages[-1][0]}  |  Records: {'all' if args.count == 0 else args.count}")
    print()

    for sid, module, desc in stages:
        print(f"{'='*60}")
        print(f"Stage {sid}: {desc}")
        print(f"{'='*60}")
        try:
            run_stage(module, args.count)
        except Exception as e:
            print(f"\nStage {sid} FAILED: {e}")
            print("Pipeline aborted. Fix the issue and re-run with --start {next_stage}.")
            next_idx = STAGES.index((sid, module, desc)) + 1
            if next_idx < len(STAGES):
                print(f"Suggested resume: python pipeline.py --start {STAGES[next_idx][0]}")
            sys.exit(1)
        print()

    print(f"Pipeline complete. Final output: {DATA_FILES[stages[-1][0]]}")


if __name__ == "__main__":
    main()
