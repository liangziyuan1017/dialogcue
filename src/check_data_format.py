import argparse
import json
import sys
from collections import Counter
from pathlib import Path

CANONICAL_REQUIRED = {"call_id", "dialog", "call_date", "cust_no", "coll_user_id", "mob_typ", "talk_time", "plan_evaluation", "customer_info"}
CANONICAL_OPTIONAL = set()

RAW_REQUIRED = {"call_id", "dialog", "cust_no"}
RAW_EXPECTED_EXTRA = {
    "acNo", "agentTalkTime", "calledNo", "channel", "collArea", "collGroupId",
    "collId", "collUserId", "connectDate", "corpCode", "custInfo", "dialDate",
    "dialType", "id", "isRecorded", "mobTyp", "phoneRoute", "result", "ringTime", "talkTime",
}

CI_CANONICAL_ALWAYS = {
    "经营贷款余额", "其他贷款余额", "学历", "商业房贷余额",
    "持卡客户是否疑似高风险代理投诉", "持卡客户是否疑似代理中介投诉",
    "总欠款", "ct标签", "近7天还款操作", "近7日接通次数", "客户投诉评分",
}
CI_CANONICAL_OPTIONAL = {
    "社保缴纳情况", "名下历史车辆数", "客户风险标识等级",
    "理财时点值",
}

MOB_TYP_VALUES = {"", "M1", "M2", "M3", "M4", "M5", "M6"}


def check_record(idx, record):
    errors = []
    keys = set(record.keys())

    if CANONICAL_REQUIRED.issubset(keys):
        fmt = "canonical"
    elif RAW_REQUIRED.issubset(keys):
        fmt = "raw"
    else:
        if "call_id" not in keys:
            errors.append(f"record {idx}: missing required key 'call_id'")
        if "dialog" not in keys:
            errors.append(f"record {idx}: missing required key 'dialog'")
        return "unknown", errors

    if fmt == "canonical":
        if not isinstance(record["call_id"], str) or not record["call_id"]:
            errors.append(f"record {idx}: call_id must be a non-empty string, got {record['call_id']!r}")
        if not isinstance(record["dialog"], str):
            errors.append(f"record {idx}: dialog must be a string, got {type(record['dialog']).__name__}")
        if not isinstance(record["call_date"], str):
            errors.append(f"record {idx}: call_date must be a string")
        if not isinstance(record["cust_no"], str):
            errors.append(f"record {idx}: cust_no must be a string")
        if not isinstance(record["coll_user_id"], str):
            errors.append(f"record {idx}: coll_user_id must be a string")
        if record["mob_typ"] not in MOB_TYP_VALUES:
            errors.append(f"record {idx}: mob_typ '{record['mob_typ']}' not in {MOB_TYP_VALUES}")
        if not isinstance(record["talk_time"], str):
            errors.append(f"record {idx}: talk_time must be a string")
        if not isinstance(record["customer_info"], dict):
            errors.append(f"record {idx}: customer_info must be a dict, got {type(record['customer_info']).__name__}")
        else:
            ci = record["customer_info"]
            for k in CI_CANONICAL_ALWAYS:
                if k not in ci:
                    errors.append(f"record {idx}: customer_info missing always-present key '{k}'")
            unexpected = set(ci.keys()) - CI_CANONICAL_ALWAYS - CI_CANONICAL_OPTIONAL
            if unexpected:
                errors.append(f"record {idx}: customer_info has unexpected keys: {sorted(unexpected)}")

    elif fmt == "raw":
        if not isinstance(record["call_id"], str) or not record["call_id"]:
            errors.append(f"record {idx}: call_id must be a non-empty string")
        if not isinstance(record["dialog"], str):
            errors.append(f"record {idx}: dialog must be a string")
        if "custInfo" in record:
            ci_raw = record["custInfo"]
            if isinstance(ci_raw, str):
                try:
                    ci_parsed = json.loads(ci_raw)
                except json.JSONDecodeError as e:
                    errors.append(f"record {idx}: custInfo is not valid JSON: {e}")
                    ci_parsed = None
            else:
                ci_parsed = ci_raw
            if ci_parsed is not None:
                if not isinstance(ci_parsed, list):
                    errors.append(f"record {idx}: custInfo must parse to a list, got {type(ci_parsed).__name__}")
                else:
                    for j, item in enumerate(ci_parsed):
                        if not isinstance(item, dict):
                            errors.append(f"record {idx}: custInfo[{j}] must be a dict")
                        elif "tagName" not in item:
                            errors.append(f"record {idx}: custInfo[{j}] missing 'tagName'")

    return fmt, errors


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
            all_errors.append(f"line {i+1}: JSON parse error: {e}")
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
    print(f"Formats: canonical={format_counts['canonical']}, raw={format_counts['raw']}, unknown={format_counts['unknown']}")
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
    parser = argparse.ArgumentParser(description="Validate matched_data.jsonl format")
    parser.add_argument("file", type=Path, nargs="?", default=Path("data/data_input/matched_data.jsonl"), help="Path to JSONL file")
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
