import asyncio
from collections import OrderedDict as _OrderedDict

from f007_infrastructure.config import get as _cfg
from f007_infrastructure.label_relabel import apply_relabel as _apply_relabel
from f007_infrastructure.llm_client import LLMResponseError, call_deepseek_json
from f007_infrastructure.logging import get_logger as _get_logger
from f008_state_extraction.bert_extractor import (
    extract_state_bert,
    get_extraction_provider,
)

_log = _get_logger(__name__)

_extract_cache: _OrderedDict = _OrderedDict()
_taxonomy_version = 0


def invalidate_extract_cache() -> None:
    global _taxonomy_version
    _taxonomy_version += 1
    _extract_cache.clear()


_WILLINGNESS_LEVELS = ["resistant", "weak", "conditional", "negotiating", "strong"]


def extract_state_llm(utterance: str, taxonomy: dict) -> dict:
    from f000_keyword_discovery.keyword_prompts import _build_customer_batch_prompt

    prompt = _build_customer_batch_prompt([(utterance, [])])
    raw = call_deepseek_json(prompt, temperature=0.1)
    result = raw[0] if isinstance(raw, list) and raw else (raw if isinstance(raw, dict) else {})

    def _extract_groups(items):
        if not items:
            return []
        groups = []
        for item in items:
            if isinstance(item, dict):
                g = item.get("group", item.get("keyword", ""))
            else:
                g = item
            if g and g not in groups:
                groups.append(g)
        return groups

    return {
        "facts": _extract_groups(result.get("facts")),
        "emotions": _extract_groups(result.get("emotions")),
        "actions": result.get("actions", []),
        "willingness": result.get("willingness", None),
        "confidence": result.get("confidence", 0.5),
        "method": "llm",
    }


async def extract_state_keyword(utterance: str, taxonomy: dict, db=None) -> dict:
    if db is None:
        return {"facts": [], "emotions": [], "actions": [], "willingness": None, "confidence": 0.0, "method": "keyword"}

    matches = await db.taxonomy_keyword_search(utterance, limit=20)
    facts = []
    emotions = []
    actions = []
    for m in matches:
        group = m.get("group_name", "")
        cat = m.get("category", "")
        if not group:
            continue
        if cat == "facts" and group not in facts:
            facts.append(group)
        elif cat == "emotions" and group not in emotions:
            emotions.append(group)
        elif cat in ("collector_actions", "actions") and group not in actions:
            actions.append(group)

    kw_base = _cfg("keyword_confidence.base", 0.3)
    kw_per = _cfg("keyword_confidence.per_match", 0.1)
    kw_ceil = _cfg("keyword_confidence.ceiling", 0.8)
    kw_no_match = _cfg("keyword_confidence.no_match", 0.1)
    confidence = min(kw_base + kw_per * len(matches), kw_ceil) if matches else kw_no_match
    return {"facts": facts, "emotions": emotions, "actions": actions, "willingness": None, "confidence": confidence, "method": "keyword"}


async def extract_state(utterance: str, taxonomy: dict, db=None) -> dict:
    cache_key = (utterance, _taxonomy_version)
    cached = _extract_cache.get(cache_key)
    if cached is not None:
        _extract_cache.move_to_end(cache_key)
        return cached

    provider = get_extraction_provider()
    primary = None
    try:
        if provider == "bert":
            primary = await asyncio.to_thread(extract_state_bert, utterance)
        else:
            primary = await asyncio.to_thread(extract_state_llm, utterance, taxonomy)
    except LLMResponseError as e:
        _log.warning("LLM JSON parse failed, falling back to keyword; raw=%s", e.raw_text[:200])
    except Exception:
        _log.warning(
            "primary state extraction failed (provider=%s); falling back to keyword",
            provider,
            exc_info=True,
        )

    kw_result = await extract_state_keyword(utterance, taxonomy, db=db)

    if primary is not None:
        for key in ("facts", "emotions", "actions"):
            for item in kw_result.get(key, []):
                if item not in primary.get(key, []):
                    primary[key].append(item)
        result = primary
    else:
        result = kw_result

    _apply_relabel(result)

    cache_size = _cfg("extraction.cache_size", 512)
    if cache_size > 0:
        _extract_cache[cache_key] = result
        if len(_extract_cache) > cache_size:
            _extract_cache.popitem(last=False)
    return result


def relabel_state(state: dict) -> dict:
    result = dict(state)
    _apply_relabel(result)
    return result


def merge_state(existing_state: dict, new_extraction: dict) -> dict:
    """Merge a new turn's extraction into the path-structured conversation state.

    Semantics (ADR-021 / ADR-015):
      - `branch_key` holds exactly ONE label — the most recent branching
        decision. Priority when a turn yields multiple new labels:
        facts > emotions > actions. The winner lives in `branch_key`;
        every other new label is absorbed into `inherited_facts` /
        `inherited_emotions` (ordered-set, dedup).
      - `inherited_facts` / `inherited_emotions` accumulate from ancestors
        and never lose a prior label. The current `branch_key` winner is
        NOT duplicated into inherited.
      - `willingness` is a scalar: overwritten by any non-null new value.
      - Actions are transient (the collector's current move); they set
        `branch_key` but are not accumulated.

    Idempotency: for facts+emotions-only extractions, applying the same
    extraction twice yields the same state (all labels are absorbed on
    the first pass). Re-applying an action legitimately updates
    `branch_key` (a move can be re-emitted).
    """
    bk = dict(existing_state.get("branch_key", {}))
    inh_facts = list(existing_state.get("inherited_facts", []))
    inh_emotions = list(existing_state.get("inherited_emotions", []))

    seen_facts = set(inh_facts)
    if "facts" in bk:
        seen_facts.update(bk["facts"])
    seen_emotions = set(inh_emotions)
    if "emotions" in bk:
        seen_emotions.update(bk["emotions"])

    new_facts = [f for f in new_extraction.get("facts", []) if f not in seen_facts]
    new_emotions = [e for e in new_extraction.get("emotions", []) if e not in seen_emotions]
    new_actions = new_extraction.get("actions", [])

    if new_facts or new_emotions or new_actions:
        if "facts" in bk:
            for f in bk["facts"]:
                if f not in inh_facts:
                    inh_facts.append(f)
        if "emotions" in bk:
            for e in bk["emotions"]:
                if e not in inh_emotions:
                    inh_emotions.append(e)

        if new_facts:
            winner = new_facts[-1]
            for f in new_facts[:-1]:
                if f not in inh_facts:
                    inh_facts.append(f)
            for e in new_emotions:
                if e not in inh_emotions:
                    inh_emotions.append(e)
            bk = {"facts": [winner]}
            if winner in inh_facts:
                inh_facts.remove(winner)
        elif new_emotions:
            winner = new_emotions[-1]
            for e in new_emotions[:-1]:
                if e not in inh_emotions:
                    inh_emotions.append(e)
            bk = {"emotions": [winner]}
            if winner in inh_emotions:
                inh_emotions.remove(winner)
        elif new_actions:
            bk = {"action": new_actions[-1]}

    result = {
        "branch_key": bk,
        "inherited_facts": inh_facts,
        "inherited_emotions": inh_emotions,
        "willingness": existing_state.get("willingness"),
    }
    new_w = new_extraction.get("willingness")
    if new_w is not None:
        result["willingness"] = new_w
    return result


def path_state_to_flat(state: dict) -> tuple[list[str], list[str], list[str]]:
    bk = state.get("branch_key", {})
    all_facts = list(state.get("inherited_facts", []))
    all_emotions = list(state.get("inherited_emotions", []))
    all_actions = []
    if "facts" in bk:
        all_facts.extend(bk["facts"])
    if "emotions" in bk:
        all_emotions.extend(bk["emotions"])
    if "action" in bk:
        all_actions.append(bk["action"])
    return all_facts, all_emotions, all_actions


def flat_to_path_state(facts: list[str], emotions: list[str], actions: list[str], willingness=None) -> dict:
    facts = list(facts)
    emotions = list(emotions)
    actions = list(actions)
    bk: dict = {}
    inh_facts = []
    inh_emotions = []
    if actions:
        bk = {"action": actions[-1]}
        inh_facts = facts
        inh_emotions = emotions
    elif facts:
        bk = {"facts": [facts[-1]]}
        inh_facts = facts[:-1]
        inh_emotions = emotions
    elif emotions:
        bk = {"emotions": [emotions[-1]]}
        inh_facts = facts
        inh_emotions = emotions[:-1]
    return {
        "branch_key": bk,
        "inherited_facts": inh_facts,
        "inherited_emotions": inh_emotions,
        "willingness": willingness,
    }
