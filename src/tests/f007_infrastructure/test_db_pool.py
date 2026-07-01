from unittest.mock import MagicMock, patch

from f007_infrastructure.db import SentenceDB


def _make_mock_pool(mock_conn):
    pool = MagicMock()
    pool.getconn.return_value = mock_conn
    return pool


def test_uses_threaded_connection_pool():
    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_pool = _make_mock_pool(mock_conn)
    with patch("f007_infrastructure.db.psycopg2.pool.ThreadedConnectionPool", return_value=mock_pool), \
         patch("f007_infrastructure.db.register_vector"):
        db = SentenceDB("dsn")
    assert db._pool is mock_pool


def test_connection_context_manager_checks_out_and_returns():
    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_pool = _make_mock_pool(mock_conn)
    with patch("f007_infrastructure.db.psycopg2.pool.ThreadedConnectionPool", return_value=mock_pool), \
         patch("f007_infrastructure.db.register_vector"):
        db = SentenceDB("dsn")
        with db.connection() as conn:
            assert conn is mock_conn
    mock_pool.getconn.assert_called_once()
    mock_pool.putconn.assert_called_once_with(mock_conn)


def test_closed_connection_gets_replaced():
    closed_conn = MagicMock()
    closed_conn.closed = 2
    fresh_conn = MagicMock()
    fresh_conn.closed = 0
    mock_pool = MagicMock()
    mock_pool.getconn.side_effect = [closed_conn, fresh_conn]
    with patch("f007_infrastructure.db.psycopg2.pool.ThreadedConnectionPool", return_value=mock_pool), \
         patch("f007_infrastructure.db.register_vector"):
        db = SentenceDB("dsn")
        with db.connection() as conn:
            assert conn is fresh_conn
    mock_pool.putconn.assert_any_call(closed_conn, close=True)


def test_close_closes_pool():
    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_pool = _make_mock_pool(mock_conn)
    with patch("f007_infrastructure.db.psycopg2.pool.ThreadedConnectionPool", return_value=mock_pool), \
         patch("f007_infrastructure.db.register_vector"):
        db = SentenceDB("dsn")
        db.close()
    mock_pool.closeall.assert_called_once()


def test_pool_max_from_config():
    mock_conn = MagicMock()
    mock_conn.closed = False
    with patch("f007_infrastructure.db.psycopg2.pool.ThreadedConnectionPool") as mock_ctor, \
         patch("f007_infrastructure.db.register_vector"):
        mock_ctor.return_value = _make_mock_pool(mock_conn)
        SentenceDB("dsn", pool_max=5)
    call_args = mock_ctor.call_args
    assert call_args[0][1] == 5  # second positional arg = maxconn


def test_concurrent_access_uses_pool():
    import threading

    mock_conn = MagicMock()
    mock_conn.closed = False
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = []
    mock_cursor.fetchone.return_value = None
    mock_conn.cursor.return_value = mock_cursor

    mock_pool = _make_mock_pool(mock_conn)
    errors = []

    with patch("f007_infrastructure.db.psycopg2.pool.ThreadedConnectionPool", return_value=mock_pool), \
         patch("f007_infrastructure.db.register_vector"):
        db = SentenceDB("dsn")

        def worker():
            try:
                db.get_node_by_signature("sig")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert not errors
    assert mock_pool.getconn.call_count == 10
    assert mock_pool.putconn.call_count == 10
