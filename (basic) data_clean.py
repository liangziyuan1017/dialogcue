"""Data cleaning pipeline for debt collection call records.

Applies the following steps in order:
1. Fix truncated role labels - restores "催收:" to "催收员:" where
   the ASR transcription cut off the speaker label.
2. Normalize punctuation - maps all Chinese punctuation marks to their
   English equivalents (e.g. ，→, 。→. ？→? ；→; ：→: etc.) so that
   downstream processing uses a consistent character set.
3. Re-parse dialog - re-segments the cleaned dialog_raw string into
   structured DialogTurn objects with the now-normalized separators.
4. Rebuild dialog_raw - reconstructs the dialog raw string from the
   parsed turns, ensuring the serialized form reflects the cleaned
   data exactly.
5. Clean planevaluation - strips markdown residue (backtick blocks,
   horizontal rules, excess whitespace) from the evaluation field.
6. Normalize planevaluation punctuation - applies the same CN→EN
   punctuation mapping to the cleaned evaluation text.
7. Re-parse planevaluation - extracts structured PlanEvaluation fields
   (reduction_plan, mina_plan, technique) from the cleaned text.
"""

import copy
import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Optional

from data_parser import (
    CallRecord,
    DialogTurn,
    PlanEvaluation,
    parse_dialog,
    parse_planevaluation,
    load_records,
    ROLE_COLLECTOR,
)

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "data_0520.json"
OUTPUT_FILE = BASE_DIR / "data_0520_cleaned.json"

CN_TO_EN_PUNCT = {
    "\uff0c": ",",      # ，→,
    "\u3002": ".",      # 。→.
    "\uff1f": "?",      # ？→?
    "\uff01": "!",      # ！→!
    "\uff1a": ":",      # ：→:
    "\uff1b": ";",      # ；→;
    "\u3001": ",",      # 、→,
    "\u201c": '"',      # "→"
    "\u201d": '"',      # "→"
    "\u2018": "'",      # '→'
    "\u2019": "'",      # '→'
    "\uff08": "(",      # （→(
    "\uff09": ")",      # ）→)
    "\u3010": "[",      # 【→[
    "\u3011": "]",      # 】→]
    "\u300a": "<",      # 《→<
    "\u300b": ">",      # 》→>
}

DEFAULT_FILLERS = frozenset({
    "嗯", "好", "噢", "啊", "对", "是", "唉", "呃",
    "谢", "号", "六", "接", "可", "然", "后", "拜",
    "的", "完", "喂", "行", "个", "不", "没", "来",
    "去", "下", "这", "那", "么", "什", "怎", "多",
    "少", "到", "在", "有", "会", "能", "要", "做",
    "说", "看", "知", "想", "给", "让", "把", "被",
})


def normalize_punctuation(text: str) -> str:
    """Replaces Chinese punctuation marks with English equivalents.

    Args:
        text: Input string possibly containing Chinese punctuation.

    Returns:
        String with all Chinese punctuation mapped to English.
    """
    for cn, en in CN_TO_EN_PUNCT.items():
        text = text.replace(cn, en)
    return text


def fix_truncated_roles(dialog_raw: str) -> str:
    """Fixes truncated role labels in the dialog raw string.

    The ASR transcription occasionally produces "催收:" instead of
    "催收员:" when the speaker label is cut off. This function
    restores the full label.

    Args:
        dialog_raw: Raw dialog string with role-prefixed turns.

    Returns:
        Dialog string with corrected role labels.
    """
    text = re.sub(r"催收[:;]", "催收员:", dialog_raw)
    text = re.sub(r"催收：", "催收员:", text)
    return text


def clean_planevaluation(pe_raw: str) -> str:
    """Strips markdown artifacts from a planevaluation raw string.

    Removes backtick blocks, horizontal rules (---), and trailing
    whitespace that are transcription/formatting residue.

    Args:
        pe_raw: Raw planevaluation string, typically a markdown table.

    Returns:
        Cleaned planevaluation string without markdown residue.
    """
    if not pe_raw:
        return ""
    text = pe_raw
    text = re.sub(r"`+", "", text)
    text = re.sub(r"-{2,}", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    return text



def _rebuild_dialog_raw(turns: list[DialogTurn]) -> str:
    """Reconstructs a dialog raw string from a list of DialogTurn objects.

    Args:
        turns: List of DialogTurn objects with role and text.

    Returns:
        Semicolon-separated string in "role:text;role:text" format.
    """
    segments = [f"{t.role}:{t.text}" for t in turns if t.role]
    return "; ".join(segments)


def clean_record(record: CallRecord) -> CallRecord:
    """Applies the full cleaning pipeline to a single CallRecord.

    Execution order:
        1. Fix truncated role labels in dialog_raw.
        2. Normalize punctuation in dialog_raw (CN→EN).
        3. Re-parse dialog from the cleaned raw string.
        4. Rebuild dialog_raw from parsed turns.
        5. Clean and normalize planevaluation.
        6. Re-parse planevaluation from the cleaned raw string.

    Args:
        record: Input CallRecord to clean.

    Returns:
        A new CallRecord with all cleaning applied.
    """
    dialog_raw = fix_truncated_roles(record.dialog_raw)
    dialog_raw = normalize_punctuation(dialog_raw)

    turns = parse_dialog(dialog_raw)
    dialog_raw = _rebuild_dialog_raw(turns)

    pe_raw = clean_planevaluation(record.planevaluation_raw)
    pe_raw = normalize_punctuation(pe_raw)
    evaluation = parse_planevaluation(pe_raw)

    cleaned = replace(
        record,
        dialog_raw=dialog_raw,
        planevaluation_raw=pe_raw,
        turns=turns,
        evaluation=evaluation,
    )
    return cleaned


def _record_to_dict(record: CallRecord) -> dict:
    """Serializes a CallRecord back to the JSON schema.

    Args:
        record: A cleaned CallRecord.

    Returns:
        Dictionary matching the data_0520.json schema.
    """
    return {
        "call_id": record.call_id,
        "dialog": record.dialog_raw,
        "calldate": record.calldate,
        "custno": record.custno,
        "colluserid": record.colluserid,
        "mobtyp": record.mobtyp,
        "talktime": record.talktime,
        "planevaluation": record.planevaluation_raw,
    }


def clean_all_records(
    input_path: Optional[str] = None,
    output_path: Optional[str] = None,
) -> list[CallRecord]:
    """Loads, cleans, and saves all call records.

    Args:
        input_path: Path to input JSON file. Defaults to data_0520.json.
        output_path: Path to output JSON file. Defaults to data_0520_cleaned.json.

    Returns:
        List of cleaned CallRecord objects.
    """
    in_path = Path(input_path) if input_path else INPUT_FILE
    out_path = Path(output_path) if output_path else OUTPUT_FILE

    records = load_records(str(in_path))
    cleaned = [clean_record(r) for r in records]

    data = [_record_to_dict(r) for r in cleaned]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return cleaned


def _print_stats(before: list[CallRecord], after: list[CallRecord]) -> None:
    """Prints before/after comparison statistics.

    Args:
        before: Records before cleaning.
        after: Records after cleaning.
    """
    b_turns = sum(len(r.turns) for r in before)
    a_turns = sum(len(r.turns) for r in after)

    b_cn_punct = sum(
        1 for r in before for t in r.turns
        if re.search(r"[，。？！：；、]", t.text)
    )
    a_cn_punct = sum(
        1 for r in after for t in r.turns
        if re.search(r"[，。？！：；、]", t.text)
    )

    b_truncated = sum(
        1 for r in before if re.search(r"催收[：:]", r.dialog_raw)
        and not re.search(r"催收员[：:]", r.dialog_raw)
    )

    b_stutters = sum(
        1 for r in before for t in r.turns
        if re.search(r"(.)\1{2,}", t.text)
    )
    a_stutters = sum(
        1 for r in after for t in r.turns
        if re.search(r"(.)\1{2,}", t.text)
    )

    b_pe_artifacts = sum(
        1 for r in before if "`" in r.planevaluation_raw or "---" in r.planevaluation_raw
    )
    a_pe_artifacts = sum(
        1 for r in after if "`" in r.planevaluation_raw or "---" in r.planevaluation_raw
    )

    print("=" * 50)
    print("CLEANING REPORT")
    print("=" * 50)
    print(f"Records:                {len(before)}")
    print(f"Total turns:            {b_turns} -> {a_turns}")
    print(f"CN punct in turns:      {b_cn_punct} -> {a_cn_punct}")
    print(f"Truncated role labels:  {b_truncated} -> 0")
    print(f"Stutters (3+ repeat):   {b_stutters} -> {a_stutters} (preserved)")
    print(f"PE markdown artifacts:  {b_pe_artifacts} -> {a_pe_artifacts}")
    print("=" * 50)


if __name__ == "__main__":
    before = load_records(str(INPUT_FILE))
    after = clean_all_records(
        input_path=str(INPUT_FILE),
        output_path=str(OUTPUT_FILE),
    )
    _print_stats(before, after)
    print(f"\nCleaned data saved to: {OUTPUT_FILE}")
