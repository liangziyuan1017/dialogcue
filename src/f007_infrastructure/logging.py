import json
import logging
import sys
from contextvars import ContextVar

from f007_infrastructure.config import get as _cfg

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

_loggers: dict[str, logging.Logger] = {}


def bind_request_id(rid: str | None) -> str | None:
    return _request_id.set(rid)


def get_request_id() -> str | None:
    return _request_id.get()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": _request_id.get(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str, level: str | None = None) -> logging.Logger:
    if name in _loggers:
        return _loggers[name]
    if level is None:
        level = _cfg("logging.level", "INFO")
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False
    _loggers[name] = logger
    return logger
