import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from old_files.pipeline_steps import (
    ANALYSIS_OUTPUTS,
    DATA_DIR,
    LLM_STEPS,
    _load_py_results,
    _run_llm_step,
    _run_skip_llm,
    _run_with_scheduler,
    _write_py_results,
)


def run_pipeline(input_file: Path) -> None:
    print("=" * 60)
    print("PHASE 1: LLM Data Cleaning")
    print("=" * 60)

    prev_output = input_file
    for step in LLM_STEPS:
        if step["name"] == "data_merge":
            data_file = input_file
            merge_output = DATA_DIR / step["default_output"]
            if prev_output != input_file:
                import shutil
                shutil.copy2(prev_output, merge_output)
                print(f"  Pre-populated {merge_output.name} from {prev_output.name}")
        else:
            data_file = prev_output
        output_file = DATA_DIR / step["default_output"]
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
    print("PHASE 2: Collector & Customer Turn Analysis")
    print("=" * 60)

    print(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] Running analyze_collector_turns...")
    import f003_reward_labeling.analyze_collector_turns as act
    collector_result = act.analyze_collector_turns(records)
    collector_out = ANALYSIS_OUTPUTS["analyze_collector_turns"]
    with open(collector_out, "w", encoding="utf-8") as f:
        json.dump(collector_result, f, ensure_ascii=False, indent=2)
    print(f"  Collector analysis written to {collector_out.name}")
    print(f"  Found {len(collector_result.get('collector_actions', []))} action groups")

    print(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] Running analyze_customer_turns...")
    import f003_reward_labeling.analyze_customer_turns as acust
    customer_result = acust.analyze_customer_turns(records)
    customer_out = ANALYSIS_OUTPUTS["analyze_customer_turns"]
    with open(customer_out, "w", encoding="utf-8") as f:
        json.dump(customer_result, f, ensure_ascii=False, indent=2)
    print(f"  Customer analysis written to {customer_out.name}")
    print(f"  Facts: {len(customer_result.get('facts', []))}, "
          f"Emotions: {len(customer_result.get('emotions', []))}")

    print("\n" + "=" * 60)
    print("PHASE 3: Reward Labeling")
    print("=" * 60)

    print(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] Aligning schema...")
    import f001_schema_alignment.align_schema as als
    aligned = als.align_all(records)
    aligned_out = ANALYSIS_OUTPUTS["align_schema"]
    _write_py_results(aligned, aligned_out)
    print(f"  Aligned {len(aligned)} records → {aligned_out.name}")

    print(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] Running reward_label...")
    import f003_reward_labeling.reward_label as rl
    rewarded = rl.label_all(aligned)
    reward_out = ANALYSIS_OUTPUTS["reward_label"]
    _write_py_results(rewarded, reward_out)
    print(f"  Reward output written to {reward_out.name}")
    reward_count = sum(1 for r in rewarded if r.get("reward") == 1)
    print(f"  Rewarded (R=1): {reward_count}/{len(rewarded)}")

    print("\n" + "=" * 60)
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Pipeline complete.")
    print(f"Outputs:")
    for name, out in ANALYSIS_OUTPUTS.items():
        print(f"  {out}")
    for step in LLM_STEPS:
        print(f"  {step['default_output']}")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the full pipeline: clean → logic → complete → merge → analysis → reward"
    )
    parser.add_argument(
        "input_file",
        type=Path,
        nargs="?",
        default=DATA_DIR / "matched_data.jsonl",
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
        "--interval", type=int, default=600,
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
