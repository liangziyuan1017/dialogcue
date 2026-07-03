import asyncio
import csv
import threading
from collections import OrderedDict as _OrderedDict
from pathlib import Path

from f007_infrastructure.config import get as _cfg
from f007_infrastructure.llm_client import LLMResponseError, call_deepseek_json
from f007_infrastructure.logging import get_logger as _get_logger

_log = _get_logger(__name__)

_DATA_LABELS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "data_labels"

_relabel_lock = threading.Lock()

_extract_cache: _OrderedDict = _OrderedDict()
_taxonomy_version = 0


def invalidate_extract_cache() -> None:
    global _taxonomy_version
    _taxonomy_version += 1
    _extract_cache.clear()

_FACT_CSV_MAP = None
_EMOTION_CSV_MAP = None
_FACT_DESCRIPTIONS = None
_EMOTION_DESCRIPTIONS = None
_FACT_RELABEL_MODULE = None
_EMOTION_RELABEL_MODULE = None

_WILLINGNESS_LEVELS = ["resistant", "weak", "conditional", "negotiating", "strong"]


def _load_csv_relabel_maps():
    global _FACT_CSV_MAP, _EMOTION_CSV_MAP
    if _FACT_CSV_MAP is not None and _EMOTION_CSV_MAP is not None:
        return
    _FACT_CSV_MAP = {}
    _EMOTION_CSV_MAP = {}

    facts_path = _DATA_LABELS_DIR / "facts_relabeled.csv"
    if facts_path.exists():
        with open(facts_path, newline="") as f:
            for row in csv.DictReader(f):
                tag = row.get("tag", "").strip()
                new = row.get("new_label", "").strip()
                if tag and new:
                    _FACT_CSV_MAP[tag] = new

    emotions_path = _DATA_LABELS_DIR / "emotions_relabeled.csv"
    if emotions_path.exists():
        with open(emotions_path, newline="") as f:
            for row in csv.DictReader(f):
                tag = row.get("tag", "").strip()
                new = row.get("new_label", "").strip()
                if tag and new:
                    _EMOTION_CSV_MAP[tag] = new


def _load_descriptions():
    global _FACT_DESCRIPTIONS, _EMOTION_DESCRIPTIONS
    if _FACT_DESCRIPTIONS is None:
        _FACT_DESCRIPTIONS = {}
        facts_desc_path = _DATA_LABELS_DIR / "facts_descriptions.py"
        if facts_desc_path.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location("facts_desc", facts_desc_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _FACT_DESCRIPTIONS = getattr(mod, "TAG_LABELS", {})

    if _EMOTION_DESCRIPTIONS is None:
        _EMOTION_DESCRIPTIONS = {}
        emotions_desc_path = _DATA_LABELS_DIR / "emotions_descriptions.py"
        if emotions_desc_path.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location("emotions_desc", emotions_desc_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _EMOTION_DESCRIPTIONS = getattr(mod, "TAG_LABELS", {})


def _load_relabel_module(name: str):
    path = _DATA_LABELS_DIR / f"llm_relabel_{name}.py"
    if not path.exists():
        return None
    import importlib.util
    import sys
    if str(_DATA_LABELS_DIR) not in sys.path:
        sys.path.insert(0, str(_DATA_LABELS_DIR))
    spec = importlib.util.spec_from_file_location(f"llm_relabel_{name}", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _get_fact_relabel_module():
    global _FACT_RELABEL_MODULE
    if _FACT_RELABEL_MODULE is None:
        _FACT_RELABEL_MODULE = _load_relabel_module("facts")
    return _FACT_RELABEL_MODULE


def _get_emotion_relabel_module():
    global _EMOTION_RELABEL_MODULE
    if _EMOTION_RELABEL_MODULE is None:
        _EMOTION_RELABEL_MODULE = _load_relabel_module("emotions")
    return _EMOTION_RELABEL_MODULE


def _relabel_via_llm(items: list[str], category: str) -> tuple[list[str], dict[str, str]]:
    if not items:
        return [], {}
    mod = _get_fact_relabel_module() if category == "facts" else _get_emotion_relabel_module()
    if mod is None:
        return items, {}
    try:
        categories_block = mod.build_categories_block()
    except Exception:
        return items, {}

    tags_block = "\n".join(f"{i + 1}. `{t}`" for i, t in enumerate(items))
    system = mod.SYSTEM_PROMPT.format(categories=categories_block)
    user = mod.USER_PROMPT_TEMPLATE.format(count=len(items), tags=tags_block)
    prompt = f"{system}\n\n{user}"

    try:
        mapping = call_deepseek_json(prompt, temperature=0.0)
    except Exception:
        return items, {}

    valid_keys = set(mod.TAG_LABELS.keys())
    result = []
    seen = set()
    new_mappings: dict[str, str] = {}
    for item in items:
        new = mapping.get(item, item)
        if new not in valid_keys:
            new = item
        new_mappings[item] = new
        if new not in seen:
            result.append(new)
            seen.add(new)
    return result, new_mappings


def _append_relabel_to_csv(category: str, mappings: dict[str, str]) -> None:
    if not mappings:
        return
    path = _DATA_LABELS_DIR / f"{category}_relabeled.csv"
    with _relabel_lock:
        file_exists = path.exists()
        with open(path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["tag", "example", "count", "old_label", "new_label"])
            if not file_exists:
                writer.writeheader()
            for tag, new_label in mappings.items():
                writer.writerow({"tag": tag, "example": "", "count": 1, "old_label": tag, "new_label": new_label})


def _apply_relabel(result: dict) -> None:
    _load_csv_relabel_maps()
    _load_descriptions()

    fact_canonical = set((_FACT_DESCRIPTIONS or {}).keys())
    emotion_canonical = set((_EMOTION_DESCRIPTIONS or {}).keys())
    fact_map = _FACT_CSV_MAP if _FACT_CSV_MAP is not None else {}
    emotion_map = _EMOTION_CSV_MAP if _EMOTION_CSV_MAP is not None else {}

    for key, canonical, csv_map in [
        ("facts", fact_canonical, fact_map),
        ("emotions", emotion_canonical, emotion_map),
    ]:
        items = result.get(key, [])
        if not items:
            continue

        kept: list[str] = []
        unknown: list[str] = []
        seen = set()
        for item in items:
            canonical_hit = _hard_match(item, canonical)
            csv_hit: str | None = None
            if canonical_hit is not None:
                resolved: str | None = canonical_hit
            else:
                csv_hit = _hard_match(item, csv_map.keys())
                resolved = csv_map[csv_hit] if csv_hit is not None else None
            if resolved is not None:
                if resolved not in seen:
                    kept.append(resolved)
                    seen.add(resolved)
            elif item not in unknown:
                unknown.append(item)

        if unknown:
            llm_relabeled, new_mappings = _relabel_via_llm(unknown, key)
            for item in llm_relabeled:
                if item not in seen:
                    kept.append(item)
                    seen.add(item)
            if new_mappings:
                _append_relabel_to_csv(key, new_mappings)
                with _relabel_lock:
                    csv_map.update(new_mappings)

        result[key] = kept


_STEM_SUFFIXES = ("ing", "ed", "es", "s", "d")


def _stem(token: str) -> str:
    for suf in _STEM_SUFFIXES:
        if token.endswith(suf) and len(token) - len(suf) >= 3:
            return token[: -len(suf)]
    return token


def _tokens(tag: str) -> frozenset[str]:
    parts = tag.lower().replace("-", "_").split("_")
    return frozenset(_stem(p) for p in parts if len(p) >= 2)


def _hard_match(tag: str, candidates) -> str | None:
    cand_list = list(candidates)
    if not cand_list:
        return None
    t = tag.lower().strip()
    for c in cand_list:
        if c.lower() == t:
            return c
    for c in cand_list:
        cl = c.lower()
        if len(cl) >= 4 and (cl in t or t in cl):
            return c
    tt = _tokens(t)
    if not tt:
        return None
    best = None
    best_score = 0
    for c in cand_list:
        ct = _tokens(c)
        if not ct:
            continue
        overlap = len(tt & ct)
        threshold = max(1, (len(ct) + 1) // 2)
        if overlap >= threshold and overlap > best_score:
            best = c
            best_score = overlap
    return best


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

    try:
        llm_result = await asyncio.to_thread(extract_state_llm, utterance, taxonomy)
    except LLMResponseError as e:
        llm_result = None
        _log.warning("LLM JSON parse failed, falling back to keyword; raw=%s", e.raw_text[:200])
    except Exception:
        llm_result = None

    kw_result = await extract_state_keyword(utterance, taxonomy, db=db)

    if llm_result is not None:
        for key in ("facts", "emotions", "actions"):
            for item in kw_result.get(key, []):
                if item not in llm_result.get(key, []):
                    llm_result[key].append(item)
        result = llm_result
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

        for f in new_facts:
            if f not in inh_facts:
                inh_facts.append(f)
        for e in new_emotions:
            if e not in inh_emotions:
                inh_emotions.append(e)

        if new_facts:
            winner = new_facts[-1]
            bk = {"facts": [winner]}
            if winner in inh_facts:
                inh_facts.remove(winner)
        elif new_emotions:
            winner = new_emotions[-1]
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
