"""Build-dataset unit tests (synthetic conversations)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from build_samples import (  # noqa: E402
    build_from_config,
    build_samples_for_conversation,
    make_smoke_conversations,
    pick_task_label,
)
from paths import (  # noqa: E402
    CONFIGS,
    MULTIHEAD_ROOT,
    ensure_multihead_on_path,
    load_fact_schema,
    load_yaml,
)


def _relocator():
    ensure_multihead_on_path()
    from raw_to_multihead import RawToMultiheadMapper
    from slot_relocate import build_slot_relocator

    schema = load_fact_schema()
    mapper = RawToMultiheadMapper(
        schema, MULTIHEAD_ROOT / "configs" / "raw_to_multihead.yaml"
    )
    relocator = build_slot_relocator(
        mapper,
        MULTIHEAD_ROOT / "configs" / "slot_relocate" / "emotion_mapping.yaml",
        MULTIHEAD_ROOT / "configs" / "slot_relocate" / "willingness_ontology.yaml",
    )
    return schema, mapper, relocator


def test_anchor_then_window_last_emotion():
    schema, mapper, relocator = _relocator()
    convs = make_smoke_conversations()
    c0 = convs[0]
    # window turn_ids for last customer turn (id=3): includes turn 1 and 3
    pick = pick_task_label(
        c0,
        [0, 1, 2, 3],
        anchor_turn_id=3,
        relocator=relocator,
        kind="emotion",
    )
    # anchor has complaint then negotiation → last on anchor = negotiation
    assert pick.label == "negotiation"


def test_build_samples_have_three_tasks():
    schema, mapper, relocator = _relocator()
    emo_vocab = {
        "distress",
        "despair",
        "complaint",
        "irritation",
        "hostility",
        "anxiety",
        "distrust",
        "confusion",
        "defensive",
        "negotiation",
        "engagement",
    }
    will_vocab = {"resistant", "weak", "conditional", "negotiating", "strong"}
    rows = build_samples_for_conversation(
        make_smoke_conversations()[0],
        mapper,
        schema,
        relocator,
        max_turns=4,
        max_chars=200,
        emotion_policy="anchor_then_window_last",
        willingness_policy="anchor_then_window_last",
        emotion_vocab=emo_vocab,
        willingness_vocab=will_vocab,
    )
    assert len(rows) == 2  # two customer turns
    assert all("fact_labels" in r and "fact_mask" in r for r in rows)
    assert any(r.get("emotion") for r in rows)
    assert any(r.get("willingness") for r in rows)
    # window scope stamped
    assert rows[0]["meta"]["label_scope"] == "window"
    assert rows[0]["input"]["strategy"] == "window_only"


def test_build_from_config_smoke(tmp_path):
    cfg = load_yaml(CONFIGS / "build_multitask_dataset.yaml")
    cfg = dict(cfg)
    cfg["output_dir"] = str(tmp_path / "data")
    cfg["reports_dir"] = str(tmp_path / "reports")
    cfg["quality"] = {"min_samples": 1, "warn_emotion_coverage_below": 0.0, "warn_willingness_coverage_below": 0.0}
    result = build_from_config(
        cfg,
        cfg_dir=CONFIGS,
        conversations=make_smoke_conversations(),
    )
    assert result["errors"] == []
    assert result["summary"]["n_samples"] >= 2
    # at least one split file
    out = Path(result["out_dir"])
    files = list(out.glob("multitask_*.jsonl"))
    assert files
    line = files[0].read_text(encoding="utf-8").strip().splitlines()[0]
    obj = json.loads(line)
    assert "emotion" in obj and "willingness" in obj
    assert "fact_labels" in obj
