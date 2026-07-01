from unittest.mock import patch

import pytest

from f007_infrastructure.retry import retry_call


class TransientError(Exception):
    pass


class PermanentError(ValueError):
    pass


def test_retries_on_retryable_exception():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientError("transient")
        return "ok"

    with patch("f007_infrastructure.retry.time.sleep"):
        result = retry_call(flaky, retryable=(TransientError,), max_retries=3, min_sleep=0.01, max_sleep=0.01)
    assert result == "ok"
    assert calls["n"] == 3


def test_does_not_retry_on_non_retryable_exception():
    calls = {"n": 0}

    def always_fails():
        calls["n"] += 1
        raise PermanentError("permanent")

    with patch("f007_infrastructure.retry.time.sleep"):
        with pytest.raises(PermanentError):
            retry_call(always_fails, retryable=(TransientError,), max_retries=3, min_sleep=0.01, max_sleep=0.01)
    assert calls["n"] == 1


def test_does_not_retry_on_value_error():
    calls = {"n": 0}

    def always_fails():
        calls["n"] += 1
        raise ValueError("bad value")

    with patch("f007_infrastructure.retry.time.sleep"):
        with pytest.raises(ValueError):
            retry_call(always_fails, retryable=(TransientError,), max_retries=3, min_sleep=0.01, max_sleep=0.01)
    assert calls["n"] == 1


def test_on_fail_callback_not_invoked_on_success():
    def ok():
        return "ok"

    def on_fail(e):
        return "fallback"
    with patch("f007_infrastructure.retry.time.sleep"):
        result = retry_call(ok, retryable=(TransientError,), max_retries=3, min_sleep=0.01, max_sleep=0.01, on_fail=on_fail)
    assert result == "ok"


def test_on_fail_callback_invoked_after_exhausting_retries():
    def always_fails():
        raise TransientError("always")

    def on_fail(e):
        return f"fallback:{e}"
    with patch("f007_infrastructure.retry.time.sleep"):
        result = retry_call(always_fails, retryable=(TransientError,), max_retries=2, min_sleep=0.01, max_sleep=0.01, on_fail=on_fail)
    assert result == "fallback:always"
