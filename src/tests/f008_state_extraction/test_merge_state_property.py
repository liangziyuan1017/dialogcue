from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from f008_state_extraction.state_extraction import merge_state

labels = st.text(min_size=1, max_size=10, alphabet=st.characters(min_codepoint=97, max_codepoint=122))
fact_list = st.lists(labels, max_size=5, unique=True)
emo_list = st.lists(labels, max_size=5, unique=True)
act_list = st.lists(labels, max_size=3, unique=True)
willingness = st.one_of(st.none(), st.sampled_from(["resistant", "weak", "conditional", "negotiating", "strong"]))

branch_key_st = st.one_of(
    st.dictionaries(st.just("facts"), st.lists(labels, min_size=1, max_size=1), max_size=1),
    st.dictionaries(st.just("emotions"), st.lists(labels, min_size=1, max_size=1), max_size=1),
    st.dictionaries(st.just("action"), labels, max_size=1),
    st.just({}),
)

state_st = st.fixed_dictionaries({
    "branch_key": branch_key_st,
    "inherited_facts": fact_list,
    "inherited_emotions": emo_list,
    "willingness": willingness,
})

extraction_st = st.fixed_dictionaries({
    "facts": fact_list,
    "emotions": emo_list,
    "actions": act_list,
    "willingness": willingness,
})

# Facts+emotions-only extraction: these are accumulated state labels (no transient action).
accumulating_extraction_st = st.fixed_dictionaries({
    "facts": fact_list,
    "emotions": emo_list,
    "actions": st.just([]),
    "willingness": willingness,
})


def _bk_values(bk):
    for v in bk.values():
        if isinstance(v, list):
            yield from v
        else:
            yield v


@given(state_st, extraction_st)
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None, max_examples=200)
def test_no_duplicates_in_inherited(state, extraction):
    result = merge_state(state, extraction)
    assert len(result["inherited_facts"]) == len(set(result["inherited_facts"]))
    assert len(result["inherited_emotions"]) == len(set(result["inherited_emotions"]))


@given(state_st, extraction_st)
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None, max_examples=200)
def test_branch_key_single_element(state, extraction):
    result = merge_state(state, extraction)
    bk = result["branch_key"]
    assert len(bk) <= 1
    if bk:
        key = next(iter(bk))
        val = bk[key]
        if key == "action":
            assert isinstance(val, str)
        else:
            assert isinstance(val, list) and len(val) == 1


@given(state_st, extraction_st)
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None, max_examples=200)
def test_no_loss_of_prior_inherited(state, extraction):
    prior_facts = set(state["inherited_facts"])
    prior_emotions = set(state["inherited_emotions"])
    result = merge_state(state, extraction)
    assert prior_facts.issubset(set(result["inherited_facts"]) | set(_bk_values(result["branch_key"]) if "facts" in result["branch_key"] else []))
    assert prior_emotions.issubset(set(result["inherited_emotions"]) | set(_bk_values(result["branch_key"]) if "emotions" in result["branch_key"] else []))


@given(state_st, accumulating_extraction_st)
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None, max_examples=200)
def test_idempotent_under_repeated_extraction(state, extraction):
    once = merge_state(state, extraction)
    twice = merge_state(once, extraction)
    assert once == twice


@given(state_st, labels)
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None, max_examples=200)
def test_action_idempotent_when_already_branch_key(state, action):
    state = dict(state)
    state["branch_key"] = {"action": action}
    extraction = {"facts": [], "emotions": [], "actions": [action], "willingness": None}
    result = merge_state(state, extraction)
    assert result["branch_key"] == {"action": action}
