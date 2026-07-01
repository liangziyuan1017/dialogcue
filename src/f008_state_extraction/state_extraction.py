import csv
from pathlib import Path

from f007_infrastructure.config import get as _cfg
from f007_infrastructure.llm_client import call_deepseek_json

_DATA_LABELS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "data_labels"

_FACT_CSV_MAP = None
_EMOTION_CSV_MAP = None
_FACT_DESCRIPTIONS = None
_EMOTION_DESCRIPTIONS = None

_WILLINGNESS_LEVELS = ["resistant", "weak", "conditional", "negotiating", "cooperative", "strong"]


def _load_csv_relabel_maps():
    global _FACT_CSV_MAP, _EMOTION_CSV_MAP
    if _FACT_CSV_MAP is not None:
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
    if _FACT_DESCRIPTIONS is not None:
        return

    _FACT_DESCRIPTIONS = {}
    facts_desc_path = _DATA_LABELS_DIR / "facts_descriptions.py"
    if facts_desc_path.exists():
        import importlib.util
        spec = importlib.util.spec_from_file_location("facts_desc", facts_desc_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _FACT_DESCRIPTIONS = getattr(mod, "TAG_LABELS", {})

    _EMOTION_DESCRIPTIONS = {}
    emotions_desc_path = _DATA_LABELS_DIR / "emotions_descriptions.py"
    if emotions_desc_path.exists():
        import importlib.util
        spec = importlib.util.spec_from_file_location("emotions_desc", emotions_desc_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _EMOTION_DESCRIPTIONS = getattr(mod, "TAG_LABELS", {})


def _relabel_via_csv(items: list[str], csv_map: dict[str, str]) -> tuple[list[str], list[str], dict[str, str]]:
    relabeled = []
    unknown = []
    new_mappings = {}
    seen = set()
    for item in items:
        new = csv_map.get(item)
        if new:
            if new not in seen:
                relabeled.append(new)
                seen.add(new)
        else:
            if item not in seen:
                unknown.append(item)
                seen.add(item)
    return relabeled, unknown, new_mappings


def _relabel_via_llm(items: list[str], category: str, descriptions: dict) -> tuple[list[str], dict[str, str]]:
    if not items or not descriptions:
        return items, {}

    categories_block = "\n".join(
        f"- **{k}**: {v['description']}" for k, v in descriptions.items()
    )
    tags_block = "\n".join(f"- `{t}`" for t in items)

    prompt = f"""Classify the following {category} tags into the categories below.

## Categories

{categories_block}

## Rules

1. Every tag MUST be assigned to exactly one category key.
2. Choose the category that best captures the semantic meaning.
3. Return a JSON object mapping each tag string to its category key.
4. Do NOT invent new categories.

Tags:
{tags_block}"""

    try:
        mapping = call_deepseek_json(prompt, temperature=0.0)
    except Exception:
        return items, {}

    result = []
    seen = set()
    new_mappings = {}
    for item in items:
        new = mapping.get(item, item)
        new_mappings[item] = new
        if new not in seen:
            result.append(new)
            seen.add(new)
    return result, new_mappings


def _append_relabel_to_csv(category: str, mappings: dict[str, str]) -> None:
    if not mappings:
        return
    path = _DATA_LABELS_DIR / f"{category}_relabeled.csv"
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

    for key, csv_map, descriptions in [
        ("facts", _FACT_CSV_MAP, _FACT_DESCRIPTIONS),
        ("emotions", _EMOTION_CSV_MAP, _EMOTION_DESCRIPTIONS),
    ]:
        items = result.get(key, [])
        if not items:
            continue

        relabeled, unknown, _ = _relabel_via_csv(items, csv_map)

        if unknown:
            llm_relabeled, new_mappings = _relabel_via_llm(unknown, key, descriptions)
            seen = set(relabeled)
            for item in llm_relabeled:
                if item not in seen:
                    relabeled.append(item)
                    seen.add(item)
            if new_mappings:
                _append_relabel_to_csv(key, new_mappings)
                if key == "facts":
                    _FACT_CSV_MAP.update(new_mappings)
                else:
                    _EMOTION_CSV_MAP.update(new_mappings)

        result[key] = relabeled


def _format_willingness_for_prompt(taxonomy: dict) -> str:
    willingness = taxonomy.get("willingness_levels", [])
    if willingness:
        levels = [f"  - {w.get('level', '')}: {w.get('definition', '')}" for w in willingness]
        return "WILLINGNESS LEVELS (pick exactly one or null):\n" + "\n".join(levels)
    return "WILLINGNESS (pick one: resistant, weak, conditional, negotiating, cooperative, strong, or null)"


def extract_state_llm(utterance: str, taxonomy: dict) -> dict:
    willingness_text = _format_willingness_for_prompt(taxonomy)
    prompt = f"""Extract the customer's state from the following utterance.

Extract facts and emotions FREELY — use whatever labels best describe the customer's situation and emotional state. Do NOT limit yourself to a predefined list. Use snake_case English labels (e.g. "financial_hardship", "request_installment", "income_delay").

{willingness_text}

Utterance: {utterance}

Return JSON:
- facts: list of fact labels (free-form snake_case English)
- emotions: list of emotion labels (free-form snake_case English)
- actions: list of collector action labels (usually empty for customer turns)
- willingness: one of "resistant", "weak", "conditional", "negotiating", "cooperative", "strong", or null
- confidence: 0-1"""

    result = call_deepseek_json(prompt, temperature=0.1)
    return {
        "facts": result.get("facts", []),
        "emotions": result.get("emotions", []),
        "actions": result.get("actions", []),
        "willingness": result.get("willingness", None),
        "confidence": result.get("confidence", 0.5),
        "method": "llm",
    }


def extract_state_keyword(utterance: str, taxonomy: dict, db=None) -> dict:
    if db is None:
        return {"facts": [], "emotions": [], "actions": [], "willingness": None, "confidence": 0.0, "method": "keyword"}

    matches = db.taxonomy_keyword_search(utterance, limit=20)
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


def extract_state(utterance: str, taxonomy: dict, db=None) -> dict:
    try:
        llm_result = extract_state_llm(utterance, taxonomy)
    except Exception:
        llm_result = None

    kw_result = extract_state_keyword(utterance, taxonomy, db=db)

    if llm_result is not None:
        for key in ("facts", "emotions", "actions"):
            for item in kw_result.get(key, []):
                if item not in llm_result.get(key, []):
                    llm_result[key].append(item)
        result = llm_result
    else:
        result = kw_result

    _apply_relabel(result)
    return result


def relabel_state(state: dict) -> dict:
    result = dict(state)
    _apply_relabel(result)
    return result


def merge_state(existing_state: dict, new_extraction: dict) -> dict:
    bk = dict(existing_state.get("branch_key", {}))
    inh_facts = list(existing_state.get("inherited_facts", []))
    inh_emotions = list(existing_state.get("inherited_emotions", []))

    all_facts = set(inh_facts)
    if "facts" in bk:
        all_facts.update(bk["facts"])
    all_emotions = set(inh_emotions)
    if "emotions" in bk:
        all_emotions.update(bk["emotions"])

    new_facts = [f for f in new_extraction.get("facts", []) if f not in all_facts]
    new_emotions = [e for e in new_extraction.get("emotions", []) if e not in all_emotions]
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
        for f in new_facts[:-1]:
            inh_facts.append(f)
        bk = {"facts": [new_facts[-1]]}
    elif new_emotions:
        for e in new_emotions[:-1]:
            inh_emotions.append(e)
        bk = {"emotions": [new_emotions[-1]]}
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
    bk = {}
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
