from unittest.mock import MagicMock

from f009_api_server.rate_limit import RateLimiter


def test_token_bucket_allows_up_to_burst():
    rl = RateLimiter(rate_rps=10, burst=5, clock=MagicMock(side_effect=[0.0] * 100))
    for _ in range(5):
        assert rl.allow("1.2.3.4") is True


def test_token_bucket_rejects_over_burst_immediately():
    rl = RateLimiter(rate_rps=10, burst=5, clock=MagicMock(side_effect=[0.0] * 100))
    for _ in range(5):
        rl.allow("1.2.3.4")
    assert rl.allow("1.2.3.4") is False


def test_token_bucket_refills_over_time():
    times = [0.0] * 6 + [1.0]
    rl = RateLimiter(rate_rps=10, burst=5, clock=MagicMock(side_effect=times))
    for _ in range(5):
        rl.allow("ip")
    assert rl.allow("ip") is False  # exhausted at t=0
    assert rl.allow("ip") is True   # t=1 → 10 tokens refilled, capped at burst=5


def test_rate_limiter_isolated_per_ip():
    rl = RateLimiter(rate_rps=1, burst=1, clock=MagicMock(side_effect=[0.0] * 100))
    assert rl.allow("a") is True
    assert rl.allow("a") is False
    assert rl.allow("b") is True
