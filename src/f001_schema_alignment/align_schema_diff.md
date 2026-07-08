# align_schema.py diff — custInfo migration

## 1. Replace `_map_credit_rating` with direct pass-through (line 40–43)

```diff
-def _map_credit_rating(raw):
-    first = raw[0] if raw else "0"
-    mapping = {"Z": "good", "B": "moderate", "2": "moderate", "3": "moderate", "0": "bad"}
-    return mapping.get(first, "unknown")
```

(Removed entirely — risk level is now stored as raw value, not classified.)

## 2. Add `_parse_custInfo` helper (after line 78)

```diff
+def _parse_custInfo(raw):
+    if not raw:
+        return {}
+    try:
+        tags = json.loads(raw) if isinstance(raw, str) else raw
+        return {t["tagName"]: t.get("tagValue", "") for t in tags if "tagName" in t}
+    except (json.JSONDecodeError, TypeError):
+        return {}
```

## 3. Rewrite `build_context` (lines 82–108)

Old context used nonexistent tag names. New context maps to actual `custInfo` tags.

```diff
 def build_context(customer_info, mob_typ):
     return {
-        "has_auto_loan": _parse_bool_has(customer_info.get("他行是否有车贷", ""), "有车贷")
-        or _parse_bool_has(customer_info.get("我行是否有车贷", ""), "有车贷"),
-        "has_mortgage": _parse_bool_has(customer_info.get("他行是否有房贷", ""), "有房贷")
-        or _parse_bool_has(customer_info.get("我行是否有房贷", ""), "有房贷"),
-        "credit_rating": _map_credit_rating(customer_info.get("24期缴款评等", "")),
-        "days_delinquent": _map_days_delinquent(mob_typ),
-        "total_debt": _parse_int(customer_info.get("总欠款", "0")),
-        "external_debt": _parse_external_debt(customer_info.get("外部欠款金额", "")),
-        "has_negotiation_history": customer_info.get("历史协商情况", "") != "无协商历史",
-        "available_plans": _parse_available_plans(customer_info.get("当前可使用的协商方案", "")),
-        "social_insurance_stable": "有社保" in customer_info.get("社保缴纳情况", "")
-        and "灵活就业" not in customer_info.get("社保缴纳情况", ""),
-        "card_restricted": customer_info.get("是否管制", "") != "可正常使用卡片",
-        "is_cash_out_customer": customer_info.get("是否为套现客户", "") != "非套现客户",
-        "external_debt_institutions": _parse_external_debt_institutions(customer_info.get("外部共债机构数", "")),
-        "interest_ratio": _parse_percentage(customer_info.get("利息占欠款比例", "0%")),
-        "installment_ratio": _parse_percentage(customer_info.get("分期金额占欠款比例", "0%")),
-        "age": _parse_int(customer_info.get("年龄", "0")),
-        "gender": customer_info.get("性别", ""),
-        "education": _map_education(customer_info.get("学历", "")),
-        "industry": customer_info.get("行业", ""),
-        "has_complaint_history": "没有" not in customer_info.get("历史投诉情况", "没有"),
-        "has_legal_tools": customer_info.get("当前可使用的法务工具", "") != "无可用的法务工具",
-        "is_negotiation_brain_customer": customer_info.get("是否谈判大脑客户", "") == "Y",
+        "business_loan_balance": _parse_int(customer_info.get("经营贷款余额", "0")),
+        "mortgage_balance": _parse_int(customer_info.get("商业房贷余额", "0")),
+        "other_loan_balance": _parse_int(customer_info.get("其他贷款余额", "0")),
+        "wealth_value": _parse_int(customer_info.get("理财时点值", "0")),
+        "current_balance": _parse_int(customer_info.get("目前余额", "0")),
+        "has_business_loan": _parse_int(customer_info.get("经营贷款余额", "0")) > 0,
+        "has_mortgage": _parse_int(customer_info.get("商业房贷余额", "0")) > 0,
+        "has_other_loan": _parse_int(customer_info.get("其他贷款余额", "0")) > 0,
+        "risk_level": _parse_int(customer_info.get("客户风险标识等级", "0")),
+        "complaint_score": _parse_int(customer_info.get("客户投诉评分", "0")),
+        "education": _map_education(customer_info.get("学历", "")),
+        "days_delinquent": _map_days_delinquent(mob_typ),
+        "recent_repayment": customer_info.get("（掌生APP操作）近7天-还款操作", "") == "Y",
+        "recent_contact_count": _parse_int(customer_info.get("近7日接通次数", "0")),
+        "is_high_risk_proxy_complaint": customer_info.get("持卡用户是否疑似高风险代理投诉", "") == "是",
+        "is_proxy_intermediary_complaint": customer_info.get("持卡用户是否疑似代理中介投诉", "") == "是",
+        "has_social_insurance": bool(customer_info.get("持卡人当前是否缴纳社保", "")),
+        "vehicle_count": _parse_int(customer_info.get("持卡用户名下历史车辆数", "0")),
     }
```

## 4. Rewrite `align_record` (lines 126–147)

Old version read stale snake_case fields. New version reads canonical camelCase fields from source and parses `custInfo` JSON string.

```diff
 def align_record(record, labeled_lookup=None):
     dialog = record["response"]["dialog"]
-    customer_info = record.get("customer_info", {})
+    cust_info_dict = _parse_custInfo(record.get("custInfo", ""))
     labeled_dialog = None
     if labeled_lookup is not None:
         labeled_rec = labeled_lookup.get(record["call_id"])
         if labeled_rec is not None:
             labeled_dialog = labeled_rec["response"]["dialog"]
     return {
         "call_id": record["call_id"],
         "cust_no": record.get("cust_no") or record.get("custno", ""),
-        "call_date": record.get("call_date", ""),
-        "coll_user_id": record.get("coll_user_id", ""),
-        "mob_typ": record.get("mob_typ", ""),
-        "talk_time": record.get("talk_time", ""),
-        "plan_evaluation": record.get("plan_evaluation", ""),
-        "customer_info": customer_info,
+        "dialDate": record.get("dialDate", ""),
+        "connectDate": record.get("connectDate", ""),
+        "dialType": record.get("dialType", ""),
+        "ringTime": record.get("ringTime", ""),
+        "collUserId": record.get("collUserId", ""),
+        "collId": record.get("collId", ""),
+        "collArea": record.get("collArea", ""),
+        "collGroupId": record.get("collGroupId", ""),
+        "acNo": record.get("acNo", ""),
+        "isRecorded": record.get("isRecorded", ""),
+        "result": record.get("result", ""),
+        "talkTime": record.get("talkTime", ""),
+        "channel": record.get("channel", ""),
+        "corpCode": record.get("corpCode", ""),
+        "calledNo": record.get("calledNo", ""),
+        "mobTyp": record.get("mobTyp", ""),
+        "phoneRoute": record.get("phoneRoute", ""),
+        "agentTalkTime": record.get("agentTalkTime", ""),
+        "custInfo": record.get("custInfo", ""),
         "turns_annotated": build_turns_annotated(dialog, labeled_dialog),
         "reward": None,
         "state_transitions": [],
-        "context": build_context(customer_info, record.get("mob_typ", "")),
+        "context": build_context(cust_info_dict, record.get("mobTyp", "")),
     }
```
