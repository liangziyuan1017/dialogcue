import re

from f007_infrastructure.config import get as _cfg

CLOSING_ACTIONS = {"closure", "goodbye"}


MAX_MERGED_WORDS = _cfg("decision_tree.max_merged_words", 150)


def _word_count(text):
    cleaned = re.sub(r"[，。、！？；：\u201c\u201d\u2018\u2019（）\s]", "", text)
    return len(cleaned)


ACK_MAX_WORDS = _cfg("decision_tree.ack_max_words", 15)


def _is_ack_interruption(turn):
    if turn["role"] != "客户":
        return False
    if turn.get("label") == 1:
        return False
    state = turn.get("state") or {}
    if state.get("facts") or state.get("emotions"):
        return False
    return _word_count(turn["text"]) <= ACK_MAX_WORDS


def _find_merge_candidates(turns):
    candidates = []
    i = 0
    while i < len(turns):
        if turns[i]["role"] == "催收员":
            group_indices = [i]
            interruptions = []
            skipped_label1 = []
            j = i + 1
            while j < len(turns):
                if turns[j]["role"] == "催收员":
                    group_indices.append(j)
                    j += 1
                elif turns[j].get("label") == 1:
                    skipped_label1.append(j)
                    j += 1
                elif _is_ack_interruption(turns[j]):
                    if j + 1 < len(turns) and (turns[j + 1]["role"] == "催收员" or turns[j + 1].get("label") == 1):
                        interruptions.append(j)
                        j += 1
                    else:
                        break
                else:
                    break
            if len(group_indices) >= 2:
                candidates.append({
                    "collector_indices": group_indices,
                    "interruption_indices": interruptions,
                    "skipped_label1_indices": skipped_label1,
                })
            i = j
        else:
            i += 1
    return candidates


def _build_merge_prompt(turns, group):
    indices = group["collector_indices"]
    lines = []
    for i, idx in enumerate(indices):
        wc = _word_count(turns[idx]["text"])
        lines.append(f"  [{i}] ({wc}字) 催收员: {turns[idx]['text']}")
    for idx in group["interruption_indices"]:
        next_ci = next(c for c in indices if c > idx)
        i = indices.index(next_ci)
        lines.insert(i, f"  [客户说: {turns[idx]['text']}]")
    turn_list = "\n".join(lines)
    prompt = f"""将这些催收员连续话语分组。同一组的会合并为一个句子，不同组保留独立。

约束：每个合并组的总字数不能超过{MAX_MERGED_WORDS}字。

催收员话语:
{turn_list}

分组规则 (偏向不合并，只有明确是同一话题才合并):
- 同一方案解释的连续话语 → 合并（如果总字数≤{MAX_MERGED_WORDS}）
- 客户只是简短应答(嗯/好)后催收员继续同一方案 → 合并
- 不同论点/话题 → 分开
- 客户提出新观点/异议 → 分开
- 不确定 → 分开

回复JSON:
{{"groups": [[0,1],[2],[3]], "reason": "简要说明"}}
groups是索引列表，每个子列表是一个合并组。单独的话语用单元素列表如[2]。"""
    return prompt


def _enforce_word_limit(turns, collector_indices, partition):
    final = []
    for g in partition:
        if len(g) <= 1:
            final.append(g)
            continue
        current_sub = [g[0]]
        current_words = _word_count(turns[collector_indices[g[0]]]["text"])
        for k in range(1, len(g)):
            w = _word_count(turns[collector_indices[g[k]]]["text"])
            if current_words + w <= MAX_MERGED_WORDS:
                current_sub.append(g[k])
                current_words += w
            else:
                final.append(current_sub)
                current_sub = [g[k]]
                current_words = w
        final.append(current_sub)
    return final


def _ensure_same_action_merged(turns, indices, partition):
    actions = [(turns[idx].get("state") or {}).get("action") for idx in indices]
    idx_to_group = {}
    for gi, g in enumerate(partition):
        for idx in g:
            idx_to_group[idx] = gi
    changed = True
    while changed:
        changed = False
        for i in range(len(indices) - 1):
            if actions[i] and actions[i] == actions[i + 1]:
                gi = idx_to_group.get(i)
                gj = idx_to_group.get(i + 1)
                if gi is not None and gj is not None and gi != gj:
                    partition[gi] = partition[gi] + partition[gj]
                    partition[gj] = []
                    for idx in partition[gi]:
                        idx_to_group[idx] = gi
                    changed = True
    return [g for g in partition if g]


def _llm_should_merge(turns, group):
    from f007_infrastructure.llm_client import call_deepseek_json
    from f007_infrastructure.retry import retry_call
    indices = group["collector_indices"]
    if len(indices) <= 1:
        return [[0]]
    actions = []
    for idx in indices:
        action = (turns[idx].get("state") or {}).get("action")
        actions.append(action)
    if len(set(a for a in actions if a)) == 1 and any(actions):
        return _enforce_word_limit(turns, indices, [list(range(len(indices)))])
    prompt = _build_merge_prompt(turns, group)
    try:
        result = retry_call(call_deepseek_json, prompt, max_retries=3)
        groups = result.get("groups", [[i] for i in range(len(indices))])
    except Exception:
        groups = [[i] for i in range(len(indices))]
    if not groups:
        return [[i] for i in range(len(indices))]
    validated = []
    seen = set()
    for g in groups:
        if not isinstance(g, list):
            continue
        clean = [i for i in g if isinstance(i, int) and 0 <= i < len(indices) and i not in seen]
        if clean:
            validated.append(clean)
            seen.update(clean)
    for i in range(len(indices)):
        if i not in seen:
            validated.append([i])
    validated = _ensure_same_action_merged(turns, indices, validated)
    return _enforce_word_limit(turns, indices, validated)


def _merge_turns(turns, indices, call_id):
    first = turns[indices[0]]
    merged_text = " ".join(turns[i]["text"] for i in indices)
    actions = []
    for i in indices:
        action = (turns[i].get("state") or {}).get("action")
        if action:
            actions.append(action)
    primary_action = actions[0] if actions else None
    last_willingness = None
    for i in reversed(indices):
        w = (turns[i].get("state") or {}).get("willingness")
        if w:
            last_willingness = w
            break
    merged_ids = [f"{call_id}_t{turns[i]['turn_index']}" for i in indices]
    entry = {
        "script_text": merged_text,
        "script_id": f"{call_id}_t{first['turn_index']}_merged",
        "source_call_ids": [call_id],
        "customer_willingness": last_willingness,
        "merged_from": merged_ids,
    }
    if primary_action:
        entry["collector_action"] = primary_action
    return entry


def _apply_merges(turns, call_id, merge_decisions=None):
    candidates = _find_merge_candidates(turns)
    if not candidates:
        return turns
    remove_indices = set()
    merge_entries = {}
    for group in candidates:
        key = tuple(group["collector_indices"])
        cache_key = (call_id, key)
        if merge_decisions is not None and cache_key in merge_decisions:
            partition = merge_decisions[cache_key]
            partition = _enforce_word_limit(turns, group["collector_indices"], partition)
        else:
            partition = _llm_should_merge(turns, group)
            if merge_decisions is not None:
                merge_decisions[cache_key] = partition
        collector_indices = group["collector_indices"]
        interruption_indices = group["interruption_indices"]
        for idx in group.get("skipped_label1_indices", []):
            remove_indices.add(idx)
        for sub in partition:
            if len(sub) <= 1:
                continue
            abs_indices = [collector_indices[i] for i in sub]
            first_idx = abs_indices[0]
            merge_entries[first_idx] = _merge_turns(turns, abs_indices, call_id)
            for idx in abs_indices[1:]:
                remove_indices.add(idx)
            for a, b in zip(abs_indices, abs_indices[1:], strict=False):
                for int_idx in interruption_indices:
                    if a < int_idx < b:
                        state = turns[int_idx].get("state") or {}
                        if not state.get("facts") and not state.get("emotions"):
                            remove_indices.add(int_idx)
    result = []
    for i, turn in enumerate(turns):
        if i in remove_indices:
            continue
        if i in merge_entries:
            merged = merge_entries[i]
            result.append({
                "turn_index": turn["turn_index"],
                "role": "催收员",
                "text": merged["script_text"],
                "state": turn.get("state", {}),
                "_merged_entry": merged,
            })
        else:
            result.append(turn)
    return result
