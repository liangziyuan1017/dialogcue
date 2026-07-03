import asyncio
from datetime import datetime, timedelta

from f009_api_server.session_store import SessionStore


def test_cap_enforced():
    store = SessionStore(max_sessions=3, ttl=1800)
    for i in range(3):
        store.create(cust_no=f"c{i}", context={})
    assert len(store) == 3
    sid = store.create(cust_no="overflow", context={})
    assert sid is not None
    assert len(store) <= 3


def test_ttl_eviction():
    now = datetime(2026, 7, 2, 12, 0, 0)
    store = SessionStore(max_sessions=100, ttl=10, clock=lambda: now)
    sid = store.create(cust_no="c", context={})
    assert store.get(sid) is not None
    store._clock = lambda: now + timedelta(seconds=11)
    store.evict_expired()
    assert store.get(sid) is None


def test_per_session_lock_serializes_concurrent_writes():
    store = SessionStore(max_sessions=100, ttl=1800)
    sid = store.create(cust_no="c", context={})
    order = []

    async def writer(label, delay):
        async with store.lock(sid):
            order.append(f"{label}-start")
            await asyncio.sleep(delay)
            order.append(f"{label}-end")

    async def main():
        await asyncio.gather(writer("a", 0.02), writer("b", 0.01))

    asyncio.run(main())
    assert order == ["a-start", "a-end", "b-start", "b-end"] or order == ["b-start", "b-end", "a-start", "a-end"]


def test_get_returns_none_for_unknown():
    store = SessionStore(max_sessions=100, ttl=1800)
    assert store.get("nope") is None


def test_remove_returns_session():
    store = SessionStore(max_sessions=100, ttl=1800)
    sid = store.create(cust_no="c", context={})
    removed = store.remove(sid)
    assert removed is not None
    assert store.get(sid) is None
    assert store.remove(sid) is None
