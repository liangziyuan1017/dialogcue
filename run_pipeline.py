import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SCRIPTS = [
    {
        "name": "data_clean_2",
        "script": BASE_DIR / "(llm) data_clean_2.py",
        "default_output": "output_2.py",
    },
    {
        "name": "data_logic",
        "script": BASE_DIR / "(llm) data_logic.py",
        "default_output": "output_logic.py",
    },
    {
        "name": "data_complete",
        "script": BASE_DIR / "(llm) data_complete.py",
        "default_output": "output_complete.py",
    },
    {
        "name": "data_polish",
        "script": BASE_DIR / "(llm) data_polish.py",
        "default_output": "output_polish.py",
    },
    {
        "name": "data_alert",
        "script": BASE_DIR / "(llm) data_alert.py",
        "default_output": "output_alert.py",
    },
    {
        "name": "data_merge",
        "script": BASE_DIR / "(llm) data_merge.py",
        "default_output": "output_merge.py",
    },
]

CHECK_INTERVAL = 600
HOUR_FORBID_START = 4
HOUR_FORBID_END = 5

def is_within_allowed_hours() -> bool:
    return not (HOUR_FORBID_START <= datetime.now().hour < HOUR_FORBID_END)


def run_step(step: dict, data_file: Path, output_file: Path) -> None:
    env = {
        **subprocess.os.environ,
        "DATA_FILE": str(data_file),
        "OUTPUT_FILE": str(output_file),
    }
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Running {step['name']}...")
    print(f"  DATA_FILE  = {data_file}")
    print(f"  OUTPUT_FILE = {output_file}")
    result = subprocess.run(
        [sys.executable, str(step["script"])],
        env=env,
        cwd=str(BASE_DIR),
    )
    if result.returncode != 0:
        print(f"  {step['name']} failed with exit code {result.returncode}")
        sys.exit(result.returncode)
    print(f"  {step['name']} completed.")


def run_pipeline(input_file: Path) -> None:
    prev_output = input_file
    for i, step in enumerate(SCRIPTS):
        if step["name"] == "data_merge":
            data_file = input_file
        else:
            data_file = prev_output
        output_file = BASE_DIR / step["default_output"]
        run_step(step, data_file, output_file)
        prev_output = output_file
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Pipeline complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the LLM data cleaning pipeline with time-based scheduling.")
    parser.add_argument("input_file", type=Path, help="Input data file (e.g. data_0520.json)")
    args = parser.parse_args()

    input_file = args.input_file.resolve()
    if not input_file.exists():
        print(f"Input file not found: {input_file}")
        sys.exit(1)

    print(f"Pipeline started. Input: {input_file}")
    print(f"Forbidden hours: {HOUR_FORBID_START}:00 - {HOUR_FORBID_END}:00")
    print(f"Checking every {CHECK_INTERVAL}s\n")

    ran_today = False

    while True:
        now = datetime.now()
        if is_within_allowed_hours():
            if not ran_today:
                print(f"\n[{now:%Y-%m-%d %H:%M:%S}] Outside forbidden hours. Running pipeline...")
                run_pipeline(input_file)
                ran_today = True
                print(f"[{now:%Y-%m-%d %H:%M:%S}] Pipeline finished for today. Sleeping until tomorrow...\n")
            else:
                print(f"[{now:%Y-%m-%d %H:%M:%S}] Already ran today. Sleeping...")
        else:
            ran_today = False
            print(f"[{now:%Y-%m-%d %H:%M:%S}] Within forbidden hours ({HOUR_FORBID_START}:00-{HOUR_FORBID_END}:00). Sleeping...")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
