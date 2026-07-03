from datetime import date

from f007_infrastructure.scheduler_state import SchedulerState, persist_run, should_run_pipeline


class TestSchedulerStatePersistence:
    def test_load_returns_none_when_file_missing(self, tmp_path):
        state = SchedulerState(tmp_path / "state.json")
        assert state.load_last_run_date() is None

    def test_save_then_load_roundtrip(self, tmp_path):
        state = SchedulerState(tmp_path / "state.json")
        d = date(2026, 7, 3)
        state.save_last_run_date(d)
        assert state.load_last_run_date() == d

    def test_save_overwrites_previous(self, tmp_path):
        state = SchedulerState(tmp_path / "state.json")
        state.save_last_run_date(date(2026, 7, 2))
        state.save_last_run_date(date(2026, 7, 3))
        assert state.load_last_run_date() == date(2026, 7, 3)

    def test_load_corrupt_file_returns_none(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text("not json")
        state = SchedulerState(p)
        assert state.load_last_run_date() is None

    def test_load_invalid_date_string_returns_none(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text('{"last_run_date": "not-a-date"}')
        state = SchedulerState(p)
        assert state.load_last_run_date() is None

    def test_load_missing_last_run_date_key_returns_none(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text("{}")
        state = SchedulerState(p)
        assert state.load_last_run_date() is None


class TestPersistRun:
    def test_returns_true_on_success(self, tmp_path):
        state = SchedulerState(tmp_path / "state.json")
        assert persist_run(state, date(2026, 7, 3)) is True
        assert state.load_last_run_date() == date(2026, 7, 3)

    def test_returns_false_on_failure(self, tmp_path):
        ro_dir = tmp_path / "readonly"
        ro_dir.mkdir()
        ro_dir.chmod(0o444)
        state = SchedulerState(ro_dir / "state.json")
        assert persist_run(state, date(2026, 7, 3)) is False


class TestShouldRunPipeline:
    def test_runs_when_not_ran_and_no_last_run(self):
        assert should_run_pipeline(False, None, date(2026, 7, 3)) is True

    def test_does_not_run_when_already_ran_today(self):
        assert should_run_pipeline(True, date(2026, 7, 3), date(2026, 7, 3)) is False

    def test_does_not_run_when_last_run_is_today(self):
        assert should_run_pipeline(False, date(2026, 7, 3), date(2026, 7, 3)) is False

    def test_runs_when_last_run_is_yesterday(self):
        assert should_run_pipeline(False, date(2026, 7, 2), date(2026, 7, 3)) is True

    def test_does_not_run_when_ran_today_even_if_last_run_yesterday(self):
        assert should_run_pipeline(True, date(2026, 7, 2), date(2026, 7, 3)) is False


class TestRestartScenarios:
    def test_restart_same_day_no_rerun(self, tmp_path):
        state = SchedulerState(tmp_path / "state.json")
        today = date(2026, 7, 3)
        state.save_last_run_date(today)
        last_run_date = state.load_last_run_date()
        ran_today = last_run_date is not None and last_run_date == today
        assert should_run_pipeline(ran_today, last_run_date, today) is False

    def test_restart_next_day_runs(self, tmp_path):
        state = SchedulerState(tmp_path / "state.json")
        state.save_last_run_date(date(2026, 7, 3))
        today = date(2026, 7, 4)
        last_run_date = state.load_last_run_date()
        ran_today = last_run_date is not None and last_run_date == today
        assert should_run_pipeline(ran_today, last_run_date, today) is True

    def test_fresh_start_runs(self, tmp_path):
        state = SchedulerState(tmp_path / "state.json")
        today = date(2026, 7, 3)
        last_run_date = state.load_last_run_date()
        ran_today = last_run_date is not None and last_run_date == today
        assert should_run_pipeline(ran_today, last_run_date, today) is True
