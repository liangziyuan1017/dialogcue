import csv
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from f007_infrastructure import label_relabel as lr


@pytest.fixture
def temp_csv(tmp_path, monkeypatch):
    monkeypatch.setattr(lr, "_DATA_LABELS_DIR", tmp_path)
    lr._FACT_CSV_MAP = {}
    lr._EMOTION_CSV_MAP = {}
    return tmp_path


def test_concurrent_appends_no_corruption(temp_csv):
    n_threads = 50
    per_thread = 4

    def write_batch(tid):
        mappings = {f"tag_{tid}_{i}": f"canonical_{tid}_{i}" for i in range(per_thread)}
        lr.append_relabel_to_csv("facts", mappings)

    with ThreadPoolExecutor(max_workers=n_threads) as pool:
        list(pool.map(write_batch, range(n_threads)))

    path = temp_csv / "facts_relabeled.csv"
    rows = list(csv.DictReader(open(path, newline="")))
    assert len(rows) == n_threads * per_thread
    tags = {r["tag"] for r in rows}
    assert len(tags) == n_threads * per_thread


def test_concurrent_map_updates_no_lost_entries(temp_csv):
    n_threads = 50
    map_obj = {}
    barrier = threading.Barrier(n_threads)

    def update_batch(tid):
        barrier.wait()
        with lr._relabel_lock:
            for i in range(10):
                map_obj[f"t{tid}_{i}"] = f"c{tid}_{i}"

    with ThreadPoolExecutor(max_workers=n_threads) as pool:
        list(pool.map(update_batch, range(n_threads)))

    assert len(map_obj) == n_threads * 10
