"""Contract / label / adjacency unit tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from labels import (  # noqa: E402
    adjacent_pair_set,
    emotion_labels,
    load_adjacent_config,
    willingness_labels,
)
from paths import CONFIGS, load_yaml, load_fact_schema  # noqa: E402


def test_emotion_11():
    labs = emotion_labels()
    assert len(labs) == 11
    assert labs[0] == "distress"
    assert labs[-1] == "engagement"


def test_willingness_5():
    labs = willingness_labels()
    assert labs == [
        "resistant",
        "weak",
        "conditional",
        "negotiating",
        "strong",
    ]


def test_contract_fields():
    c = load_yaml(CONFIGS / "contract.yaml")
    assert c["fact"] == "v3.1.2-patch1"
    assert c["emotion"] == "11v1"
    assert c["willingness"] == "5v1"
    assert c["adjacency"] == "none"
    assert c["context"]["max_turns"] == 4
    assert c["context"]["max_chars"] == 200
    assert c["context"]["strategy"] == "window_only"


def test_adjacent_pairs_frozen():
    cfg = load_adjacent_config()
    all_pairs = adjacent_pair_set(cfg, eval_set="all_rule")
    validated = adjacent_pair_set(cfg, eval_set="data_validated")
    assert frozenset({"complaint", "irritation"}) in validated
    assert frozenset({"anxiety", "distress"}) in all_pairs
    assert frozenset({"anxiety", "distress"}) not in validated
    assert len(all_pairs) == len(validated) + len(
        adjacent_pair_set(cfg, eval_set="rule_only")
    )


def test_fact_schema_19_heads():
    schema = load_fact_schema()
    assert schema.n_heads == 19
    names = set(schema.head_names)
    assert "Asset" in names
    assert "Commitment" in names
    assert "Contactability" in names
    commit = schema.head_by_name()["Commitment"]
    assert "resistant" in commit.values
