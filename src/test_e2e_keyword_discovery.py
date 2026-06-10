import json
import os
import pytest
from src.discover_keywords import discover_keywords
from src.load_data import load_records

E2E = os.environ.get("RUN_E2E") == "1"


@pytest.mark.skipif(not E2E, reason="Set RUN_E2E=1 to run e2e with real API")
def test_e2e_discover_keywords_produces_valid_taxonomy():
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "state_keywords.json")
        result = discover_keywords(output_path=out_path)

        assert "facts" in result
        assert "emotions" in result
        assert "willingness_levels" in result
        assert "collector_actions" in result

        observed_facts = [f for f in result["facts"] if f["source"] == "observed"]
        observed_emotions = [e for e in result["emotions"] if e["source"] == "observed"]
        observed_actions = [a for a in result["collector_actions"] if a["source"] == "observed"]

        assert len(observed_facts) >= 5
        assert len(observed_emotions) >= 5
        assert len(observed_actions) >= 4
        assert len(result["willingness_levels"]) >= 2

        for f in result["facts"]:
            assert "group_name" in f
            assert "keywords" in f
            assert "frequency" in f
            assert "source" in f

        for lvl in result["willingness_levels"]:
            assert "level" in lvl
            assert "definition" in lvl
            assert "boundary" in lvl
            assert "example_turns" in lvl

        with open(out_path) as fh:
            data = json.load(fh)
        assert data == result


import tempfile
