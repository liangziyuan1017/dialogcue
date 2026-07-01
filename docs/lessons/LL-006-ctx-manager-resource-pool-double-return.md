---
id: LL-006
title: Context manager resource pool — guard against double-return in error handler
status: accepted
created: 2026-07-01
related: [F012, ADR-027]
---

# LL-006: Context Manager Resource Pool — Double-Return in Error Handler

## Context

F012 Phase B introduced a `connection()` context manager on `SentenceDB` that
checks out a connection from a `ThreadedConnectionPool` and returns it on exit.
The error handler for `OperationalError` closes the connection via
`pool.putconn(conn, close=True)`.

## Pitfall

If `putconn(conn, close=True)` itself raises (e.g., pool already closed), the
`returned` flag is never set to `True`, so the `finally` block calls
`pool.putconn(conn)` again — a **double-return** of the same connection to the
pool. This can corrupt pool internal state or raise a masking exception that
hides the original `OperationalError`.

## Guard

When returning a resource in an `except` block before a `finally` that also
returns it:

1. Set the "already returned" flag **before** calling the return function,
   not after.
2. Wrap the return call in `try/except` so a failure there doesn't mask the
   original exception.
3. The `finally` block checks the flag and only returns if not already returned.

```python
except SomeError:
    returned = True          # set BEFORE the call
    try:
        pool.putconn(conn, close=True)
    except Exception:
        pass
    raise
finally:
    if not returned:
        pool.putconn(conn)
```

## Scope

Applies to any context manager that checks out a pooled resource and has
error-specific cleanup before the standard `finally` return.

## Decision

Accepted 2026-07-01. Pattern applied in `db.py:connection()`.
