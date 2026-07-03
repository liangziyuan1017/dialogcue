"""Scheduler state persistence (F012 Phase F, AC-F3).

Persists ``last_run_date`` to a JSON file so that a process restart
within the same calendar day does not trigger a duplicate pipeline run.
"""

import json
from datetime import date
from pathlib import Path


class SchedulerState:
    def __init__(self, path: Path):
        self._path = Path(path)

    def load_last_run_date(self) -> date | None:
        if not self._path.exists():
            return None
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        s = data.get("last_run_date")
        if not s:
            return None
        try:
            return date.fromisoformat(s)
        except ValueError:
            return None

    def save_last_run_date(self, d: date) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps({"last_run_date": d.isoformat()}), encoding="utf-8")


def should_run_pipeline(ran_today: bool, last_run_date: date | None, today: date) -> bool:
    if ran_today:
        return False
    if last_run_date is not None and last_run_date == today:
        return False
    return True


def persist_run(state: SchedulerState, run_date: date) -> bool:
    try:
        state.save_last_run_date(run_date)
        return True
    except Exception:
        return False
