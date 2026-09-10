import argparse
import json
import sys
from collections import Counter
from pathlib import Path

INPUT_REQUIRED = {"call_id", "dialog", "custInfo"}
INPUT_ALLOWED_KEYS = INPUT_REQUIRED

# Tags present on every record in data/data_input/*.jsonl
CI_ALWAYS_TAGS = {
    "经营贷款余额",
    "理财资产时点值",
    "最高学历",
    "商业房贷余额",
    "其他贷款余额",
    "高风险代理投诉",
    "代理中介投诉",
    "当前社保缴纳状态",
    "账户当前余额",
    "客户标签",
    "历史车辆数量",
    "近7日接通次数",
    "客户风险等级",
    "客户投诉评分",
}

# Same semantic field; either name is accepted
CI_REPAYMENT_TAGS = {
    "近7日还款操作",
    "（掌生APP操作）近7天-还款操作",
}

CI_KNOWN_TAGS = CI_ALWAYS_TAGS | CI_REPAYMENT_TAGS


def _parse_cust_info(idx, ci_raw, errors):
    if isinstance(ci_raw, str):
        try:
            ci_parsed = json.loads(ci_raw)
        except json.JSONDecodeError as e:
            errors.append(f"record {idx}: custInfo is not valid JSON: {e}")
            return None
    else:
        ci_parsed = ci_raw

    if not isinstance(ci_parsed, list):
        errors.append(f"record {idx}: custInfo must be a list, got {type(ci_parsed).__name__}")
        return None
    return ci_parsed


def _check_cust_info(idx, ci_parsed, errors):
    seen_tags = set()
    for j, item in enumerate(ci_parsed):
        if not isinstance(item, dict):
            errors.append(f"record {idx}: custInfo[{j}] must be a dict")
            continue
        if "tagName" not in item:
            errors.append(f"record {idx}: custInfo[{j}] missing 'tagName'")
            continue
        if "tagValue" not in item:
            errors.append(f"record {idx}: custInfo[{j}] missing 'tagValue'")
            continue
        tn = item["tagName"]
        if not isinstance(tn, str) or not tn:
            errors.append(f"record {idx}: custInfo[{j}] tagName must be a non-empty string")
            continue
        if tn in seen_tags:
            errors.append(f"record {idx}: custInfo duplicate tagName '{tn}'")
        seen_tags.add(tn)
        if tn not in CI_KNOWN_TAGS:
            errors.append(f"record {idx}: custInfo[{j}] unknown tagName '{tn}'")
        tv = item["tagValue"]
        if tv is not None and not isinstance(tv, (str, int, float, bool)):
            errors.append(
                f"record {idx}: custInfo[{j}] tagValue must be a scalar, got {type(tv).__name__}"
            )

    missing_tags = CI_ALWAYS_TAGS - seen_tags
    if missing_tags:
        errors.append(f"record {idx}: custInfo missing always-present tags: {sorted(missing_tags)}")
    if not (seen_tags & CI_REPAYMENT_TAGS):
        errors.append(
            f"record {idx}: custInfo missing repayment tag "
            f"(one of {sorted(CI_REPAYMENT_TAGS)})"
        )


def check_record(idx, record):
    """Validate one input record. Returns (format_name, errors)."""
    errors = []
    keys = set(record.keys())

    missing = INPUT_REQUIRED - keys
    if missing:
        for key in sorted(missing):
            errors.append(f"record {idx}: missing required key '{key}'")
        return "unknown", errors

    extra = keys - INPUT_ALLOWED_KEYS
    if extra:
        errors.append(f"record {idx}: unexpected keys: {sorted(extra)}")

    if not isinstance(record["call_id"], str) or not record["call_id"]:
        errors.append(f"record {idx}: call_id must be a non-empty string, got {record['call_id']!r}")
    if not isinstance(record["dialog"], str):
        errors.append(f"record {idx}: dialog must be a string, got {type(record['dialog']).__name__}")
    elif not record["dialog"].strip():
        errors.append(f"record {idx}: dialog must be a non-empty string")

    ci_parsed = _parse_cust_info(idx, record["custInfo"], errors)
    if ci_parsed is not None:
        _check_cust_info(idx, ci_parsed, errors)

    return "input", errors


def check_file(path, strict=False):
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    all_errors = []
    format_counts = Counter()
    call_ids = set()
    duplicate_ids = set()
    parse_errors = 0

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as e:
            all_errors.append(f"line {i + 1}: JSON parse error: {e}")
            parse_errors += 1
            continue

        fmt, errors = check_record(i, record)
        format_counts[fmt] += 1
        all_errors.extend(errors)

        cid = record.get("call_id", "")
        if cid:
            if cid in call_ids:
                duplicate_ids.add(cid)
            call_ids.add(cid)

    total = sum(format_counts.values())

    print(f"File: {path}")
    print(f"Records: {total}")
    print(f"Formats: input={format_counts['input']}, unknown={format_counts['unknown']}")
    print(f"Unique call_ids: {len(call_ids)}")
    if duplicate_ids:
        print(f"Duplicate call_ids: {len(duplicate_ids)}")
        for d in sorted(duplicate_ids)[:10]:
            print(f"  {d}")
        if len(duplicate_ids) > 10:
            print(f"  ... and {len(duplicate_ids) - 10} more")
    if parse_errors:
        print(f"Parse errors: {parse_errors}")

    if all_errors:
        print(f"\nErrors ({len(all_errors)}):")
        for e in all_errors[:50]:
            print(f"  {e}")
        if len(all_errors) > 50:
            print(f"  ... and {len(all_errors) - 50} more")
    else:
        print("\nAll records valid.")

    if strict and all_errors:
        sys.exit(1)

    return len(all_errors) == 0


def main():
    parser = argparse.ArgumentParser(
        description="Validate data_input JSONL format (call_id, dialog, custInfo)"
    )
    parser.add_argument(
        "file",
        type=Path,
        nargs="?",
        default=Path("data/data_input/input_data.jsonl"),
        help="Path to JSONL file",
    )
    parser.add_argument("--strict", action="store_true", help="Exit with code 1 on any error")
    args = parser.parse_args()

    if not args.file.exists():
        print(f"File not found: {args.file}")
        sys.exit(1)

    ok = check_file(args.file, strict=args.strict)
    if not ok and args.strict:
        sys.exit(1)


if __name__ == "__main__":
    main()
