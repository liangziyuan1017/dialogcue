from f004_decision_tree.tree_transforms import (
    _collapse_redundant_facts,
    _deduplicate_nodes,
    _consolidate_endpoints,
    _propagate_sentences,
)


def _has_dup_pool(node, visited=None):
    if visited is None:
        visited = set()
    nid = id(node)
    if nid in visited:
        return False
    visited.add(nid)
    pool = node.get("sentence_pool", [])
    texts = [s["script_text"] for s in pool]
    if len(texts) != len(set(texts)):
        return True
    for child in node.get("children", []):
        if _has_dup_pool(child, visited):
            return True
    return False


def test_collapse_redundant_facts_dedup():
    child_sentence = {"script_text": "hello", "script_id": "s1", "source_call_ids": [], "customer_willingness": None}
    dup_sentence = {"script_text": "hello", "script_id": "s2", "source_call_ids": [], "customer_willingness": None}
    root = {
        "state_id": "root",
        "branch_key": {},
        "sentence_pool": [child_sentence],
        "children": [
            {
                "state_id": "f:already_known",
                "branch_key": {"facts": ["already_known"]},
                "sentence_pool": [child_sentence, dup_sentence],
                "children": [],
            }
        ],
    }
    _collapse_redundant_facts(root, accumulated_facts={"already_known"})
    assert not _has_dup_pool(root), f"Dup found after _collapse_redundant_facts: {[s['script_text'] for s in root['sentence_pool']]}"


def test_deduplicate_nodes_dedup():
    shared = {"script_text": "shared line", "script_id": "s1", "source_call_ids": [], "customer_willingness": None}
    dup = {"script_text": "shared line", "script_id": "s2", "source_call_ids": [], "customer_willingness": None}
    root = {
        "state_id": "root",
        "branch_key": {},
        "sentence_pool": [],
        "children": [
            {
                "state_id": "a:info",
                "branch_key": {"action": "information"},
                "inherited_facts": [],
                "inherited_emotions": [],
                "sentence_pool": [shared],
                "children": [],
            },
            {
                "state_id": "a:info",
                "branch_key": {"action": "information"},
                "inherited_facts": [],
                "inherited_emotions": [],
                "sentence_pool": [dup],
                "children": [],
            },
        ],
    }
    _deduplicate_nodes(root)
    assert not _has_dup_pool(root), "Dup found after _deduplicate_nodes"


def test_consolidate_endpoints_dedup():
    ending_a = {"script_text": "goodbye", "script_id": "e1", "source_call_ids": [], "customer_willingness": None, "gesture_type": "ending"}
    ending_b = {"script_text": "goodbye", "script_id": "e2", "source_call_ids": [], "customer_willingness": None, "gesture_type": "ending"}
    root = {
        "state_id": "initial_contact",
        "branch_key": {},
        "sentence_pool": [ending_a],
        "children": [
            {
                "state_id": "child",
                "branch_key": {"facts": ["x"]},
                "sentence_pool": [ending_b],
                "children": [],
            }
        ],
    }
    _consolidate_endpoints(root)
    normal_end = next(c for c in root["children"] if c["state_id"] == "normal_end")
    texts = [s["script_text"] for s in normal_end["sentence_pool"]]
    assert len(texts) == len(set(texts)), f"Dup in normal_end pool: {texts}"


def test_propagate_then_collapse_no_dup():
    sentence = {"script_text": "offer plan", "script_id": "s1", "source_call_ids": [], "customer_willingness": None}
    root = {
        "state_id": "root",
        "branch_key": {},
        "sentence_pool": [sentence],
        "children": [
            {
                "state_id": "f:already_known",
                "branch_key": {"facts": ["already_known"]},
                "sentence_pool": [],
                "children": [],
            }
        ],
    }
    _propagate_sentences(root)
    _collapse_redundant_facts(root, accumulated_facts={"already_known"})
    assert not _has_dup_pool(root), f"Dup after propagate+collapse: {[s['script_text'] for s in root['sentence_pool']]}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
