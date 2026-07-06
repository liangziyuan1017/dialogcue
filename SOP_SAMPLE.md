# Mined SOP Sample — Financial Hardship

> Generated from `output_rewarded.py` (31 annotated calls, 6 successful).
> This is a **draft** sample — `review_status: draft`, not loaded by the online system.
> Produced by running the `SOP_MINING.md` pipeline manually on the current dataset.

---

## Dataset Summary

| Metric | Value |
|---|---|
| Total annotated calls | 31 |
| Successful calls (reward=1) | 6 (19.4%) |
| Calls in this cluster | 14 |
| Successful calls in cluster | 2 (14.3%) |
| Wilson confidence (lower bound) | 0.040 |
| Review status | `draft` (confidence < 0.15 threshold) |

---

## SOP Definition

### Identity

| Field | Value |
|---|---|
| `sop_id` | `mined_financial_hardship` |
| `source` | `mined` |
| `review_status` | `draft` |
| `advisory` | `false` |
| `severity` | 4 (success rate 14.3% < 20%) |

### Triggers

**Facts:**

- `financial_hardship`

**Emotions:**

- `frustration`

### Anti-Goals

| Action | Success Rate | Failure Rate | Reason |
|---|---|---|---|
| `legal_threat` | 0% (0/2) | 17% (2/12) | Appears only in failed calls — correlates with failure |

### Compliance Guard

| Action | Success Rate | Blocked? | Reason |
|---|---|---|---|
| `pressure` | 100% (2/2) | Yes — `NEVER_GOAL_ACTIONS` | Appears in all successes but is coercive; never mined as a goal |

### Completion

| Field | Value |
|---|---|
| `min_goals` | 4 |
| `total_goals` | 4 |

---

## Goals

### Goal 1: Empathy

| Field | Value |
|---|---|
| `id` | `goal_empathy` |
| `collector_action` | `empathy` |
| `priority` | 3 |
| `lift` | ∞ (appears in 100% of successes) |
| `required` | Yes |

**Sub-themes:**

**Theme 1 — 确认客户当前资金周转困难** (4 sentences, 2 calls)

> "就是说目前还没有周转到这个资金，是吗？"
>
> "噢，就是说还是要等到解封，对吧？但您现在最需要的就是时间啊，张先生，对吧？"

**Theme 2 — 理解客户被冻结/起诉的处境** (2 sentences, 1 call)

> "工资卡都已经被冻结了？工行那边起诉的事情是吧？"
>
> "工行那边起诉的那个事情是吧？"

---

### Goal 2: Information

| Field | Value |
|---|---|
| `id` | `goal_information` |
| `collector_action` | `information` |
| `priority` | 2 |
| `lift` | ∞ |
| `required` | Yes |

**Sub-themes:**

**Theme 1 — 回顾客户之前反馈的困难和协商历史** (5 sentences, 2 calls)

> "我们看了一下，您之前反馈过目前经济比较困难，多行欠款，希望减免息费，少还一点，减轻压力，对吧？"
>
> "那之前一线工作人员不是给您提供了一个还1000块钱的方案嘛，说帮您把两期账单清零，下次还款时间到6月份。这个方案您还有印象吗？"

**Theme 2 — 说明逾期金额和还款详情** (4 sentences, 2 calls)

> "您看到了。张先生，您这边逾期的最低应缴款是440块钱。"
>
> "然后那个还款方案有相应的注意事项，我大概跟您说一下好吧。"

---

### Goal 3: Plan Proposal

| Field | Value |
|---|---|
| `id` | `goal_plan_proposal` |
| `collector_action` | `plan_proposal` |
| `priority` | 4 |
| `lift` | ∞ |
| `required` | Yes |

**Sub-themes:**

**Theme 1 — 提出具体金额和时间的还款方案** (6 sentences, 2 calls)

> "那这个方案您能处理的话，我这边确实可以帮您申请下次还款日到6月份，而且相应的息费也可以申请减免掉。"
>
> "张先生，所以说您看一下，想办法在周一之前把1000块钱处理进来，好吧？"

**Theme 2 — 建议替代筹资途径** (2 sentences, 1 call)

> "您看一下这样吧，您工资卡被冻结，您让家人朋友那边帮您想一下办法，直接把这个资金转到信用卡里面，也算是您还款。"

---

### Goal 4: Closure

| Field | Value |
|---|---|
| `id` | `goal_closure` |
| `collector_action` | `closure` |
| `priority` | 6 |
| `lift` | ∞ |
| `required` | Yes |

**Sub-themes:**

**Theme 1 — 约定后续联系和方案跟进** (2 sentences, 2 calls)

> "嗯，行，那张先生，我们到时候再联系，祝您生活愉快，再见。"
>
> "明白了，明白的。那您的情况我这边了解了。张先生，如果有合适的方案，我会再给您来电话的。"

---

## Evidence

| Field | Value |
|---|---|
| `call_count` | 14 |
| `success_count` | 2 |
| `failure_count` | 12 |
| `success_rate` | 14.3% |
| `global_success_rate` | 19.4% |
| `lift_over_baseline` | 0.74 |
| `insufficient_success_data` | `false` |

---

## Confidence

| Field | Value |
|---|---|
| `sop_confidence` (Wilson LB) | 0.040 |
| `sample_size` | 14 |
| `success_sample_size` | 2 |

> **Why `draft`:** Wilson lower bound is 0.040, well below the 0.15 auto-approval threshold. With only 2 successful calls in the cluster, all goals have `lift = ∞` (both successes share identical action profiles), so the pipeline cannot yet differentiate which actions drive success. The anti-goal signal (`legal_threat`) is clear. Once reward labeling runs on the full 107 records (50+ successes expected), lift scores will differentiate and confidence will improve.

---

## Successful Call Profiles

### Call 1: `2320459500460373224`

| Turn | Action | Excerpt |
|---|---|---|
| 1 | greeting | "喂,您好，请问是张先生吗？" |
| 2 | information | "您之前反馈过目前经济比较困难，多行欠款，希望减免息费…" |
| 3 | plan_proposal | "那这个方案您能处理的话，我这边确实可以帮您申请下次还款日到6月份…" |
| 4 | empathy | "工行那边起诉的那个事情是吧？" |
| 5 | empathy | "还是要等到解封，对吧？但您现在最需要的就是时间啊" |
| 6 | plan_proposal | "您工资卡被冻结，您让家人朋友那边帮您想一下办法" |
| 7 | plan_proposal | "想办法在周一之前把1000块钱处理进来，好吧？" |
| 8 | empathy | "那您明天我们也不给您来电，您专心周转，好吧？" |
| 9 | closure | "我们到时候再联系，祝您生活愉快，再见。" |

**Customer facts:** `financial_hardship`, `multiple_debts`, `bank_account_frozen`, `legal_procedure_pending`, `debt_priority`
**Customer emotions:** `frustration`

### Call 2: `2317662270201974818`

| Turn | Action | Excerpt |
|---|---|---|
| 1 | information | "您的个人信用卡逾期问题。银行给您发的短信您有看到吗？" |
| 2 | information | "您这边逾期的最低应缴款是440块钱。" |
| 3 | plan_proposal | "在线处理一下440块钱。我这边帮您在线撤案" |
| 4 | information | "之前给您办理的那个特殊优惠方案，不是每个月让您还600多块钱就可以了嘛" |
| 5 | plan_proposal | "银行也是愿意帮助您的…您产生的利息违约金，我这边申请一下给您减免掉" |
| 6 | empathy | "我们银行呢，也是一直有在跟您不断的沟通和联系的。确实银行就是不会不管您的" |
| 7 | plan_proposal | "您想后期还全款的话…您周转到后就还进来440块钱" |
| 8 | closure | "如果有合适的方案，我会再给您来电话的。" |

**Customer facts:** `financial_hardship`, `prior_contact_attempt`, `unresolved_issue`, `missed_contact_explanation`
**Customer emotions:** `frustration`, `defensive`, `helplessness`

---

## Assessment

### What Works

- **Goals are real** — every goal is backed by actual collector sentences from successful calls.
- **Sub-themes are concrete** — each theme has specific example sentences showing exactly what successful collectors said.
- **Anti-goal is clear** — `legal_threat` appears in 0% of successes, 17% of failures.
- **Compliance guard works** — `pressure` appears in 100% of successes but is correctly blocked from being a goal.
- **Review gate works** — SOP is `draft`, will not influence live recommendations until a human approves it.

### What's Limited

- **Only 2 successful calls** — all goals have `lift = ∞` because both successes have identical action profiles. Cannot yet differentiate which actions drive success.
- **Wilson confidence 0.040** — well below the 0.15 auto-approval threshold.
- **No goal-quality differentiation** — with 2 successes, the humane scoring LLM judge has very little data to evaluate.
- **Cluster success rate (14.3%) is below global rate (19.4%)** — the situation is harder than average, which is why severity is 4.

### What Changes with 107 Calls (50+ Successes)

- Lift scores will differentiate (not all ∞) — some goals will be `required`, others `optional`.
- Wilson confidence will cross 0.15 → SOPs can `auto_approved`.
- Sub-theme clustering will find more distinct themes per goal.
- Anti-goal detection will be more reliable with larger failure sample.
- LLM quality assessment will have more example sentences to evaluate.
