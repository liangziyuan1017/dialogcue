# SOP Integration — Goal-Based SOP Layer on the Recommendation Engine

> Status: design spec, ready for implementation
> Source proposal: `SOP.md`
> Constraint: `state_extraction` is a pure feature extractor (moving to BERT). It must NOT make SOP decisions. The SOP layer is a **downstream consumer** of its output, fully decoupled.

---

## 1. Design Principles

1. **SOPs are unordered goal-checklists**, not linear flows. Goals are interchangeable — the engine picks the highest-priority unfulfilled goal each turn based on conversation context, not a fixed sequence.
2. **SOP biases the existing retrieval ranking; it does not replace it.** When no SOP is active, the system is byte-for-byte identical to today. SOP is a continuous dial (`w_sop`), not a branch.
3. **Three-mode seamless switching**, all automatic:
   - No SOP detected → pure decision-tree ranking (current system).
   - SOP detected at turn 1 → SOP-biased ranking from the start.
   - SOP detected mid-conversation → SOP activates on that turn, biases ranking immediately.
   - SOP goals complete → SOP deactivates, pure decision-tree resumes.
4. **No generative path.** The system retrieves historical collector scripts; it does not generate text. SOP influences *which* retrieved script wins, not *what* text is produced. This preserves the HWR/win-rate signal the ranking depends on.
5. **state_extraction is not involved in SOP decisions.** It produces `facts`, `emotions`, `willingness` (today via DeepSeek, tomorrow via BERT). The SOP layer reads that output and makes all decisions itself.

---

## 2. Architecture (decoupled)

```
customer utterance
       │
       ▼
┌──────────────────┐
│  state_extraction │  (f008 — pure feature extractor, BERT later)
│  → facts          │  NO SOP logic here, ever
│  → emotions       │
│  → willingness    │
└──────┬───────────┘
       │  (output only)
       ▼
┌──────────────────┐
│  SOP layer (f011) │  ← NEW, fully decoupled
│                   │
│  1. detect_sop()  │  deterministic fact→SOP lookup (no LLM)
│     facts → sop   │
│                   │
│  2. track_goals() │  independent goal-completion checker
│     transcript →  │  (rule-based default, optional LLM)
│     completed[]   │  NOT state_extraction
│                   │
│  3. sop_score()   │  per-candidate bias score
│     candidate →   │
│     0.0 / 1.0     │
└──────┬───────────┘
       │  (sop_score per candidate + active_sop metadata)
       ▼
┌──────────────────┐
│  retrieval_engine │  (f006 — existing, +1 ranking term)
│  rank_sentences   │
│  + w_sop·sop_score│
└──────────────────┘
```

**Key decoupling point:** the SOP layer sits between state_extraction and retrieval_engine. It consumes state_extraction's *output* (`facts`, `emotions`) but never calls state_extraction, never extends its prompt, and never depends on its internal mechanism. When state_extraction swaps to BERT, the SOP layer is unchanged — it still reads the same `facts` list.

---

## 3. SOP Catalog

Hand-authored starting catalog derived from the taxonomy in `src/f000_keyword_discovery/data/state_keywords.json` (50+ fact groups → 8 SOPs). These are **not** mined from call data — they are domain-expert SOPs using the taxonomy's fact/emotion/action group names. The automatic mining tool (`SOP_MINING.md`) produces a separate `sop_catalog_mined.yaml` from `output_rewarded.py` (annotated call data with reward labels). At server startup, both catalogs are loaded; hand-authored overrides mined for the same `sop_id` (see §11.5). Each SOP maps trigger facts to goals. Goals map to collector-action groups already in the taxonomy, so the ranking bias can operate on existing sentence metadata — no new tagging required.

> **Note on `legal_threat` as a goal action:** SOPs 3.3 and 3.6 use `collector_action: legal_threat` for goals like `explain_implications` and `explain_consequences`. These are hand-authored and intentional — the collector explains legal consequences *factually*, not as a threat. The mining pipeline (`SOP_MINING.md` Step 4a) blocks `legal_threat` from being *mined* as a goal (`NEVER_GOAL_ACTIONS`), because mined SOPs can't distinguish factual legal explanation from coercive threat. Hand-authored SOPs can override this guard because a domain expert has vetted the intent.

### 3.1 SOP: Financial Hardship

```yaml
sop_id: financial_hardship
severity: 3
trigger_facts:
  - financial_hardship
  - unemployment
  - unemployment_duration
  - salary_delay
  - family_illness
  - illness
  - business_difficulty
  - temporary_inability_to_pay
trigger_emotions:
  - distress
  - helplessness
  - stress
goals:
  - id: empathy
    description: "Acknowledge the customer's hardship with empathy"
    collector_action: empathy
    priority: 1
  - id: assess_situation
    description: "Understand the specific financial situation and cause"
    collector_action: information
    priority: 2
  - id: explain_options
    description: "Explain available hardship assistance options before demanding payment"
    collector_action: plan_proposal
    priority: 3
  - id: determine_affordability
    description: "Determine what the customer can realistically pay"
    collector_action: information
    priority: 4
  - id: agree_next_action
    description: "Agree on a concrete next action or payment arrangement"
    collector_action: closure
    priority: 5
required:
  - "Do not pressure customer before empathy and options are delivered"
  - "Show empathy"
  - "Explain hardship options before demanding payment"
optional:
  - ask_about_employment
  - ask_about_expected_recovery
  - discuss_budget
  - schedule_callback
completion:
  min_goals: 4
  total_goals: 5
```

### 3.2 SOP: Multi-Bank Debt Crisis

```yaml
sop_id: multi_bank_debt_crisis
severity: 4
trigger_facts:
  - multiple_debts
  - negotiating_with_others
  - debt_priority
  - wage_garnishment
  - external_debt
  - external_debt_uncollected
trigger_emotions:
  - anxiety
  - helplessness
goals:
  - id: empathy
    description: "Acknowledge the multi-bank pressure situation"
    collector_action: empathy
    priority: 1
  - id: assess_total_exposure
    description: "Understand total debt across institutions and prioritization"
    collector_action: information
    priority: 2
  - id: explain_bank_position
    description: "Explain what this bank can offer relative to other creditors"
    collector_action: information
    priority: 3
  - id: propose_solution
    description: "Propose a solution that accounts for their other obligations"
    collector_action: plan_proposal
    priority: 4
  - id: agree_next_action
    description: "Agree on next action"
    collector_action: closure
    priority: 5
required:
  - "Do not dismiss other bank obligations"
  - "Acknowledge the customer is being pulled in multiple directions"
completion:
  min_goals: 4
  total_goals: 5
```

### 3.3 SOP: Account Frozen / Legal Escalation

```yaml
sop_id: account_frozen_legal
severity: 5
trigger_facts:
  - account_frozen
  - bank_account_frozen
  - card_frozen
  - account_locked
  - legal_procedure_pending
  - legal_procedure_awareness
  - legal_resolution
  - bankruptcy
trigger_emotions:
  - distress
  - helplessness
  - threat
goals:
  - id: empathy
    description: "Acknowledge the severity of the legal/frozen situation"
    collector_action: empathy
    priority: 1
  - id: understand_status
    description: "Understand current legal/frozen status and timeline"
    collector_action: information
    priority: 2
  - id: explain_implications
    description: "Explain what happens next legally and what the bank can/cannot do"
    collector_action: legal_threat
    priority: 3
  - id: explore_resolution
    description: "Explore available resolution paths (unfreeze, negotiate, legal settlement)"
    collector_action: plan_proposal
    priority: 4
  - id: agree_next_action
    description: "Agree on next action with realistic timeline"
    collector_action: closure
    priority: 5
required:
  - "Do not make legal promises the bank cannot keep"
  - "Acknowledge frozen funds before demanding payment"
  - "Explain legal consequences factually, not as threats"
completion:
  min_goals: 4
  total_goals: 5
```

### 3.4 SOP: Billing Dispute

```yaml
sop_id: billing_dispute
severity: 2
trigger_facts:
  - billing_dispute
  - high_interest
  - interest_accumulation
  - unresolved_issue
  - prior_contact_attempt
  - missed_contact_explanation
trigger_emotions:
  - frustration
  - anger
  - skepticism
  - accusation
goals:
  - id: empathy
    description: "Acknowledge the customer's frustration with the billing issue"
    collector_action: empathy
    priority: 1
  - id: verify_dispute
    description: "Verify the specific billing/interest discrepancy"
    collector_action: information
    priority: 2
  - id: explain_breakdown
    description: "Explain the charge/interest breakdown clearly"
    collector_action: information
    priority: 3
  - id: resolve_or_escalate
    description: "Resolve the dispute or escalate to proper channel"
    collector_action: plan_proposal
    priority: 4
  - id: agree_next_action
    description: "Agree on next action"
    collector_action: closure
    priority: 5
required:
  - "Do not dismiss the dispute"
  - "Verify before explaining"
completion:
  min_goals: 3
  total_goals: 5
```

### 3.5 SOP: Broken Promise / Re-negotiation

```yaml
sop_id: broken_promise_renegotiation
severity: 3
trigger_facts:
  - previous_agreement
  - previous_offer
  - negotiation_history
  - promise_to_pay
  - promise_date
  - payment_commitment_date
trigger_emotions:
  - defensiveness
  - frustration
goals:
  - id: reference_prior
    description: "Reference the prior agreement/offer accurately"
    collector_action: information
    priority: 1
  - id: understand_why_broken
    description: "Understand why the prior commitment was not met"
    collector_action: empathy
    priority: 2
  - id: assess_current
    description: "Assess current ability to pay"
    collector_action: information
    priority: 3
  - id: propose_new_plan
    description: "Propose a new realistic plan or reinstate the old one"
    collector_action: plan_proposal
    priority: 4
  - id: agree_next_action
    description: "Agree on next action with explicit commitment"
    collector_action: closure
    priority: 5
required:
  - "Acknowledge the prior agreement exists"
  - "Do not pretend the prior offer never happened"
completion:
  min_goals: 4
  total_goals: 5
```

### 3.6 SOP: Debt Evasion / Denial

```yaml
sop_id: debt_evasion_denial
severity: 4
trigger_facts:
  - debt_evasion
  - acknowledge_debt   # low/reluctant acknowledgment
trigger_emotions:
  - rejection
  - defensiveness
  - anger
  - threat
goals:
  - id: verify_identity_debt
    description: "Calmly verify the debt belongs to the customer"
    collector_action: information
    priority: 1
  - id: de_escalate
    description: "De-escalate the confrontation"
    collector_action: empathy
    priority: 2
  - id: present_evidence
    description: "Present factual account history/evidence"
    collector_action: information
    priority: 3
  - id: explain_consequences
    description: "Explain consequences of non-payment factually"
    collector_action: legal_threat
    priority: 4
  - id: offer_path_forward
    description: "Offer a path forward if they acknowledge"
    collector_action: plan_proposal
    priority: 5
required:
  - "Do not accuse or threaten"
  - "Stay factual and calm"
  - "Verify before disputing"
completion:
  min_goals: 3
  total_goals: 5
```

### 3.7 SOP: Installment / Negotiation Request

```yaml
sop_id: installment_request
severity: 2
trigger_facts:
  - request_installment
  - repayment_intent
  - ability_to_pay
  - income_statement
  - expected_income
trigger_emotions:
  - pleading
  - hesitation
  - conditional   # via willingness level 2
goals:
  - id: understand_request
    description: "Understand the specific installment/repayment request"
    collector_action: information
    priority: 1
  - id: assess_eligibility
    description: "Assess eligibility for requested plan"
    collector_action: information
    priority: 2
  - id: explain_options
    description: "Explain available plans (including alternatives if requested one unavailable)"
    collector_action: plan_proposal
    priority: 3
  - id: determine_affordability
    description: "Determine affordable payment amount and term"
    collector_action: plan_proposal
    priority: 4
  - id: agree_next_action
    description: "Agree on the plan and next action"
    collector_action: closure
    priority: 5
required:
  - "Do not refuse without explaining alternatives"
  - "Acknowledge the customer is trying to pay"
completion:
  min_goals: 4
  total_goals: 5
```

### 3.8 SOP: Emotional Escalation (Compliance Safety)

```yaml
sop_id: emotional_escalation
severity: 5
trigger_facts: []   # triggered by emotions only
trigger_emotions:
  - anger
  - threat
  - accusation
  - exhaustion
  - impatience
goals:
  - id: de_escalate
    description: "De-escalate the emotional intensity"
    collector_action: empathy
    priority: 1
  - id: acknowledge_concern
    description: "Acknowledge the specific complaint/threat explicitly"
    collector_action: information
    priority: 2
  - id: redirect_to_issue
    description: "Redirect conversation back to the debt issue calmly"
    collector_action: information
    priority: 3
  - id: offer_resolution
    description: "Offer a concrete resolution or next step"
    collector_action: plan_proposal
    priority: 4
required:
  - "Do not argue or match the customer's tone"
  - "Do not threaten back"
  - "If customer threatens complaint, acknowledge and provide proper channel"
completion:
  min_goals: 2
  total_goals: 4
```

---

## 4. SOP Detection

**Mechanism:** deterministic lookup, no LLM. Runs every turn after state_extraction produces its output.

```python
def detect_sop(extracted_facts: list[str], extracted_emotions: list[str], active_sop: SOP | None) -> SOP | None:
    """
    Called every turn with the OUTPUT of state_extraction.
    Does NOT call state_extraction. Does NOT use any LLM.
    """
    # 1. Check all SOPs for trigger matches
    candidates = []
    for sop in SOP_CATALOG:
        fact_match = len(set(sop.trigger_facts) & set(extracted_facts))
        emotion_match = len(set(sop.trigger_emotions) & set(extracted_emotions))
        if fact_match > 0 or emotion_match > 0:
            candidates.append((sop, sop.severity, fact_match + emotion_match))

    if not candidates:
        return active_sop  # keep existing SOP if still active (goals not complete)

    # 2. Highest severity wins; ties broken by match count
    candidates.sort(key=lambda x: (x[1], x[2]), reverse=True)
    best = candidates[0][0]

    # 3. If a higher-severity SOP appears mid-conversation, switch to it
    if active_sop and best.severity > active_sop.severity:
        return best  # mid-conversation switch to more urgent SOP

    # 4. If no active SOP, activate the best candidate
    if not active_sop:
        return best

    # 5. Keep current SOP if it's still active (don't flit between equal-severity SOPs)
    return active_sop
```

**Properties:**
- Runs in O(SOPs × triggers) — microseconds, no I/O.
- Mid-conversation activation is free: detection runs every turn, so if a customer mentions bankruptcy on turn 5, `account_frozen_legal` activates on turn 5.
- Mid-conversation escalation is handled: a higher-severity SOP preempts a lower one (e.g. customer gets angry during hardship discussion → `emotional_escalation` severity 5 preempts `financial_hardship` severity 3).
- Does not flit between same-severity SOPs — once active, stays until goals complete or a higher-severity one appears.

---

## 5. Goal Completion Tracking

**Constraint:** this is independent of state_extraction. It has its own mechanism.

**Default: rule-based matcher** (no LLM, deterministic, cheap).

Each goal has a completion rule evaluated against the conversation transcript (customer + collector turns so far). Rules check whether any collector turn's `extracted_actions` list contains the goal's action — a goal is "completed" when the collector has performed the corresponding action.

> **Transcript field:** collector turns are stored as `{"role": "collector", "utterance": "...", "extracted_actions": ["empathy", "information"]}` (see `server.py:591`). The `extracted_actions` field is a list of action strings produced by `extract_state` on the collector's utterance. Goal completion rules read this list, not a singular `collector_action` field.

```python
def _collector_actions_in_transcript(transcript: list[dict]) -> set[str]:
    """Extract all collector actions from the transcript."""
    actions = set()
    for t in transcript:
        if t.get("role") == "collector":
            actions.update(t.get("extracted_actions", []))
    return actions


GOAL_COMPLETION_RULES = {
    "empathy": lambda transcript: "empathy" in _collector_actions_in_transcript(transcript),
    "assess_situation": lambda transcript: any(
        "information" in t.get("extracted_actions", [])
        and contains(t.get("utterance", ""), ["困难", "情况", "什么原因", "收入", "工资"])
        for t in transcript if t.get("role") == "collector"
    ),
    "explain_options": lambda transcript: "plan_proposal" in _collector_actions_in_transcript(transcript),
    "determine_affordability": lambda transcript: any(
        "information" in t.get("extracted_actions", [])
        and contains(t.get("utterance", ""), ["还多少", "能还", "周转", "多少金额"])
        for t in transcript if t.get("role") == "collector"
    ),
    "agree_next_action": lambda transcript: "closure" in _collector_actions_in_transcript(transcript),
    # ... one rule per goal across all SOPs
}
```

The `extracted_actions` field on each collector transcript turn is already produced by the existing system (`server.py:587` calls `extract_state` on the collector utterance, which returns `actions`). So goal completion reuses **existing metadata on the transcript**, not state_extraction's current-turn output.

> **Reliability caveat:** `extract_state` was designed primarily for customer turns (facts/emotions/willingness). Its accuracy on collector utterances is unverified — the collector action taxonomy (`greeting`, `empathy`, `information`, `plan_proposal`, `pressure`, `closure`, `legal_threat`) is extracted via the same LLM + keyword fallback pipeline, but collector language patterns differ from customer language. If `extracted_actions` is unreliable, goal completion rules will fire incorrectly. **Mitigation:** validate `extract_state` accuracy on a sample of collector turns before relying on goal completion. If accuracy is poor, either (a) retrain/fine-tune the extraction for collector utterances, or (b) use a dedicated collector-action classifier (the future BERT model can handle this). The goal completion mechanism itself is sound — only the input quality is in question.

```python
def track_goals(sop: SOP, transcript: list[dict]) -> tuple[list[str], list[str]]:
    completed = []
    remaining = []
    for goal in sop.goals:
        rule = GOAL_COMPLETION_RULES.get(goal.id)
        if rule and rule(transcript):
            completed.append(goal.id)
        else:
            remaining.append(goal.id)
    return completed, remaining
```

**Optional upgrade:** a dedicated lightweight LLM call in the SOP module (`f011_sop/goal_checker.py`) that takes the transcript + goal list and returns completed/remaining. This is independent of state_extraction — separate call, separate prompt, separate module. Only enable if rule-based accuracy is insufficient. Default is rule-based.

**Completion check:**
```python
def is_sop_complete(sop: SOP, completed: list[str]) -> bool:
    return len(completed) >= sop.completion.min_goals
```

When complete → deactivate SOP → `w_sop = 0` → pure decision-tree resumes next turn.

---

## 6. Ranking Integration

### 6.1 Current formula (`retrieval_ranking.py:108`)

```python
final_score = (
    0.35 * win_rate
  + 0.25 * vec_score
  + 0.10 * sas
  + 0.10 * bg_boost
  + 0.20 * bitmask_score
)
```

### 6.2 New formula — one added term, renormalized

The existing 5 weights sum to 1.0 (`0.35+0.25+0.10+0.10+0.20`). Adding `w_sop` naively would make the max score `1.0 + w_sop`, letting SOP dominate. Instead, when SOP is active, **renormalize all weights to sum to 1.0** so SOP is a true bias, not an additive override:

```python
final_score = (
    w_wr * win_rate
  + w_vs * vec_score
  + w_sa * sas
  + w_bg * bg_boost
  + w_bm * bitmask_score
  + w_sop * sop_score          # ← NEW
)
```

Where:
- When no SOP active: `w_sop = 0`, other weights unchanged (sum to 1.0). Formula identical to today.
- When SOP active: `w_sop = config("sop.weight", 0.20)`, and all existing weights are scaled by `(1 - w_sop) / 1.0` so the total still sums to 1.0. E.g. `win_rate` becomes `0.35 * (1 - 0.20) = 0.28`.

```python
def get_effective_weights(active_sop: bool) -> dict[str, float]:
    base = get_ranking_weights()  # {win_rate: 0.35, vec_score: 0.25, ...}
    if not active_sop:
        base["sop"] = 0.0
        return base
    w_sop = _cfg("sop.weight", 0.20)
    scale = 1.0 - w_sop
    return {k: v * scale for k, v in base.items()} | {"sop": w_sop}
```

- `sop_score` = `1.0` if the candidate sentence's `collector_action` group matches the highest-priority **unfulfilled** goal's `collector_action`, `-1.0` if it matches an anti-goal, `0.5` for partial match, else `0.0`.
- **Calibration guidance:** `w_sop = 0.20` means SOP influences at most 20% of the final score — enough to break ties and bias toward goal-aligned scripts, not enough to override a clearly better non-SOP candidate. Tune via offline eval: run the recommendation engine over historical calls with and without SOP, measure repayment rate lift. If SOP-active calls show >5pp lift, `w_sop` is well-calibrated; if <1pp, lower it.

### 6.3 Per-candidate sop_score computation

```python
def compute_sop_score(candidate, active_sop, remaining_goals) -> float:
    if active_sop is None:
        return 0.0

    candidate_action = candidate.get("collector_action")

    # Anti-goal penalty: candidate's action is in the SOP's anti_goals list
    anti_goals = getattr(active_sop, "anti_goals", [])
    if candidate_action in anti_goals:
        return -1.0  # penalize actions that correlate with failure

    # Advisory SOP (no goals, only anti-goals): no positive boost
    if not remaining_goals:
        return 0.0

    # highest-priority unfulfilled goal
    top_goal = min(remaining_goals, key=lambda g: g.priority)  # priority 1 = highest

    if candidate_action == top_goal.collector_action:
        return 1.0

    # partial credit: candidate addresses any remaining goal (not just top)
    for goal in remaining_goals:
        if candidate_action == goal.collector_action:
            return 0.5

    return 0.0
```

This means:
- The top unfulfilled goal's action gets full SOP boost (`1.0`).
- Any other unfulfilled goal's action gets partial boost (`0.5`) — keeps options open, doesn't over-constrain.
- Fulfilled goals' actions get `0.0` — don't re-recommend what's already done.
- **Anti-goal actions get `-1.0`** — penalize actions that correlate with failure in this situation (e.g. `pressure` in a financial hardship SOP).
- **Advisory SOPs** (zero-success clusters, no goals): only apply anti-goal penalties, no positive boost. This lets the system say "avoid pressure here" even when it can't say "do X instead."
- When no SOP active, `w_sop = 0` → `sop_score` is irrelevant → formula is identical to today.

### 6.4 Concrete change to `retrieval_ranking.py`

```python
# In rank_sentences(), add parameters:
async def rank_sentences(
    pool, query_vec=None, db=None, query_bg=None,
    conversation_context="", context_missing=False,
    active_sop=None, remaining_goals=None,  # ← NEW
):
    ...
    weights = get_effective_weights(active_sop is not None)  # renormalized

    for s in pool:
        ...
        sop_score = compute_sop_score(s, active_sop, remaining_goals) if active_sop else 0.0
        s["sop_score"] = sop_score
        s["final_score"] = float(
            weights["win_rate"] * s.get("win_rate", 0)
          + weights["vec_score"] * s["vec_score"]
          + weights["sas"] * s.get("sas", 0)
          + weights["bg_boost"] * bg_boost
          + weights["bitmask_score"] * bitmask_score
          + weights["sop"] * sop_score
        )
```

Total change: ~15 lines in `retrieval_ranking.py`, ~30 lines in a new `f011_sop/sop_engine.py`.

---

## 7. Activation / Deactivation / Mid-Conversation Switch

```
Turn 1: customer says "我失业了" (I lost my job)
  state_extraction → facts: ["unemployment"]
  detect_sop → financial_hardship (severity 3)
  track_goals → completed: [], remaining: [empathy, assess, explain, affordability, agree]
  ranking → w_sop=0.20, empathy action gets sop_score=1.0
  → recommends an empathy script

Turn 2: collector expresses empathy, customer says "下个月找到新工作了"
  state_extraction → facts: ["unemployment", "expected_income"]
  detect_sop → financial_hardship (still active)
  track_goals → completed: [empathy], remaining: [assess, explain, affordability, agree]
  ranking → assess_situation action gets sop_score=1.0
  → recommends an information-gathering script

Turn 3: customer suddenly says "你们再逼我我就去法院告你们" (I'll sue you)
  state_extraction → emotions: ["anger", "threat"]
  detect_sop → emotional_escalation (severity 5) > financial_hardship (severity 3)
  → SWITCH to emotional_escalation
  track_goals → completed: [], remaining: [de_escalate, acknowledge, redirect, offer]
  ranking → de_escalate (empathy action) gets sop_score=1.0
  → recommends a de-escalation script

Turn 4: collector de-escalates, customer calms down, says "好吧那分期怎么办"
  state_extraction → facts: ["request_installment"], emotions: []
  detect_sop → installment_request (severity 2) < emotional_escalation (severity 5)
  BUT emotional_escalation goals: completed [de_escalate, acknowledge] ≥ min_goals 2
  → emotional_escalation COMPLETE → deactivate
  → re-detect → installment_request activates
  → seamless switch to installment SOP
```

**All switching is automatic.** No explicit state machine. The per-turn SOP update follows this **exact execution order**:

```python
def update_sop_state(
    sop_state: SOPState,
    extracted_facts: list[str],
    extracted_emotions: list[str],
    transcript: list[dict],
) -> SOPState:
    """
    Called once per turn, after state_extraction, before ranking.
    Exact order of operations:
      1. Track goals on the CURRENT active SOP (if any) against the transcript.
      2. Check completion of the current SOP. If complete, deactivate.
      3. Detect: run detect_sop on current facts/emotions. If a new SOP is detected
         (either because the old one was deactivated, or because a higher-severity
         SOP preempts the active one), switch to it.
      4. If the SOP changed in step 3, track goals on the NEW SOP (it starts fresh
         with completed=[] — goals are re-evaluated against the full transcript).
      5. Return the updated state for ranking.
    """
    # Step 1: track goals on current SOP
    if sop_state.active_sop is not None:
        completed, remaining = track_goals(sop_state.active_sop, transcript)
        sop_state.completed_goals = completed
        sop_state.remaining_goals = remaining

    # Step 2: check completion → deactivate
    if sop_state.active_sop is not None and is_sop_complete(sop_state.active_sop, sop_state.completed_goals):
        sop_state.active_sop = None
        sop_state.completed_goals = []
        sop_state.remaining_goals = []

    # Step 3: detect (may activate a new SOP or escalate to a higher-severity one)
    detected = detect_sop(extracted_facts, extracted_emotions, sop_state.active_sop)
    if detected is not sop_state.active_sop:
        sop_state.active_sop = detected
        # Step 4: new SOP → re-track goals from scratch against full transcript
        if detected is not None:
            sop_state.completed_goals, sop_state.remaining_goals = track_goals(detected, transcript)
            sop_state.turns_active = 0
        else:
            sop_state.completed_goals = []
            sop_state.remaining_goals = []

    if sop_state.active_sop is not None:
        sop_state.turns_active += 1

    return sop_state
```

**Key ordering decisions:**
- **Complete before detect:** if the current SOP's goals are met, it deactivates *before* detection runs. This lets detection find a new SOP for the same turn (e.g. hardship completes → installment request detected in the same turn).
- **Re-track on switch:** when a new SOP activates mid-conversation, goals are evaluated against the *full transcript so far*, not just future turns. A goal that was already achieved before the SOP activated (e.g. empathy was already expressed) is immediately marked complete.
- **Detect can escalate:** if a higher-severity SOP appears while a lower-severity one is still active (and not complete), `detect_sop` switches to the higher-severity one. The lower-severity SOP's goal progress is discarded.

---

## 8. Data Structures

### 8.1 SOP catalog file: `src/f011_sop/sop_catalog.yaml`

Contains all 8 SOPs from §3 in the YAML schema shown. Loaded once at server startup.

### 8.2 Per-turn SOP state (in session)

```python
@dataclass
class SOPState:
    active_sop: SOP | None
    completed_goals: list[str]
    remaining_goals: list[str]
    turns_active: int          # how many turns this SOP has been active
```

Stored in `SessionStore` alongside the existing conversation state. Persists across turns within a session. Cleared on session end.

### 8.3 Recommendation response additions

The `/api/v1/recommend` response gains optional SOP metadata (for UI/debugging, does not change the contract):

```json
{
  "recommendation": "...",
  "confidence": 0.87,
  "sop": {
    "active": true,
    "sop_id": "financial_hardship",
    "completed_goals": ["empathy"],
    "remaining_goals": ["assess_situation", "explain_options", "determine_affordability", "agree_next_action"],
    "top_goal": "assess_situation"
  }
}
```

---

## 9. Implementation Plan

### Files to create

| File | Purpose | Lines |
|---|---|---|
| `src/f011_sop/__init__.py` | Module init | 1 |
| `src/f011_sop/sop_catalog.yaml` | The 8 SOP definitions (§3) | ~250 |
| `src/f011_sop/sop_engine.py` | `detect_sop`, `track_goals`, `is_sop_complete`, `compute_sop_score` | ~120 |
| `src/f011_sop/goal_rules.py` | `GOAL_COMPLETION_RULES` — rule-based goal matchers | ~80 |
| `src/f011_sop/models.py` | `SOP`, `Goal`, `SOPState` dataclasses + YAML loader | ~60 |
| `src/tests/test_sop_detection.py` | Detection tests (trigger matching, severity precedence, mid-conversation switch) | ~100 |
| `src/tests/test_sop_goals.py` | Goal completion rule tests | ~80 |
| `src/f011_sop/mine_sops.py` | SOP mining pipeline (§11) | ~150 |
| `src/f011_sop/mining/clustering.py` | Situation clustering | ~100 |
| `src/f011_sop/mining/goal_mining.py` | Goal extraction from successful calls | ~80 |
| `src/f011_sop/mining/scoring.py` | Lift, priority, severity, completion scoring | ~80 |
| `src/f011_sop/mining/emit.py` | YAML catalog writer | ~50 |
| `src/tests/test_sop_mining.py` | Mining tests on synthetic calls | ~120 |

### Files to modify

| File | Change | Lines changed |
|---|---|---|
| `src/f006_retrieval_engine/retrieval_ranking.py` | Add `active_sop`, `remaining_goals` params; add `w_sop * sop_score` term | ~15 |
| `src/f009_api_server/server.py` | After state extraction, call `detect_sop` + `track_goals`; pass to `rank_sentences`; add SOP metadata to response | ~25 |
| `src/f009_api_server/session_store.py` | Add `SOPState` to session | ~5 |
| `config.md` | Add `sop.weight: 0.20`, `sop.completion_threshold` | ~5 |

### Execution order

1. Create `f011_sop/models.py` — dataclasses + YAML loader.
2. Create `f011_sop/sop_catalog.yaml` — the 8 SOPs from §3.
3. Create `f011_sop/goal_rules.py` — completion rules per goal ID.
4. Create `f011_sop/sop_engine.py` — `detect_sop`, `track_goals`, `is_sop_complete`, `compute_sop_score`.
5. Write `tests/test_sop_detection.py` + `tests/test_sop_goals.py` — verify detection, severity precedence, mid-conversation switch, goal completion, deactivation.
6. Modify `retrieval_ranking.py` — add `w_sop * sop_score` term.
7. Modify `server.py` — wire SOP layer into the `_run_turn` pipeline (after state extraction, before ranking).
8. Modify `session_store.py` — persist `SOPState`.
9. Add config to `config.md`.
10. End-to-end test: send a multi-turn conversation through `/api/v1/recommend`, verify SOP activates, biases ranking, completes, deactivates.

### Pipeline insertion point in `server.py`

```
existing: extract_state → merge_state → bitmask+embed → recommend → respond
new:      extract_state → merge_state → SOP_detect → SOP_track → bitmask+embed → recommend(+sop) → respond
```

The SOP layer inserts between state merge and ranking. It reads `merged_state.facts` and `merged_state.emotions` (output of state extraction) and the transcript (for goal completion). It does NOT call state extraction, does NOT modify state extraction, does NOT touch state extraction's prompt or model.

---

## 10. Config Additions (`config.md`)

```yaml
sop:
  weight: 0.20          # w_sop when SOP active; 0.0 when inactive. Existing weights renormalized to (1-w_sop).
  partial_credit: 0.5   # sop_score for non-top remaining goals
  anti_goal_penalty: 1.0  # sop_score for anti-goal actions (negative)
  completion_threshold: null  # per-SOP, uses sop.completion.min_goals if null
  enable_llm_goal_checker: false  # optional upgrade; default rule-based
```

---

## 11. SOP Mining — Automatically Building SOPs from Historical Call Data

The catalog in §3 is a hand-authored starting point. The system must also **mine SOPs automatically** from the existing call data, so that as more calls are collected, new SOPs are discovered and existing ones are refined without manual effort.

> **The complete, authoritative mining specification is in `SOP_MINING.md`.** This section provides a summary and integration points. All algorithm details, pseudocode, parameters, and the review workflow live in `SOP_MINING.md` to avoid duplication drift.

### 11.1 Data Inputs

| Source | File | What it provides |
|---|---|---|
| Annotated calls | `f003_reward_labeling/data/output_rewarded.py` | Per-call `turns_annotated` (customer turns with `facts`/`emotions`/`willingness`, collector turns with `action`), `reward` (1=repayment, 0=failure), `customer_info` |
| Taxonomy | `f000_keyword_discovery/data/state_keywords.json` | Canonical fact/emotion/action group names (validation only) |

### 11.2 Mining Pipeline Summary

The full pipeline is specified in `SOP_MINING.md` §4-§6. Summary:

```
output_rewarded.py
       │
       ▼
Step 1: build_signatures() → per-call fact/emotion sets + collector action sequences
       │
       ▼
Step 2: cluster_calls() → situation archetypes (Jaccard co-occurrence clustering + emotion-only pass)
       │
       ▼
Step 3: split_by_outcome() → success/failure per cluster
         is_sop_warranted() → two-condition gate (situation differs + action predictiveness)
       │
       ▼
Step 4: mine_goals() → candidate goals (actions in ≥40% of successful calls)
         ⚠ compliance guard: NEVER_GOAL_ACTIONS blocks pressure/legal_threat from being goals
         mine_anti_goals() → actions to avoid (correlate with failure)
       │
       ▼
Step 4c: mine_goal_themes() → sub-themes per goal (embed sentences → cluster → LLM label)
Step 4d: score_goal_humanity() → humane quality validation per goal (LLM judge on example sentences)
       │
       ▼
Step 5: compute_lift() → required vs optional
         compute_priority() → soft ordering (median first-appearance)
         compute_completion_threshold() → min_goals
         compute_severity() → urgency (inverse success rate + domain overrides)
         compute_confidence() → Wilson interval lower bound (small-N safety)
       │
       ▼
Step 5f: assess_sop_quality() → LLM quality review (10-dimension rubric) + adversarial review
       │
       ▼
Step 6: emit_sop_catalog() → sop_catalog_mined.yaml (with review_status, confidence, quality_assessment)
       │
       ▼
Human review (§7 of SOP_MINING.md) → approved SOPs loaded by online system
```

### 11.3 Key Safeguards (detailed in SOP_MINING.md)

| Safeguard | Where | What it prevents |
|---|---|---|
| `NEVER_GOAL_ACTIONS` | Step 4a | `pressure`/`legal_threat` mined as goals even if they correlate with repayment (coercive tactics) |
| Humane scoring | Step 4d | Formulaic/manipulative "empathy" sentences kept as required goals |
| Wilson confidence | Step 5e | Small-N SOPs auto-deploying with noisy lift scores |
| LLM quality review | Step 5f | SOPs with poor humanity/compliance/naturalness scores going live |
| LLM adversarial review | Step 5f | Undetected coercive failure modes in the SOP design |
| Review workflow | §7 | Any SOP (mined or auto_approved) influencing live recommendations without human vetting |

### 11.4 When Mining Runs

SOP mining is an **offline pipeline step**, not online. It runs:

1. **On demand** — `python src/f011_sop/mine_sops.py` (during development or when new data arrives).
2. **Scheduled** — as a new phase appended to `whole_pipeline.py`, after reward labeling (Phase 3). It depends on `output_rewarded.py` existing. Runs daily/weekly alongside the rest of the offline pipeline.

Mining does NOT run online. The online system loads both `sop_catalog.yaml` (hand-authored) and `sop_catalog_mined.yaml` (mined, filtered by `review_status`) at startup.

### 11.5 Mined vs. Hand-Authored Catalogs

Two catalog files:

| File | Source | Role |
|---|---|---|
| `sop_catalog.yaml` | Hand-authored (§3) | Domain-expert SOPs with compliance constraints, required rules, human judgment. Always loaded. |
| `sop_catalog_mined.yaml` | Auto-mined (`SOP_MINING.md`) | Data-driven SOPs with evidence, lift scores, confidence, quality assessment. Loaded only if `review_status` is `approved` or `auto_approved`. |

**Merge strategy:** at server startup, load both. Hand-authored overrides mined for the same `sop_id`. Mined SOPs with `review_status: draft` or `rejected` are **not loaded**. This gives you:
- Human compliance constraints that data can't infer (e.g. "do not threaten back").
- Data-driven discovery of new situations humans didn't anticipate.
- Evidence-backed refinement of existing SOPs (lift scores, completion thresholds).
- **No unreviewed SOP influences live recommendations.**

```python
def load_merged_catalog() -> list[SOP]:
    authored = load_yaml("sop_catalog.yaml")
    mined = load_yaml("sop_catalog_mined.yaml")
    by_id = {}
    # Only load mined SOPs that have been reviewed and approved
    for sop in mined:
        if sop.get("review_status") in ("approved", "auto_approved"):
            by_id[sop.sop_id] = sop
    # Authored SOPs always load (domain-expert vetted) and override mined
    for sop in authored:
        by_id[sop.sop_id] = sop
    return list(by_id.values())
```

**Review gate:** mined SOPs with `review_status: draft` or `rejected` are **not loaded** — they must pass both LLM quality assessment (`SOP_MINING.md` Step 5f) and human review (`SOP_MINING.md` §7) before influencing live recommendations. With the current small dataset (31 calls), all mined SOPs will be `draft` (confidence too low for auto-approval), so none go live until a human reviews them.

### 11.6 Continuous Refinement

As new calls are collected and reward-labeled, re-running mining will:
- **Discover new SOPs** — new fact clusters that didn't meet `min_cluster_size` before now qualify.
- **Refine existing SOPs** — lift scores, priorities, and completion thresholds update with more data.
- **Retire weak SOPs** — if a cluster's success rate converges to baseline (the `is_sop_warranted` gate fails), the SOP is dropped.
- **Detect goal drift** — if a previously-required goal's lift drops below 1.5, it becomes optional.
- **Re-run quality assessment** — LLM quality + adversarial review re-evaluated on each mining run; changes in scores trigger re-review.

The `evidence` and `confidence` blocks in each mined SOP make this transparent — you can see exactly how many calls support each SOP, how strong the evidence is, and whether it's trustworthy enough to auto-deploy.

### 11.7 Mining Module Files

> Full file structure in `SOP_MINING.md` §8.

| File | Purpose |
|---|---|
| `src/f011_sop/mine_sops.py` | Mining pipeline CLI + orchestration |
| `src/f011_sop/mining/signatures.py` | Call signatures (Step 1) |
| `src/f011_sop/mining/clustering.py` | Jaccard co-occurrence clustering + emotion clusters (Step 2) |
| `src/f011_sop/mining/outcome.py` | Outcome split + SOP-warranted gate (Step 3) |
| `src/f011_sop/mining/goal_mining.py` | Goal + anti-goal mining (Step 4) |
| `src/f011_sop/mining/compliance.py` | `NEVER_GOAL_ACTIONS`, `HUMANE_CRITERIA`, humane scoring (Steps 4a, 4d) |
| `src/f011_sop/mining/theme_mining.py` | Sentence clustering + LLM theme labeling (Step 4c) |
| `src/f011_sop/mining/scoring.py` | Lift, priority, severity, completion, Wilson confidence (Step 5) |
| `src/f011_sop/mining/quality_review.py` | LLM quality rubric + adversarial review (Step 5f) |
| `src/f011_sop/mining/emit.py` | YAML catalog writer (Step 6) |
| `src/f011_sop/review_sops.py` | Review CLI — list, approve, reject (§7) |
| `src/tests/test_sop_mining.py` | Mining tests |

---

## 12. Why This Satisfies Every Requirement

| Requirement | How it's met |
|---|---|
| SOP on how collectors respond in various situations | 8 hand-authored SOPs (§3) from the taxonomy + automatically mined SOPs from call data (`SOP_MINING.md`), each with situation-specific goals |
| Mine the SOP from the current recommendation system | §11: automatic mining pipeline extracts SOPs from `output_rewarded.py` — clusters calls by situation, mines goals from successful collectors, scores by lift, emits `sop_catalog_mined.yaml` with full evidence |
| Integrate with it (if SOP exists follow it) | `w_sop > 0` biases ranking toward SOP-goal-aligned scripts |
| If no SOP, use regular system | `w_sop = 0` → formula identical to today |
| SOP detected mid-way → switch to SOP | Detection runs every turn; activates immediately on trigger |
| Not restrictive / steps interchangeable | Goals are unordered; engine picks highest-priority unfulfilled goal per turn based on context |
| Feels like human conversation | No fixed sequence, no "go to step 3"; collector can address any goal the customer's words naturally lead to |
| state_extraction not involved in decisions | SOP layer is a downstream consumer of state_extraction output; goal completion uses transcript metadata, not state extraction; fully decoupled for BERT migration |

---

## 13. SOP Credibility & Cluster Sizing

### 13.1 Threshold Tiers

| Goal | Min Successes | Min Cluster Size | Why |
|---|---|---|---|
| Draft SOP (human review) | 2 with different action profiles | 3 | Lift can differentiate (not all ∞); themes can cluster |
| Auto-approved SOP (no human review) | 4 in ≤11 calls | 10 | Wilson LB ≥ 0.15 passes; lift is finite and > 1.0 |

The critical constraint isn't just the count — it's **variation in action profiles**. If all successes share the exact same actions, lift = ∞ for everything and no action can be differentiated as important vs incidental. You need successes where some collectors used empathy and some didn't, so lift can tell you empathy actually matters.

### 13.2 Wilson LB Constraint

With 4 successes in 10 calls, Wilson LB ≈ 0.168 (passes 0.15 gate). But if the cluster is larger (e.g. 4 successes in 14 calls), Wilson drops to 0.117 (fails) — the success rate must be high enough relative to the cluster size.

| Successes | Cluster size | Wilson LB | Passes? |
|---|---|---|---|
| 4 | 10 | 0.168 | Yes |
| 4 | 11 | 0.155 | Barely |
| 4 | 12 | 0.143 | No |
| 10 | 20 | 0.28 | Yes |
| 20 | 40 | 0.36 | Yes |

### 13.3 Credibility Spectrum

4 successes is the **floor**, not the standard. More successes → more credible SOP:

| Successes/cluster | Wilson LB (at 50% rate) | Credibility | Action |
|---|---|---|---|
| 4 | 0.17 | Fragile — "probably not luck" | Draft only |
| 10 | 0.28 | Decent signal | Acceptable for low-stakes SOPs |
| 20 | 0.36 | Pattern is real | **Credible SOP — auto-approve** |
| 30 | 0.41 | Pattern is robust | **High-confidence SOP** |
| 50 | 0.47 | Very strong | Overkill for most use cases |

**20–30 successes per cluster** is the sweet spot for credible SOPs. At that level:
- Wilson LB is well above the gate (0.36–0.41)
- Lift estimates are stable (±10% won't flip the ranking)
- Enough action profile variation to trust the differentiation
- One outlier success can't distort the SOP

### 13.4 Imbalanced Clusters

Clusters don't need to be balanced. Each stands on its own:

| Cluster | Successes | Wilson LB | Credibility | Action |
|---|---|---|---|---|
| Common situation | 100 | 0.42 | Very high | Auto-approve |
| Rare situation | 10 | 0.28 | Moderate | Draft — human review |

**Tiered approval by success count:**
- **≥30 successes** → auto-approve (no human review)
- **10–29 successes** → draft SOP (human reviews before deploying)
- **<10 successes** → don't generate SOP yet, accumulate more data

As more calls come in and a rare situation hits 30 successes, it promotes from draft to auto-approved.

### 13.5 Infinite Failure Pool

If the failure pool is effectively infinite (e.g. 100K+ total calls with low success rate), Wilson LB → 0 for any finite cluster because the success rate approaches 0. **You cannot use Wilson LB with an unbounded failure pool.**

Fix: **window the failures** — for each situation cluster, take only the failures that match the same situation (same cluster). Then Wilson LB is computed on S/(S+F) where both S and F are same-situation calls. Random failures from other contexts don't count.

If a cluster genuinely has zero same-situation failures (every call in that situation succeeds), lift = ∞ for all actions and you can't differentiate. That cluster produces a SOP with no actionable insight — "just do anything, it always works."

### 13.6 Scale Considerations

| Total successes | Credible SOPs (÷25) | Bottleneck |
|---|---|---|
| 1,000 | ~40 | None — manageable |
| 10,000 | ~400 | Too many SOPs to navigate |
| 100,000 | ~4,000 | Operationally unusable |

At scale, **statistical power is no longer the constraint** — every cluster has 25+ successes easily. The bottleneck becomes **operational complexity**.

Fix: **hierarchical SOPs.**

```
Tier 1: 10-20 macro-SOPs (broad situations, e.g. "fee dispute")
  └─ Tier 2: 5-15 micro-SOPs each (specific sub-situations)
       └─ Tier 3: statistical proof (25+ successes per leaf)
```

- Tier 1: human-facing, what agents actually follow
- Tier 2: drill-down for edge cases
- Tier 3: pure evidence, never shown unless audited

The limit is no longer data — it's **how many situations humans can meaningfully distinguish**, typically 50–200 regardless of data volume.
