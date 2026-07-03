import pytest


@pytest.fixture(autouse=True)
def _clear_extract_cache():
    from f008_state_extraction import state_extraction as se
    se._extract_cache.clear()
    se._taxonomy_version = 0
    yield
    se._extract_cache.clear()
    se._taxonomy_version = 0
