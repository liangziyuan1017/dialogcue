import io
import json
import logging

import pytest

from f007_infrastructure import logging as applog


def test_get_logger_returns_logger_with_handler():
    logger = applog.get_logger("test.a1.handler")
    assert isinstance(logger, logging.Logger)
    assert len(logger.handlers) >= 1


def test_json_formatter_emits_request_id():
    rid = applog.bind_request_id("req-abc-123")
    try:
        formatter = applog.JsonFormatter()
        record = logging.LogRecord(
            name="test.a1.json",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        out = formatter.format(record)
        parsed = json.loads(out)
        assert parsed["request_id"] == "req-abc-123"
        assert parsed["message"] == "hello"
        assert parsed["level"] == "INFO"
    finally:
        applog.bind_request_id(rid)


def test_get_logger_respects_explicit_level():
    logger = applog.get_logger("test.a1.level", level="DEBUG")
    assert logger.level == logging.DEBUG


def test_get_logger_level_from_config(monkeypatch):
    monkeypatch.setattr(applog, "_cfg", lambda key, default=None: "WARNING" if key == "logging.level" else default)
    logger = applog.get_logger("test.a1.cfglevel")
    assert logger.level == logging.WARNING


def test_get_logger_is_idempotent():
    a = applog.get_logger("test.a1.idem")
    b = applog.get_logger("test.a1.idem")
    assert a is b


def test_no_request_id_emits_null():
    applog.bind_request_id(None)
    formatter = applog.JsonFormatter()
    record = logging.LogRecord(
        name="test.a1.noid",
        level=logging.WARNING,
        pathname="",
        lineno=0,
        msg="warn",
        args=(),
        exc_info=None,
    )
    parsed = json.loads(formatter.format(record))
    assert parsed["request_id"] is None
    assert parsed["message"] == "warn"
