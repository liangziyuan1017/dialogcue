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
RAW_ALL_KEYS = RAW_REQUIRED | RAW_EXPECTED_EXTRA

CI_ALWAYS_TAGS = {
    "学历",
    "持卡用户是否疑似高风险代理投诉",
    "持卡用户是否疑似代理中介投诉",
    "持卡人当前是否缴纳社保",
    "目前余额",
    "（掌生APP操作）近7天-还款操作",
    "持卡用户名下历史车辆数",
    "近7日接通次数",
    "客户风险标识等级",
    "客户投诉评分",
    "ct标签",
}
CI_OPTIONAL_TAGS = {
    "经营贷款余额",
    "商业房贷余额",
    "其他贷款余额",
    "理财时点值",
    "外部投诉评分",
    "重渠投诉次数",
    "12378次数",
}
CI_KNOWN_TAGS = CI_ALWAYS_TAGS | CI_OPTIONAL_TAGS

CI_CANONICAL_ALWAYS = CI_ALWAYS_TAGS
CI_CANONICAL_OPTIONAL = CI_OPTIONAL_TAGS

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
            unexpected = set(ci.keys()) - CI_KNOWN_TAGS
            if unexpected:
                errors.append(f"record {idx}: customer_info has unexpected keys: {sorted(unexpected)}")
            missing_tags = CI_ALWAYS_TAGS - set(ci.keys())
            if missing_tags:
                errors.append(f"record {idx}: customer_info missing always-present keys: {sorted(missing_tags)}")

    elif fmt == "raw":
        if not isinstance(record["call_id"], str) or not record["call_id"]:
            errors.append(f"record {idx}: call_id must be a non-empty string")
        if not isinstance(record["dialog"], str):
            errors.append(f"record {idx}: dialog must be a string")
        missing_keys = RAW_ALL_KEYS - keys
        if missing_keys:
            errors.append(f"record {idx}: missing raw keys: {sorted(missing_keys)}")
        extra_keys = keys - RAW_ALL_KEYS
        if extra_keys:
            errors.append(f"record {idx}: unexpected raw keys: {sorted(extra_keys)}")
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
                    seen_tags = set()
                    for j, item in enumerate(ci_parsed):
                        if not isinstance(item, dict):
                            errors.append(f"record {idx}: custInfo[{j}] must be a dict")
                            continue
                        if "tagName" not in item:
                            errors.append(f"record {idx}: custInfo[{j}] missing 'tagName'")
                            continue
                        tn = item["tagName"]
                        seen_tags.add(tn)
                        if tn not in CI_KNOWN_TAGS:
                            errors.append(f"record {idx}: custInfo[{j}] unknown tagName '{tn}'")
                    missing_tags = CI_ALWAYS_TAGS - seen_tags
                    if missing_tags:
                        errors.append(f"record {idx}: custInfo missing always-present tags: {sorted(missing_tags)}")

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
