import importlib.util
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"

LLM_STEPS = [
    {
        "name": "data_clean_2",
        "script": DATA_DIR / "(llm) data_clean_2.py",
        "default_output": "data_clean_2_output.py",
    },
    {
        "name": "data_logic",
        "script": DATA_DIR / "(llm) data_logic.py",
        "default_output": "data_logic_output.py",
    },
    {
        "name": "data_complete",
        "script": DATA_DIR / "(llm) data_complete.py",
        "default_output": "data_complete_output.py",
    },
    {
        "name": "data_merge",
        "script": DATA_DIR / "(llm) data_merge.py",
        "default_output": "data_merged_output.py",
    },
]

ANALYSIS_OUTPUTS = {
    "analyze_collector_turns": DATA_DIR / "collector_analysis.json",
    "analyze_customer_turns": DATA_DIR / "customer_analysis.json",
    "align_schema": BASE_DIR / "f001_schema_alignment" / "output_aligned.py",
    "reward_label": BASE_DIR / "f003_reward_labeling" / "output_rewarded.py",
}


def _load_py_results(path: Path) -> list[dict]:
    spec = importlib.util.spec_from_file_location("results_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.results


def _write_py_results(results: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("results = ")
        text = json.dumps(results, ensure_ascii=False, indent=2)
        text = text.replace(": null", ": None").replace(": true", ": True").replace(": false", ": False")
        f.write(text)
        f.write("\n")


def _run_llm_step(step: dict, data_file: Path, output_file: Path) -> None:
    existing_pythonpath = subprocess.os.environ.get("PYTHONPATH", "")
    infra_path = str(BASE_DIR / "infra")
    new_pythonpath = f"{infra_path}:{existing_pythonpath}" if existing_pythonpath else infra_path
    env = {
        **subprocess.os.environ,
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


def _run_skip_llm(args) -> None:
    if args.merged_file:
        merged = args.merged_file.resolve()
    else:
        merged = DATA_DIR / "data_merged_output.py"
    if not merged.exists():
        print(f"Merged file not found: {merged}")
        sys.exit(1)
    print(f"Skipping Phase 1. Loading records from {merged}...")
    records = _load_py_results(merged)
    print(f"Loaded {len(records)} records. Running analysis and reward phases...")

    import f003_reward_labeling.analyze_collector_turns as act
    collector_result = act.analyze_collector_turns(records)
    with open(ANALYSIS_OUTPUTS["analyze_collector_turns"], "w", encoding="utf-8") as f:
        json.dump(collector_result, f, ensure_ascii=False, indent=2)

    import f003_reward_labeling.analyze_customer_turns as acust
    customer_result = acust.analyze_customer_turns(records)
    with open(ANALYSIS_OUTPUTS["analyze_customer_turns"], "w", encoding="utf-8") as f:
        json.dump(customer_result, f, ensure_ascii=False, indent=2)

    import f001_schema_alignment.align_schema as als
    aligned = als.align_all(records)
    _write_py_results(aligned, ANALYSIS_OUTPUTS["align_schema"])
    import f003_reward_labeling.reward_label as rl
    rewarded = rl.label_all(aligned)
    _write_py_results(rewarded, ANALYSIS_OUTPUTS["reward_label"])
    print("Done.")


def _run_with_scheduler(input_file: Path, forbid_start: int, forbid_end: int, interval: int) -> None:
    print(f"Scheduler enabled — forbidden hours: {forbid_start}:00 – {forbid_end}:00")
    print(f"Checking every {interval}s\n")
    ran_today = False

    while True:
        now = datetime.now()
        if _is_within_allowed_hours(forbid_start, forbid_end):
            if not ran_today:
                print(f"\n[{now:%Y-%m-%d %H:%M:%S}] Outside forbidden hours. Running pipeline...")
                from old_files.run_pipeline import run_pipeline
                run_pipeline(input_file)
                ran_today = True
                print(f"[{now:%Y-%m-%d %H:%M:%S}] Pipeline finished for today. Sleeping until tomorrow...\n")
            else:
                print(f"[{now:%Y-%m-%d %H:%M:%S}] Already ran today. Sleeping...")
        else:
            ran_today = False
            print(f"[{now:%Y-%m-%d %H:%M:%S}] Within forbidden hours ({forbid_start}:00–{forbid_end}:00). Sleeping...")

        time.sleep(interval)
