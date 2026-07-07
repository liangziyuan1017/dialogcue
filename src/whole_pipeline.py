import argparse
import importlib.util
import json
import os
import pprint
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from f007_infrastructure.config import get as _cfg

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
INPUT_DIR = DATA_DIR / "data_input"
OUTPUT_DIR = DATA_DIR / "data_output"

LLM_STEPS = [
    {
        "name": "data_clean_2",
        "script": DATA_DIR / "data_cleaning" / "data_clean_2.py",
        "default_output": "output_2.py",
    },
    {
        "name": "data_logic",
        "script": DATA_DIR / "data_cleaning" / "data_logic.py",
        "default_output": "output_logic.py",
    },
    {
        "name": "data_complete",
        "script": DATA_DIR / "data_cleaning" / "data_complete.py",
        "default_output": "output_complete.py",
    },
    {
        "name": "data_merge",
        "script": DATA_DIR / "data_cleaning" / "data_merge.py",
        "default_output": "output_merged.py",
    },
]

ANALYSIS_OUTPUTS = {
    "analyze_collector_turns": BASE_DIR / "f003_reward_labeling" / "data" / "collector_analysis.json",
    "analyze_customer_turns": BASE_DIR / "f003_reward_labeling" / "data" / "customer_analysis.json",
    "align_schema": BASE_DIR / "f001_schema_alignment" / "data" / "output_aligned.py",
    "reward_label": BASE_DIR / "f003_reward_labeling" / "data" / "output_rewarded.py",
}


def _load_py_results(path: Path) -> list[dict]:
    spec = importlib.util.spec_from_file_location("results_mod", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load Python module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.results


def _write_py_results(results: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("results = ")
        f.write(pprint.pformat(results, width=120))
        f.write("\n")


def _run_llm_step(step: dict, data_file: Path, output_file: Path) -> None:
    existing_pythonpath = os.environ.get("PYTHONPATH", "")
    infra_path = str(BASE_DIR / "f007_infrastructure")
    new_pythonpath = f"{infra_path}:{existing_pythonpath}" if existing_pythonpath else infra_path
    env = {
        **os.environ,
        "DATA_FILE": str(data_file),
        "OUTPUT_FILE": str(output_file),
        "PYTHONPATH": new_pythonpath,
    }
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Running {step['name']}...")
    print(f"  DATA_FILE   = {data_file}")
    print(f"  OUTPUT_FILE = {output_file}")
    result = subprocess.run(
        [sys.executable, str(step["script"])],
        env=env,
        cwd=str(DATA_DIR),
    )
    if result.returncode != 0:
        print(f"  {step['name']} failed with exit code {result.returncode}")
        sys.exit(result.returncode)
    print(f"  {step['name']} completed.")


def _is_within_allowed_hours(forbid_start: int, forbid_end: int) -> bool:
    now_hour = datetime.now().hour
    if forbid_start <= forbid_end:
        return not (forbid_start <= now_hour < forbid_end)
    else:
        return not (now_hour >= forbid_start or now_hour < forbid_end)


def run_pipeline(input_file: Path) -> None:
    print("=" * 60)
    print("PHASE 1: LLM Data Cleaning")
    print("=" * 60)

    prev_output = input_file
    for step in LLM_STEPS:
        if step["name"] == "data_merge":
            data_file = input_file
            merge_output = OUTPUT_DIR / step["default_output"]
            if prev_output != input_file:
                shutil.copy2(prev_output, merge_output)
                print(f"  Pre-populated {merge_output.name} from {prev_output.name}")
        else:
            data_file = prev_output
        output_file = OUTPUT_DIR / step["default_output"]
        _run_llm_step(step, data_file, output_file)
        prev_output = output_file

    merged_file = prev_output

    print("\n" + "=" * 60)
    print("PHASE 1.5: Keyword Discovery & Turn Labeling")
    print("=" * 60)

    records = _load_py_results(merged_file)
    print(f"Loaded {len(records)} records from {merged_file.name}")

    print(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] Running discover_keywords...")
    import f000_keyword_discovery.discover_keywords as dk
    taxonomy = dk.discover_keywords(records)
    print(f"  Facts: {len(taxonomy.get('facts', []))}, "
          f"Emotions: {len(taxonomy.get('emotions', []))}, "
          f"Actions: {len(taxonomy.get('collector_actions', []))}, "
          f"Willingness levels: {len(taxonomy.get('willingness_levels', []))}")

    print("\n" + "=" * 60)
    print("PHASE 2: Aggregation (from Phase 1.5 taxonomy)")
    print("=" * 60)

    collector_result = {"collector_actions": taxonomy.get("collector_actions", [])}
    collector_out = ANALYSIS_OUTPUTS["analyze_collector_turns"]
    with open(collector_out, "w", encoding="utf-8") as f:
        json.dump(collector_result, f, ensure_ascii=False, indent=2)
    print(f"  Collector analysis written to {collector_out.name}")
    print(f"  Found {len(collector_result.get('collector_actions', []))} action groups")

    customer_result = {"facts": taxonomy.get("facts", []), "emotions": taxonomy.get("emotions", [])}
    customer_out = ANALYSIS_OUTPUTS["analyze_customer_turns"]
    with open(customer_out, "w", encoding="utf-8") as f:
        json.dump(customer_result, f, ensure_ascii=False, indent=2)
    print(f"  Customer analysis written to {customer_out.name}")
    print(f"  Facts: {len(customer_result.get('facts', []))}, "
          f"Emotions: {len(customer_result.get('emotions', []))}")

    print("\n" + "=" * 60)
    print("PHASE 3: Schema Alignment + State Relabeling")
    print("=" * 60)

    print(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] Aligning schema...")
    import f001_schema_alignment.align_schema as als
    aligned = als.align_all(records)
    print(f"  Aligned {len(aligned)} records")

    print(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] Relabeling facts and emotions...")
    import f001_schema_alignment.relabel_state as rs
    relabeled, stats = rs.relabel_all(aligned)
    aligned_out = ANALYSIS_OUTPUTS["align_schema"]
    _write_py_results(relabeled, aligned_out)
    print(f"  Aligned+relabeled output written to {aligned_out.name}")
    print(f"  Fact map: {stats['fact_map_size']} entries, {len(stats['facts_relabeled'])} tags relabeled")
    print(f"  Emotion map: {stats['emotion_map_size']} entries, {len(stats['emotions_relabeled'])} tags relabeled")

    print("\n" + "=" * 60)
    print("PHASE 4: Reward Labeling")
    print("=" * 60)

    print(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] Running reward_label...")
    import f003_reward_labeling.reward_label as rl
    rewarded = rl.label_all(relabeled)
    reward_out = ANALYSIS_OUTPUTS["reward_label"]
    _write_py_results(rewarded, reward_out)
    print(f"  Reward output written to {reward_out.name}")
    reward_count = sum(1 for r in rewarded if r.get("reward") == 1)
    print(f"  Rewarded (R=1): {reward_count}/{len(rewarded)}")

    print("\n" + "=" * 60)
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Pipeline complete.")
    print("Outputs:")
    for _name, out in ANALYSIS_OUTPUTS.items():
        print(f"  {out}")
    for step in LLM_STEPS:
        print(f"  {step['default_output']}")
    print("=" * 60)


def _run_skip_llm(args) -> None:
    if args.merged_file:
        merged = args.merged_file.resolve()
    else:
        merged = OUTPUT_DIR / "output_merged.py"
    if not merged.exists():
        print(f"Merged file not found: {merged}")
        sys.exit(1)
    print(f"Skipping Phase 1. Loading records from {merged}...")
    records = _load_py_results(merged)
    print(f"Loaded {len(records)} records. Running analysis and reward phases...")

    print(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] Running discover_keywords...")
    import f000_keyword_discovery.discover_keywords as dk
    taxonomy = dk.discover_keywords(records)
    print(f"  Facts: {len(taxonomy.get('facts', []))}, "
          f"Emotions: {len(taxonomy.get('emotions', []))}, "
          f"Actions: {len(taxonomy.get('collector_actions', []))}, "
          f"Willingness levels: {len(taxonomy.get('willingness_levels', []))}")

    collector_result = {"collector_actions": taxonomy.get("collector_actions", [])}
    with open(ANALYSIS_OUTPUTS["analyze_collector_turns"], "w", encoding="utf-8") as f:
        json.dump(collector_result, f, ensure_ascii=False, indent=2)

    customer_result = {"facts": taxonomy.get("facts", []), "emotions": taxonomy.get("emotions", [])}
    with open(ANALYSIS_OUTPUTS["analyze_customer_turns"], "w", encoding="utf-8") as f:
        json.dump(customer_result, f, ensure_ascii=False, indent=2)

    import f001_schema_alignment.align_schema as als
    aligned = als.align_all(records)

    import f001_schema_alignment.relabel_state as rs
    relabeled, stats = rs.relabel_all(aligned)
    _write_py_results(relabeled, ANALYSIS_OUTPUTS["align_schema"])
    print(f"  Relabeled {len(stats['facts_relabeled'])} fact tags, {len(stats['emotions_relabeled'])} emotion tags")

    import f003_reward_labeling.reward_label as rl
    rewarded = rl.label_all(relabeled)
    _write_py_results(rewarded, ANALYSIS_OUTPUTS["reward_label"])
    print("Done.")


def _run_with_scheduler(input_file: Path, forbid_start: int, forbid_end: int, interval: int) -> None:
    from f007_infrastructure.scheduler_state import SchedulerState, persist_run, should_run_pipeline

    state = SchedulerState(DATA_DIR / ".scheduler_state.json")
    last_run_date = state.load_last_run_date()
    current_date = datetime.now().date()
    ran_today = last_run_date is not None and last_run_date == current_date
    print(f"Scheduler enabled — forbidden hours: {forbid_start}:00 – {forbid_end}:00")
    print(f"Checking every {interval}s")
    print(f"Last run date: {last_run_date}\n")

    while True:
        now = datetime.now()
        if _is_within_allowed_hours(forbid_start, forbid_end):
            current_date = now.date()
            if should_run_pipeline(ran_today, last_run_date, current_date):
                print(f"\n[{now:%Y-%m-%d %H:%M:%S}] Outside forbidden hours. Running pipeline...")
                run_pipeline(input_file)
                ran_today = True
                last_run_date = current_date
                if not persist_run(state, current_date):
                    print(f"[{now:%Y-%m-%d %H:%M:%S}] Warning: failed to persist scheduler state")
                print(f"[{now:%Y-%m-%d %H:%M:%S}] Pipeline finished for today. Sleeping until tomorrow...\n")
            else:
                print(f"[{now:%Y-%m-%d %H:%M:%S}] Already ran today. Sleeping...")
        else:
            ran_today = False
            print(f"[{now:%Y-%m-%d %H:%M:%S}] Within forbidden hours ({forbid_start}:00–{forbid_end}:00). Sleeping...")

        time.sleep(interval)


_DEFAULT_INPUT = INPUT_DIR / str(_cfg("pipeline.default_data_file", "matched_data.jsonl"))

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the full pipeline: clean → logic → complete → merge → discover → analysis → reward"
    )
    parser.add_argument(
        "input_file",
        type=Path,
        nargs="?",
        default=_DEFAULT_INPUT,
        help="Input data file (default: matched_data.jsonl)",
    )
    parser.add_argument(
        "--skip-llm", action="store_true",
        help="Skip Phase 1 (LLM cleaning) and use an existing merged file",
    )
    parser.add_argument(
        "--merged-file", type=Path,
        default=None,
        help="Path to an existing merged output to use when --skip-llm is set",
    )
    parser.add_argument(
        "--forbid-start", type=int, default=None,
        help="Hour (0–23) when the forbidden window starts",
    )
    parser.add_argument(
        "--forbid-end", type=int, default=None,
        help="Hour (0–23) when the forbidden window ends (default: 5 if --forbid-start is set)",
    )
    parser.add_argument(
        "--interval", type=int, default=_cfg("pipeline.scheduler_interval", 600),
        help="Sleep interval in seconds between scheduler checks (default: 600)",
    )
    args = parser.parse_args()

    if args.skip_llm:
        _run_skip_llm(args)
        return

    input_file = args.input_file.resolve()
    if not input_file.exists():
        print(f"Input file not found: {input_file}")
        sys.exit(1)

    if args.forbid_start is not None:
        forbid_start = args.forbid_start
        forbid_end = args.forbid_end if args.forbid_end is not None else forbid_start + 1
        _run_with_scheduler(input_file, forbid_start, forbid_end, args.interval)
    else:
        print(f"Pipeline started. Input: {input_file}")
        run_pipeline(input_file)


if __name__ == "__main__":
    main()
