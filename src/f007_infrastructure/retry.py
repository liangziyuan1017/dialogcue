import random
import time

from f007_infrastructure.config import get as _cfg
from f007_infrastructure.logging import get_logger as _get_logger
_log = _get_logger(__name__)


def retry_call(fn, *args, max_retries=None, min_sleep=None, max_sleep=None, on_fail=None, **kwargs):
    if max_retries is None:
        max_retries = _cfg("retry.max_retries", 3)
    if min_sleep is None:
        min_sleep = _cfg("retry.min_sleep", 1)
    if max_sleep is None:
        max_sleep = _cfg("retry.max_sleep", 5)
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                sleep_time = random.uniform(min_sleep, max_sleep)
                _log.warning(f"Retry {attempt + 1}/{max_retries} after {sleep_time:.1f}s (error: {e})")
                time.sleep(sleep_time)
            else:
                if on_fail is not None:
                    return on_fail(last_exc)
                raise
