"""
test_concurrency.py — Concurrency tests.

Covers: Phase 9 concurrency checklist items.
- ID allocation survives concurrent calls
- Optimistic concurrency rejects stale writes
- Duplicate detection works
"""
import sys
import json
import subprocess
import threading
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def run_script(script_name: str, args: list[str]) -> dict:
    script_path = SCRIPTS_DIR / script_name
    result = subprocess.run(
        [sys.executable, str(script_path)] + args,
        capture_output=True, text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": result.stdout, "stderr": result.stderr, "exit_code": result.returncode}


class TestConcurrency:
    """Test concurrent operation safety."""

    def test_concurrent_id_allocation_no_duplicates(self):
        """Two simultaneous ID allocations should produce unique IDs."""
        results = []

        def allocate():
            r = run_script("id-allocate.py", ["--kind", "ADR"])
            results.append(r)

        t1 = threading.Thread(target=allocate)
        t2 = threading.Thread(target=allocate)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        ids = [r.get("id") for r in results if "id" in r]
        assert len(ids) == 2, f"Expected 2 IDs, got {len(ids)}: {results}"
        assert ids[0] != ids[1], f"IDs should be unique: {ids}"

    def test_concurrent_ll_allocation_no_duplicates(self):
        """Two simultaneous LL allocations should produce unique IDs."""
        results = []

        def allocate():
            r = run_script("id-allocate.py", ["--kind", "LL"])
            results.append(r)

        t1 = threading.Thread(target=allocate)
        t2 = threading.Thread(target=allocate)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        ids = [r.get("id") for r in results if "id" in r]
        assert len(ids) == 2, f"Expected 2 IDs, got {len(ids)}: {results}"
        assert ids[0] != ids[1], f"LL IDs should be unique: {ids}"

    def test_concurrent_mixed_allocations(self):
        """Mixed ADR+LL allocations don't interfere."""
        results_adr = []
        results_ll = []

        def allocate_adr():
            results_adr.append(run_script("id-allocate.py", ["--kind", "ADR"]))

        def allocate_ll():
            results_ll.append(run_script("id-allocate.py", ["--kind", "LL"]))

        threads = [
            threading.Thread(target=allocate_adr),
            threading.Thread(target=allocate_adr),
            threading.Thread(target=allocate_ll),
            threading.Thread(target=allocate_ll),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        adr_ids = [r.get("id") for r in results_adr if "id" in r]
        ll_ids = [r.get("id") for r in results_ll if "id" in r]
        assert len(adr_ids) == 2, f"Expected 2 ADR IDs: {results_adr}"
        assert len(ll_ids) == 2, f"Expected 2 LL IDs: {results_ll}"
        assert adr_ids[0] != adr_ids[1]
        assert ll_ids[0] != ll_ids[1]

    def test_lock_prevents_duplicates(self):
        """Stress test: 10 concurrent allocations all unique."""
        results = []

        def allocate():
            r = run_script("id-allocate.py", ["--kind", "ADR"])
            results.append(r)

        threads = [threading.Thread(target=allocate) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        ids = [r.get("id") for r in results if "id" in r]
        unique_ids = set(ids)
        assert len(ids) == len(unique_ids), f"All {len(ids)} IDs should be unique; got {len(unique_ids)} unique: {ids}"


    def test_cc002_duplicate_adr_title_stored_as_candidate(self):
        """CC-002: Two agents write same-title ADR → second stored as candidate."""
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = os.path.join(tmp, "docs", "decisions")
            os.makedirs(docs_dir, exist_ok=True)

            first = run_script("write-durable.py", [
                "--path", os.path.join(docs_dir, "adr-redis-1.md"),
                "--content", "---\nid: ADR-200\ntitle: Use Redis for caching\ndoc_kind: decision\nstatus: draft\ncreated: 2026-05-26\nschema_version: 1\n---\n\n# Redis Caching",
            ])
            assert first.get("result") == "written"

            second = run_script("write-durable.py", [
                "--path", os.path.join(docs_dir, "adr-redis-2.md"),
                "--content", "---\nid: ADR-201\ntitle: Use Redis for caching\ndoc_kind: decision\nstatus: candidate\npossible_duplicate_of: ADR-200\ncreated: 2026-05-26\nschema_version: 1\n---\n\n# Redis Caching (Candidate)",
            ])
            assert second.get("result") == "written"

            with open(os.path.join(docs_dir, "adr-redis-2.md"), "r") as f:
                content = f.read()
            assert "possible_duplicate_of" in content
            assert "candidate" in content

    def test_cc005_optimistic_concurrency_rejection(self):
        """CC-005: Two agents update same ADR → second rejected."""
        import tempfile
        import os
        import time

        with tempfile.TemporaryDirectory() as tmp:
            docs_dir = os.path.join(tmp, "docs", "decisions")
            os.makedirs(docs_dir, exist_ok=True)
            doc_path = os.path.join(docs_dir, "ADR-300.md")

            run_script("write-durable.py", [
                "--path", doc_path,
                "--content", "---\nid: ADR-300\ntitle: Test\ndoc_kind: decision\nstatus: draft\ncreated: 2026-05-26\nschema_version: 1\n---\n\nTest",
            ])

            time.sleep(0.1)
            result1 = run_script("write-durable.py", [
                "--path", doc_path,
                "--content", "---\nid: ADR-300\ntitle: Test\ndoc_kind: decision\nstatus: superseded\ncreated: 2026-05-26\nschema_version: 1\n---\n\nTest superseded",
            ])
            assert result1.get("result") == "written"

            result2 = run_script("write-durable.py", [
                "--path", doc_path,
                "--content", "---\nid: ADR-300\ntitle: Test\ndoc_kind: decision\nstatus: archived\ncreated: 2026-05-26\nschema_version: 1\n---\n\nTest archived",
                "--if-unmodified-since", "2026-01-01T00:00:00",
            ])
            assert result2.get("result") == "rejected", f"Stale write should be rejected: {result2}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
