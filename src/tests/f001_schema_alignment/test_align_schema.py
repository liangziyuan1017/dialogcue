from f000_keyword_discovery.load_data import load_records
from f001_schema_alignment.align_schema import align_all


def _load_labeled():
    import importlib.util
    import os
    data_path = os.path.join(os.path.dirname(__file__), "../..", "f000_keyword_discovery", "data", "output_labeled.py")
    spec = importlib.util.spec_from_file_location("output_labeled", data_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.results


def test_all_records_present():
    aligned = align_all()
    assert len(aligned) > 0


def test_every_record_has_required_fields():
    aligned = align_all()
    for rec in aligned:
        assert "turns_annotated" in rec
        assert "reward" in rec
        assert "state_transitions" in rec
        assert "context" in rec


def test_reward_is_null():
    aligned = align_all()
    for rec in aligned:
        assert rec["reward"] is None


def test_state_transitions_empty():
    aligned = align_all()
    for rec in aligned:
        assert rec["state_transitions"] == []


def test_original_dialog_preserved_verbatim():
    records = load_records()
    aligned = align_all()
    for raw, aln in zip(records, aligned, strict=False):
        raw_texts = [t["text"] for t in raw["response"]["dialog"]]
        aln_texts = [t["text"] for t in aln["turns_annotated"]]
        assert raw_texts == aln_texts, f"Mismatch in call_id {raw['call_id']}"


def test_turns_annotated_structure():
    aligned = align_all()
    for rec in aligned:
        for turn in rec["turns_annotated"]:
            assert "turn_index" in turn
            assert "role" in turn
            assert "text" in turn
            assert turn["role"] in ("客户", "催收员")


def test_state_labels_from_output_labeled_carried_into_turns_annotated():
    labeled = _load_labeled()
    aligned = align_all()
    labeled_by_id = {r["call_id"]: r for r in labeled}
    for aln in aligned:
        labeled_rec = labeled_by_id.get(aln["call_id"])
        assert labeled_rec is not None, f"call_id {aln['call_id']} not in output_labeled"
        for turn in aln["turns_annotated"]:
            labeled_turn = labeled_rec["response"]["dialog"][turn["turn_index"]]
            if "state" in labeled_turn:
                assert "state" in turn, f"call_id {aln['call_id']} turn {turn['turn_index']}: state label missing"
                assert turn["state"] == labeled_turn["state"]


def test_state_labels_count_matches_output_labeled():
    labeled = _load_labeled()
    aligned = align_all()
    labeled_by_id = {r["call_id"]: r for r in labeled}
    total_labeled_states = 0
    total_aligned_states = 0
    for aln in aligned:
        labeled_rec = labeled_by_id[aln["call_id"]]
        for t in labeled_rec["response"]["dialog"]:
            if "state" in t:
                total_labeled_states += 1
        for t in aln["turns_annotated"]:
            if "state" in t:
                total_aligned_states += 1
    assert total_aligned_states == total_labeled_states
