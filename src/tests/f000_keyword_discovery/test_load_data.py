from f000_keyword_discovery.load_data import load_records, get_turns_by_role


def test_load_records_count():
    records = load_records()
    assert len(records) == 31


def test_load_records_has_dialog():
    records = load_records()
    for r in records:
        assert "response" in r
        assert "dialog" in r["response"]
        assert len(r["response"]["dialog"]) > 0


def test_get_turns_by_role_customer():
    records = load_records()
    customer_turns = get_turns_by_role(records, "客户")
    assert len(customer_turns) > 0
    for turn, _ in customer_turns:
        assert turn["role"] == "客户"


def test_get_turns_by_role_collector():
    records = load_records()
    collector_turns = get_turns_by_role(records, "催收员")
    assert len(collector_turns) > 0
    for turn, _ in collector_turns:
        assert turn["role"] == "催收员"


def test_turns_preserve_call_id():
    records = load_records()
    customer_turns = get_turns_by_role(records, "客户")
    for turn, meta in customer_turns:
        assert "call_id" in meta
        assert "turn_index" in meta
