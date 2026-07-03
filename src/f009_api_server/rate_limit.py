"""Per-IP token-bucket rate limiter for the API server (F012 Phase C, item 2.1).

Token bucket: each IP has a bucket of capacity `burst` tokens, refilled at
`rate_rps` tokens/second. Each allowed request consumes 1 token. When the
bucket is empty the request is rejected (429).
"""

import time


class RateLimiter:
    def __init__(self, rate_rps: float, burst: int, clock=time.monotonic):
        self.rate = float(rate_rps)
        self.burst = int(burst)
        self._clock = clock
        self._buckets: dict[str, list] = {}

    def allow(self, ip: str) -> bool:
        now = self._clock()
        bucket = self._buckets.get(ip)
        if bucket is None:
            bucket = [float(self.burst), now]
            self._buckets[ip] = bucket
        tokens, last = bucket[0], bucket[1]
        tokens = min(float(self.burst), tokens + (now - last) * self.rate)
        if tokens >= 1.0:
            tokens -= 1.0
            bucket[0] = tokens
            bucket[1] = now
            return True
        bucket[0] = tokens
        bucket[1] = now
        return False
