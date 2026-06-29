import json

from infra.llm_client import call_deepseek_json


def _format_taxonomy_for_prompt(taxonomy: dict) -> str:
    sections = []
    for category, label in [("facts", "FACTS"), ("emotions", "EMOTIONS"), ("collector_actions", "COLLECTOR ACTIONS")]:
        groups = taxonomy.get(category, [])
        if groups:
            lines = [f"  - {g['group_name']} (keywords: {', '.join(g.get('keywords', [])[:5])}...)" for g in groups]
            sections.append(f"{label}:\n" + "\n".join(lines))
    willingness = taxonomy.get("willingness_levels", [])
    if willingness:
        levels = [f"  - {w.get('level', '')}: {w.get('definition', '')}" for w in willingness]
        sections.append("WILLINGNESS LEVELS:\n" + "\n".join(levels))
    return "\n\n".join(sections)


def extract_state_llm(utterance: str, taxonomy: dict) -> dict:
    taxonomy_text = _format_taxonomy_for_prompt(taxonomy)
    prompt = f"""Extract the customer's state from the following utterance.

{taxonomy_text}

Utterance: {utterance}

Return JSON:
- facts: list of matching FACTS group_names
- emotions: list of matching EMOTIONS group_names
- actions: list of matching COLLECTOR ACTIONS group_names
- willingness: one of "resistant", "weak", "conditional", "negotiating", "cooperative", "strong", or null
- confidence: 0-1

Only include group_names that actually appear in the taxonomy above."""

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
        return {"facts": [], "emotions": [], "actions": [], "confidence": 0.0, "method": "keyword"}

    matches = db.taxonomy_keyword_search(utterance, limit=20)
    facts = []
    emotions = []
    actions = []
    for m in matches:
        group = m.get("group_name", "")
        cat = m.get("category", "")
        if cat == "facts" and group not in facts:
            facts.append(group)
        elif cat == "emotions" and group not in emotions:
            emotions.append(group)
        elif cat in ("collector_actions", "actions") and group not in actions:
            actions.append(group)

    confidence = min(0.3 + 0.1 * len(matches), 0.8) if matches else 0.1
    return {"facts": facts, "emotions": emotions, "actions": actions, "willingness": None, "confidence": confidence, "method": "keyword"}


def extract_state(utterance: str, taxonomy: dict, db=None) -> dict:
    try:
        return extract_state_llm(utterance, taxonomy)
    except Exception:
        return extract_state_keyword(utterance, taxonomy, db=db)


def merge_state(existing_state: dict, new_extraction: dict) -> dict:
    result = {}
    for key in ("facts", "emotions", "actions"):
        existing = existing_state.get(key, [])
        new = new_extraction.get(key, [])
        seen = set(existing)
        merged = list(existing)
        for item in new:
            if item not in seen:
                merged.append(item)
                seen.add(item)
        result[key] = merged
    new_willingness = new_extraction.get("willingness")
    if new_willingness is not None:
        result["willingness"] = new_willingness
    else:
        result["willingness"] = existing_state.get("willingness")
    return result
