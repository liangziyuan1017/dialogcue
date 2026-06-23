import random
import time


def retry_call(fn, *args, max_retries=3, min_sleep=1, max_sleep=5, on_fail=None, **kwargs):
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                sleep_time = random.uniform(min_sleep, max_sleep)
                print(f"  Retry {attempt + 1}/{max_retries} after {sleep_time:.1f}s (error: {e})")
                time.sleep(sleep_time)
            else:
                if on_fail is not None:
                    return on_fail(last_exc)
                raise
