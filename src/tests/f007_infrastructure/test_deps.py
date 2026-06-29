def test_psycopg2_importable():
    import psycopg2
    assert psycopg2 is not None


def test_pgvector_importable():
    from pgvector.psycopg2 import register_vector
    assert register_vector is not None


def test_numpy_importable():
    import numpy as np
    assert np is not None
