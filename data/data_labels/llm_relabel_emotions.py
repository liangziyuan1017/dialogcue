"""
LLM pipeline to classify debt-collection emotion tags into semantic categories.

Usage:
    python llm_relabel_emotions.py                    # classify first 20 rows
    python llm_relabel_emotions.py --limit 100        # classify first 100 rows
    python llm_relabel_emotions.py --all              # classify all rows
    python llm_relabel_emotions.py --batch-size 30    # classify in batches of 30 tags per LLM call
"""

import csv
import json
import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

from openai import OpenAI

load_dotenv(Path(__file__).parent / ".env")

sys.path.insert(0, str(Path(__file__).parent))
from emotions_descriptions import TAG_LABELS

DATA_PATH = Path(__file__).parent / "emotions.csv"
OUTPUT_PATH = Path(__file__).parent / "emotions_relabeled.csv"

SYSTEM_PROMPT = """You are a debt-collection emotion tag classifier.

You receive a list of emotion tags (each with an example utterance and the old label) and must classify each tag into exactly one of the categories below.

Each category maps to a specific collector response strategy. Classify by what **collector response the emotion requires**, not just semantic similarity.

## Categories

{categories}

## Rules

1. Every tag MUST be assigned to exactly one category key from the list above.
2. Choose the category that best captures the **action-oriented meaning** of the tag — what response strategy the collector should use.
3. Pay attention to distinctions:
   - "distress" = real hardship, not giving up; needs empathy + practical relief
   - "despair" = hopelessness, resignation, extreme distress; needs de-escalation, NO pressure
   - "complaint" = dissatisfaction with facts/rules/outcomes; needs explanation of rules
   - "irritation" = annoyed by collection contact itself; needs cooling down, fewer interruptions
   - "hostility" = active aggression/threats; needs risk control, boundary setting
   - "anxiety" = worry about future risks; needs clarity, consequence explanation
   - "distrust" = does not trust institution/policy; needs trust-building, transparency
   - "confusion" = cannot understand information; needs clear explanation, examples
   - "defensive" = protects self-image, avoids blame; needs reduced accusation
   - "negotiation" = actively seeks conditional adjustment; needs structured negotiation
   - "engagement" = cooperation, positive intent; needs recognition, forward execution
4. Return a JSON object mapping each tag string to its category key.
5. Do NOT invent new categories. Use only the keys listed above."""

USER_PROMPT_TEMPLATE = """Classify the following {count} emotion tags into the categories defined above.

Return a JSON object like: {{"tag_name": "category_key", ...}}

Tags:
{tags}"""


def build_categories_block():
    lines = []
    for key, val in TAG_LABELS.items():
        lines.append(f'- **{key}** ({val["domain"]}): {val["description"]}')
    return "\n".join(lines)


def load_data(limit=None, input_path=None):
    path = input_path or DATA_PATH
    with open(path, "r", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)
    ncols = len(rows[0]) if rows else 0
    if rows and rows[0][0] == "tag":
        header, data = rows[0], rows[1:]
    else:
        header = ["tag", "example", "count", "old_label"][:ncols] + ["old_label"] * (4 - ncols)
        if len(header) > ncols:
            header = header[:ncols]
        header = ["tag", "example", "count", "old_label"]
        data = rows
    for row in data:
        while len(row) < 4:
            row.append("unspecified")
    if limit:
        data = data[:limit]
    return header, data


def format_tags_for_prompt(batch):
    lines = []
    for row in batch:
        tag, example, count, old_label = row[0], row[1], row[2], row[3]
        lines.append(f'{count}. `{tag}` — "{example}" (old: {old_label})')
    return "\n".join(lines)


def classify_batch(client, model, batch, categories_block):
    tags_text = format_tags_for_prompt(batch)
    system = SYSTEM_PROMPT.format(categories=categories_block)
    user = USER_PROMPT_TEMPLATE.format(count=len(batch), tags=tags_text)

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    raw = resp.choices[0].message.content
    try:
        mapping = json.loads(raw)
    except json.JSONDecodeError:
        print(f"  WARNING: failed to parse LLM response, retrying...\n  Raw: {raw[:200]}")
        return {}

    return mapping


def validate_mapping(mapping, batch):
    valid_keys = set(TAG_LABELS.keys())
    tag_names = {row[0] for row in batch}
    issues = []

    missing = tag_names - set(mapping.keys())
    if missing:
        issues.append(f"  Missing tags in response: {missing}")

    extra = set(mapping.keys()) - tag_names
    if extra:
        issues.append(f"  Extra tags in response: {extra}")

    bad_cats = {k: v for k, v in mapping.items() if v not in valid_keys}
    if bad_cats:
        issues.append(f"  Invalid categories: {bad_cats}")

    return issues


def main():
    parser = argparse.ArgumentParser(description="LLM-based emotion tag relabeling pipeline")
    parser.add_argument("--limit", type=int, default=20, help="Number of rows to classify (default: 20)")
    parser.add_argument("--all", action="store_true", help="Classify all rows")
    parser.add_argument("--batch-size", type=int, default=20, help="Tags per LLM call (default: 20)")
    parser.add_argument("--model", default="deepseek-chat", help="Model name (default: deepseek-chat)")
    parser.add_argument("--dry-run", action="store_true", help="Print prompts without calling LLM")
    parser.add_argument("--input", type=str, default=None, help="Input CSV path (default: emotions.csv)")
    parser.add_argument("--output", type=str, default=None, help="Output CSV path (default: emotions_relabeled.csv)")
    args = parser.parse_args()

    limit = None if args.all else args.limit
    input_path = Path(args.input) if args.input else None
    output_path = Path(args.output) if args.output else None
    header, data = load_data(limit, input_path)
    src_name = input_path.name if input_path else DATA_PATH.name
    print(f"Loaded {len(data)} rows from {src_name}")

    categories_block = build_categories_block()

    if args.dry_run:
        print("\n=== SYSTEM PROMPT ===")
        print(SYSTEM_PROMPT.format(categories=categories_block)[:500] + "...")
        print(f"\n=== USER PROMPT (first batch of {args.batch_size}) ===")
        batch = data[: args.batch_size]
        print(USER_PROMPT_TEMPLATE.format(count=len(batch), tags=format_tags_for_prompt(batch)))
        return

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("ERROR: set DEEPSEEK_API_KEY in .env or environment")
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    tag_to_new_label = {}

    batches = [data[i : i + args.batch_size] for i in range(0, len(data), args.batch_size)]
    print(f"Classifying in {len(batches)} batch(es) of ≤{args.batch_size} tags each...\n")

    for i, batch in enumerate(batches):
        print(f"Batch {i + 1}/{len(batches)} ({len(batch)} tags)...")
        mapping = classify_batch(client, args.model, batch, categories_block)

        issues = validate_mapping(mapping, batch)
        if issues:
            for iss in issues:
                print(iss)
            for row in batch:
                tag = row[0]
                if tag in mapping and mapping[tag] in TAG_LABELS:
                    tag_to_new_label[tag] = mapping[tag]
                else:
                    tag_to_new_label[tag] = "unclassified"
        else:
            tag_to_new_label.update(mapping)

        for row in batch[:3]:
            tag = row[0]
            new = tag_to_new_label.get(tag, "?")
            domain = TAG_LABELS.get(new, {}).get("domain", "?")
            print(f"  {tag:40s} -> {new:25s} ({domain})")
        if len(batch) > 3:
            print(f"  ... and {len(batch) - 3} more")

    header_out = header + ["new_label"]
    out_rows = [header_out]
    for row in data:
        tag = row[0]
        new_label = tag_to_new_label.get(tag, "unclassified")
        out_rows.append(row + [new_label])

    out_path = output_path or OUTPUT_PATH
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(out_rows)

    print(f"\nWrote {len(out_rows) - 1} rows to {out_path}")

    from collections import Counter

    dist = Counter(tag_to_new_label.values())
    print("\nCategory distribution:")
    for cat, cnt in dist.most_common():
        domain = TAG_LABELS.get(cat, {}).get("domain", "?")
        print(f"  {cat:30s} ({domain:12s}): {cnt}")


if __name__ == "__main__":
    main()
