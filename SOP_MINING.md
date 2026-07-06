# SOP Mining — Complete Implementation Plan

> **Standalone offline tool.** Runs independently of the online recommendation server.
> Produces `sop_catalog_mined.yaml` which the online system loads at startup.
> No dependency on the online pipeline (`f006`, `f008`, `f009`), no dependency on `state_extraction`.
> Does share infrastructure modules with the rest of the system: `f007_infrastructure.embeddings` (bge-m3 for sentence clustering) and `f007_infrastructure.llm_client` (DeepSeek for theme labeling). These are reusable utilities, not online pipeline components.

---

## 1. Purpose

Automatically discover SOPs (Standard Operating Procedures) from historical call recordings. Each mined SOP answers: **"When a customer is in situation X, what goals should a collector achieve, and which goals actually drive successful outcomes?"**

The mining tool reads annotated call data that already exists in the system, applies statistical analysis to extract situation→goal→outcome patterns, and writes a YAML catalog that the online recommendation engine consumes as a ranking bias.

```
 ┌─────────────────────────────────┐
 │  SOP Mining Tool (standalone)   │
 │                                 │
 │  annotated calls + reward labels│
 │         (already exist)         │
 │              │                  │
 │              ▼                  │
 │  cluster → mine → score → emit  │
 │              │                  │
 │              ▼                  │
 │  sop_catalog_mined.yaml         │
 └─────────────────────────────────┘
                  │
                  │  (loaded at server startup, not at runtime)
                  ▼
 ┌─────────────────────────────────┐
 │  Online Recommendation Engine   │
 │  loads sop_catalog_mined.yaml   │
 │  + sop_catalog.yaml (authored)  │
 └─────────────────────────────────┘
```

---

## 2. Data Inputs

### 2.1 Primary input: annotated call data

**File:** `src/f003_reward_labeling/data/output_rewarded.py`

A Python file containing a `results` list. Each element is a call:

```python
{
    "call_id": "2317941550352385028",
    "cust_no": "0100252354",
    "call_date": "20260506",
    "coll_user_id": "SX17625",
    "reward": 1,               # 1 = repayment achieved, 0 = not achieved
    "customer_info": { ... },   # customer profile (age, debt, industry, etc.)
    "context": { ... },         # bitmask context fields
    "turns_annotated": [
        {
            "turn_index": 0,
            "role": "催收员",           # "催收员" = collector, "客户" = customer
            "text": "您好，请问是张女士吗？",
            "state": {
                "action": "greeting"    # collector turns: action field
            }
        },
        {
            "turn_index": 7,
            "role": "客户",
            "text": "我想问一下分期的事...",
            "state": {
                "facts": ["request_installment"],       # customer turns: facts list
                "emotions": ["disappointment"],          # customer turns: emotions list
                "willingness": "conditional"             # customer turns: willingness level
            }
        },
        ...
    ]
}
```

**Key fields used by mining:**

| Field | Where | Type | Mining use |
|---|---|---|---|
| `reward` | call-level | int (0/1) | Outcome label — splits calls into success/failure |
| `turns_annotated[*].role` | turn-level | str | Distinguish customer vs collector turns |
| `turns_annotated[*].state.action` | collector turns | str | Collector action performed (goal candidate) |
| `turns_annotated[*].state.facts` | customer turns | list[str] | Customer situation facts (SOP trigger candidates) |
| `turns_annotated[*].state.emotions` | customer turns | list[str] | Customer emotions (SOP trigger candidates) |
| `turns_annotated[*].state.willingness` | customer turns | str | Willingness level (situation modifier) |

**Observed values in current dataset (31 calls):**

- Collector actions (7): `closure`, `empathy`, `greeting`, `information`, `legal_threat`, `plan_proposal`, `pressure`
- Customer facts (53): `financial_hardship`, `unemployment`, `request_installment`, `multiple_debts`, `account_frozen`, `bankruptcy`, ...
- Emotions (23): `anger`, `threat`, `distress`, `frustration`, `pleading`, ...
- Willingness (5): `resistant`, `weak`, `conditional`, `negotiating`, `strong`
- Reward distribution: 6 success (19%), 25 failure (81%)

### 2.2 Secondary input: taxonomy (for validation)

**File:** `src/f000_keyword_discovery/data/state_keywords.json`

Used to validate that mined fact/emotion/action names match the canonical taxonomy. Not strictly required for mining, but catches typos and ensures the output uses names the online system recognizes.

---

## 3. Output

**File:** `src/f011_sop/sop_catalog_mined.yaml`

A YAML file containing a list of mined SOPs. Each SOP has triggers, goals, scoring data, and an evidence block.

```yaml
sops:
  - sop_id: "mined_financial_hardship"
    source: "mined"
    review_status: "draft"
    advisory: false
    severity: 4
    trigger_facts:
      - financial_hardship
      - unemployment
      - salary_delay
      - business_difficulty
    trigger_emotions:
      - distress
      - helplessness
    goals:
      - id: "goal_empathy"
        description: "Express empathy for the customer's situation"
        collector_action: "empathy"
        priority: 1
        lift: 2.33
        required: true
      - id: "goal_information"
        description: "了解客户具体困难原因; 解释欠款和息费明细; 核实客户还款能力"
        collector_action: "information"
        priority: 2
        lift: 1.50
        required: true
        sub_themes:
          - theme: "了解客户具体困难原因"
            example_sentences:
              - "您这边是具体遇到什么样的一个困难了吗？"
              - "这两天有点困难，是因为什么原因？工资没发还是其他原因？"
            sentence_count: 12
            call_count: 7
          - theme: "解释欠款和息费明细"
            example_sentences:
              - "您目前总欠款有61000多"
              - "循环利息是38块1毛六，违约金是12块6毛五"
            sentence_count: 9
            call_count: 5
          - theme: "核实客户还款能力"
            example_sentences:
              - "您现在能周转到多少的一个金额呢？"
              - "您这边的话是通道没有打开还是什么情况"
            sentence_count: 6
            call_count: 4
      - id: "goal_plan_proposal"
        description: "Propose a concrete repayment plan"
        collector_action: "plan_proposal"
        priority: 3
        lift: 1.80
        required: true
      - id: "goal_closure"
        description: "Close with agreed next action"
        collector_action: "closure"
        priority: 4
        lift: 1.20
        required: false
    anti_goals:
      - pressure    # this action correlates with failure in this situation
    required:
      - "Avoid pressure before empathy is delivered"
    completion:
      min_goals: 3
      total_goals: 4
    evidence:
      call_count: 12
      success_count: 4
      failure_count: 8
      success_rate: 0.333
      global_success_rate: 0.194
      lift_over_baseline: 1.72
      mined_at: "2026-07-06T14:30:00"
    quality_assessment:
      quality_review:
        scores:
          situation_fit: 4
          humanity: 5
          usefulness: 4
          conversational_naturalness: 5
          outcome_support: 3
          compliance_safety: 4
          goal_completeness: 4
          anti_goal_detection: 3
          evidence_quality: 2
          runtime_feasibility: 4
        overall_score: 4
        compliance_risk: "low"
        evidence_risk: "medium"
        strengths:
          - "Goals are unordered and allow natural conversation flow"
          - "Empathy goal has genuine, situation-specific example sentences"
        problems:
          - "Evidence quality low — only 12 calls, 4 successes"
        required_changes:
          - "Add 'avoid legal_threat as motivation' to required rules"
        approval: "revise"
      adversarial_review:
        attack_vectors:
          - scenario: "Collector follows empathy goal mechanically"
            how: "Says empathy phrase then immediately demands payment"
            severity: "medium"
        missing_anti_goals: []
        flagged_example_sentences: []
        overall_risk: "low"
      llm_approval: "revise"
      assessed_at: "2026-07-06T14:31:00"
```

---

## 4. Algorithm — 6 Steps

### Step 1: Build Per-Call Signatures

Extract the complete set of facts, emotions, and willingness levels from each call's customer turns. Also extract the ordered sequence of collector actions. This gives us two views per call: the **situation** (what the customer was going through) and the **approach** (what the collector did).

```python
from dataclasses import dataclass, field
from collections import Counter

@dataclass
class CallSignature:
    call_id: str
    reward: int
    facts: set[str] = field(default_factory=set)
    emotions: set[str] = field(default_factory=set)
    willingness: set[str] = field(default_factory=set)
    collector_actions: list[str] = field(default_factory=list)  # ordered, with repeats
    collector_actions_unique: set[str] = field(default_factory=set)


def build_signatures(calls: list[dict]) -> list[CallSignature]:
    signatures = []
    for call in calls:
        sig = CallSignature(
            call_id=call["call_id"],
            reward=call["reward"],
        )
        for turn in call["turns_annotated"]:
            state = turn.get("state") or {}
            role = turn.get("role", "")

            if role == "客户":
                sig.facts.update(state.get("facts", []))
                sig.emotions.update(state.get("emotions", []))
                if "willingness" in state:
                    sig.willingness.add(state["willingness"])

            elif role == "催收员":
                action = state.get("action")
                if action:
                    sig.collector_actions.append(action)
                    sig.collector_actions_unique.add(action)

        signatures.append(sig)
    return signatures
```

**Output:** one `CallSignature` per call.

---

### Step 2: Cluster Calls Into Situation Archetypes

Calls sharing similar customer situations belong to the same SOP. We cluster by fact/emotion co-occurrence.

#### 2a. Build fact co-occurrence matrix

```python
def build_cooccurrence(signatures: list[CallSignature]) -> dict[str, Counter]:
    """fact_a → {fact_b: number of calls where both appear}"""
    co = {}
    for sig in signatures:
        for f1 in sig.facts:
            if f1 not in co:
                co[f1] = Counter()
            for f2 in sig.facts:
                co[f1][f2] += 1
    return co
```

#### 2b. Identify anchor facts

Anchor facts are high-frequency facts that define situation archetypes. A fact is an anchor if it appears in at least `min_anchor_frequency` calls.

```python
def find_anchors(signatures: list[CallSignature], min_anchor_frequency: int) -> list[str]:
    freq = Counter()
    for sig in signatures:
        freq.update(sig.facts)
    return [f for f, count in freq.items() if count >= min_anchor_frequency]
```

#### 2c. Merge co-occurring anchors

If two anchor facts co-occur with Jaccard similarity above `merge_threshold`, they describe the same situation and should be merged into one anchor group. Jaccard is used instead of raw co-occurrence rate so that rare but perfectly correlated facts (e.g. two facts that only appear in 3 calls but always together) still merge.

```python
def merge_anchors(anchors: list[str], cooccurrence: dict, total_calls: int,
                  merge_threshold: float = 0.7) -> list[set[str]]:
    """
    Group anchors with Jaccard similarity > merge_threshold.
    Jaccard(A, B) = |A ∩ B| / |A ∪ B| = co_count / (freq_A + freq_B - co_count)
    Uses union-find for transitive merging.
    """
    parent = {a: a for a in anchors}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    for i, a1 in enumerate(anchors):
        freq_a1 = cooccurrence.get(a1, {}).get(a1, 0)  # diagonal = own frequency
        for a2 in anchors[i+1:]:
            co_count = cooccurrence.get(a1, {}).get(a2, 0)
            freq_a2 = cooccurrence.get(a2, {}).get(a2, 0)
            union_count = freq_a1 + freq_a2 - co_count  # |A ∪ B|
            if union_count > 0:
                jaccard = co_count / union_count
                if jaccard >= merge_threshold:
                    union(a1, a2)

    groups = {}
    for a in anchors:
        root = find(a)
        groups.setdefault(root, set()).add(a)
    return list(groups.values())
```

#### 2d. Assign calls to clusters

Each call is assigned to the cluster whose anchor facts it shares the most overlap with. A call can belong to multiple clusters (a customer can be in financial hardship AND have a billing dispute).

```python
@dataclass
class Cluster:
    cluster_id: str
    anchor_facts: set[str]
    member_call_ids: set[str]
    trigger_facts: set[str] = field(default_factory=set)
    trigger_emotions: set[str] = field(default_factory=set)


def assign_clusters(signatures: list[CallSignature], anchor_groups: list[set[str]],
                    min_cluster_size: int) -> list[Cluster]:
    clusters = []
    for i, group in enumerate(anchor_groups):
        members = set()
        for sig in signatures:
            if sig.facts & group:  # call contains any anchor fact in this group
                members.add(sig.call_id)

        if len(members) >= min_cluster_size:
            clusters.append(Cluster(
                cluster_id=f"cluster_{i}",
                anchor_facts=group,
                member_call_ids=members,
            ))
    return clusters
```

#### 2e. Expand trigger sets

For each cluster, collect all facts and emotions that appear in at least `trigger_frequency_threshold` fraction of member calls. These become the full trigger set (broader than just the anchors).

```python
def expand_triggers(cluster: Cluster, signatures: list[CallSignature],
                    trigger_frequency_threshold: float = 0.3):
    member_sigs = [s for s in signatures if s.call_id in cluster.member_call_ids]
    n = len(member_sigs)

    fact_counts = Counter()
    emotion_counts = Counter()
    for sig in member_sigs:
        fact_counts.update(sig.facts)
        emotion_counts.update(sig.emotions)

    cluster.trigger_facts = {f for f, c in fact_counts.items() if c / n >= trigger_frequency_threshold}
    cluster.trigger_emotions = {e for e, c in emotion_counts.items() if c / n >= trigger_frequency_threshold}
```

#### 2f. Emotion-only clusters

Some situations are defined by emotion, not fact (e.g. a customer who is angry/threatening but hasn't disclosed a specific financial fact). After fact-based clustering, find calls not captured by any fact cluster and group them by high-intensity emotions.

```python
def find_emotion_clusters(signatures: list[CallSignature], fact_clusters: list[Cluster],
                          min_cluster_size: int) -> list[Cluster]:
    EMOTION_ANCHORS = {"anger", "threat", "accusation", "exhaustion", "impatience"}
    captured = set()
    for c in fact_clusters:
        captured.update(c.member_call_ids)

    clusters = []
    for emo in EMOTION_ANCHORS:
        members = {s.call_id for s in signatures
                   if emo in s.emotions and s.call_id not in captured}
        if len(members) >= min_cluster_size:
            clusters.append(Cluster(
                cluster_id=f"emotion_{emo}",
                anchor_facts=set(),
                member_call_ids=members,
                trigger_facts=set(),
                trigger_emotions={emo},
            ))
    return clusters
```

---

### Step 3: Split Each Cluster by Outcome

```python
@dataclass
class ClusterSplit:
    cluster: Cluster
    success: list[CallSignature]
    failure: list[CallSignature]
    success_rate: float


def split_by_outcome(cluster: Cluster, signatures: list[CallSignature]) -> ClusterSplit:
    members = [s for s in signatures if s.call_id in cluster.member_call_ids]
    success = [s for s in members if s.reward == 1]
    failure = [s for s in members if s.reward == 0]
    total = len(members)
    rate = len(success) / total if total > 0 else 0.0
    return ClusterSplit(cluster, success, failure, rate)
```

#### Gate: is an SOP warranted?

Two conditions must both hold:

1. **Situation condition:** the cluster's success rate differs meaningfully from the global baseline. If collectors succeed at the same rate regardless of approach, the situation doesn't need special handling.
2. **Action predictiveness condition:** at least one mined goal has `lift > 1.0` OR at least one anti-goal exists. This ensures the SOP contains actionable guidance — a goal that actually correlates with success or an action to avoid. Without this, the gate would emit SOPs for clusters where the situation is hard but no collector action makes a difference (e.g. a hopeless situation where every approach fails equally).

```python
def is_sop_warranted(split: ClusterSplit, global_success_rate: float,
                     min_effect_size: float = 0.10, min_cluster_size: int = 3) -> bool:
    if len(split.success) + len(split.failure) < min_cluster_size:
        return False
    # Condition 1: situation differs from baseline
    situation_differs = abs(split.success_rate - global_success_rate) >= min_effect_size
    if not situation_differs:
        return False
    # Condition 2: at least one action is predictive (checked by caller after goal mining)
    # This is a stub — the full check happens in emit_sop_catalog after goals are mined
    return True


def has_predictive_goals(goals: list[MinedGoal], split: ClusterSplit,
                         anti_goals: list[str]) -> bool:
    """At least one goal has lift > 1.0, or at least one anti-goal exists."""
    if anti_goals:
        return True
    for goal in goals:
        if compute_lift(goal.action, split) > 1.0:
            return True
    return False
```

The `has_predictive_goals` check runs in `emit_sop_catalog` after goals and anti-goals are mined, and filters out SOPs where no action pattern is predictive.

**Note:** with the current dataset (31 calls, 19% global success rate), `min_cluster_size` must be small (3) and `min_effect_size` modest (0.10). These parameters should be tuned as the dataset grows.

---

### Step 4: Mine Goals from Successful Calls

Goals are collector actions that successful collectors performed. We identify them by comparing action presence in successful vs. unsuccessful calls within the cluster.

#### 4a. Compliance guard — actions that can never be goals

Some actions may correlate with repayment success but are coercive, non-compliant, or dehumanizing. The mining process must **never** learn these as goals, regardless of lift. This is a hard guard, not a soft penalty — it runs before goal mining.

```python
# Actions that are never mined as goals, even if lift > 1.5.
# These can still appear as anti-goals (penalized at runtime).
NEVER_GOAL_ACTIONS = {
    "pressure",       # time pressure / urgency — can extract payment but dehumanizes
    "legal_threat",   # legal consequences — acceptable as factual explanation, not as a goal to pursue
}

# Actions that can be goals only if empathy/information precedes them in the transcript.
# Checked at runtime by the goal completion rules, not blocked at mining time.
CONDITIONAL_GOAL_ACTIONS = {
    "closure": ["empathy", "information"],  # closure is fine, but only after rapport is built
}


def filter_compliance(actions: list[str]) -> list[str]:
    """Remove actions that must never be mined as goals."""
    return [a for a in actions if a not in NEVER_GOAL_ACTIONS]
```

**Why this matters:** if `pressure` has lift 2.0 (pressure strongly correlates with repayment), the statistical mining alone would make it a required goal. That would teach the system to recommend pressure tactics — effective but coercive. The compliance guard blocks this. `pressure` can still appear as an **anti-goal** (if it correlates with failure in a specific cluster), and it can still be recommended by the underlying decision tree when the SOP is inactive — but the SOP will never *promote* it as a goal to pursue.

#### 4b. Count action presence

```python
@dataclass
class ActionStats:
    action: str
    presence_in_success: float   # fraction of successful calls where this action appears
    presence_in_failure: float   # fraction of unsuccessful calls where this action appears
    count_in_success: int
    count_in_failure: int


def compute_action_stats(split: ClusterSplit) -> list[ActionStats]:
    n_success = len(split.success)
    n_failure = len(split.failure)

    success_counts = Counter()
    failure_counts = Counter()
    for sig in split.success:
        success_counts.update(sig.collector_actions_unique)
    for sig in split.failure:
        failure_counts.update(sig.collector_actions_unique)

    all_actions = set(success_counts.keys()) | set(failure_counts.keys())
    stats = []
    for action in all_actions:
        stats.append(ActionStats(
            action=action,
            presence_in_success=success_counts[action] / n_success if n_success else 0.0,
            presence_in_failure=failure_counts[action] / n_failure if n_failure else 0.0,
            count_in_success=success_counts[action],
            count_in_failure=failure_counts[action],
        ))
    return stats
```

#### 4b. Identify goals

A collector action becomes a **goal** if it appears in at least `min_goal_presence` fraction of successful calls. Actions that appear more in failures than successes become **anti-goals**.

```python
@dataclass
class MinedGoal:
    action: str
    stats: ActionStats


def mine_goals(action_stats: list[ActionStats],
               min_goal_presence: float = 0.4) -> list[MinedGoal]:
    goals = []
    for stat in action_stats:
        if stat.action in NEVER_GOAL_ACTIONS:
            continue  # compliance guard: never mine as goal
        if stat.presence_in_success >= min_goal_presence:
            goals.append(MinedGoal(action=stat.action, stats=stat))
    return goals


def mine_anti_goals(action_stats: list[ActionStats],
                    min_excess: float = 0.15) -> list[str]:
    """Actions that appear significantly more in failures than successes."""
    anti = []
    for stat in action_stats:
        if stat.presence_in_failure - stat.presence_in_success >= min_excess:
            anti.append(stat.action)
    return anti
```

**Edge case — no successful calls in cluster:** if `n_success == 0`, we cannot mine goals from success. In this case, the SOP is emitted with an empty goal list, a flag `advisory: true` and `evidence.insufficient_success_data: true`. The SOP is still useful for its anti-goals (what to avoid) and trigger detection. The online system treats advisory SOPs differently: it penalizes anti-goal actions (negative `sop_score`) but does not boost any action (no goals to pursue). See `SOP_IMPLEMENTATION.md` §6.3 for anti-goal handling.

---

### Step 4c: Goal Theme Mining — Discover What Each Goal Actually Does

The action-level goals from Step 4b are coarse — `goal_information` doesn't distinguish "explain the debt amount" from "verify a billing dispute" from "explain interest charges." All three are `action: information`.

This step drills into each goal by **grouping the actual collector sentences** from successful calls, clustering them by semantic similarity, and labeling each sub-theme. This is data-driven: the groups are determined by what collectors actually said, not invented.

#### 4c-1. Collect sentences per goal action

For each mined goal, gather every collector turn with that action from successful calls in the cluster:

```python
@dataclass
class GoalSentence:
    text: str
    call_id: str
    turn_index: int
    reward: int


def collect_goal_sentences(goal_action: str, split: ClusterSplit,
                           calls_by_id: dict[str, dict]) -> list[GoalSentence]:
    """All collector turns with this action from successful calls in the cluster."""
    sentences = []
    for sig in split.success:
        call = calls_by_id[sig.call_id]
        for turn in call["turns_annotated"]:
            state = turn.get("state") or {}
            if (turn.get("role") == "催收员"
                    and state.get("action") == goal_action
                    and turn.get("text", "").strip()):
                sentences.append(GoalSentence(
                    text=turn["text"],
                    call_id=sig.call_id,
                    turn_index=turn["turn_index"],
                    reward=sig.reward,
                ))
    return sentences
```

#### 4c-2. Embed sentences

Use the existing bge-m3 embedding infrastructure (`f007_infrastructure/embeddings.py`):

```python
from f007_infrastructure.embeddings import embed_texts

def embed_goal_sentences(sentences: list[GoalSentence]) -> list[list[float]]:
    texts = [s.text for s in sentences]
    return embed_texts(texts)  # batched, 1024-dim, via Ollama
```

#### 4c-3. Cluster sentences by semantic similarity

Hierarchical agglomerative clustering with cosine distance. Sentences that say similar things group together. Each group = a distinct sub-theme of the goal.

```python
import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

def cluster_sentences(vectors: list[list[float]], distance_threshold: float = 0.35) -> list[list[int]]:
    """
    Cluster sentence vectors by cosine similarity.
    distance_threshold: max cosine distance within a cluster (0.35 ≈ 65% similarity).
    Returns list of clusters, each a list of sentence indices.
    """
    if len(vectors) <= 1:
        return [list(range(len(vectors)))]

    mat = np.array(vectors, dtype=np.float32)
    # Normalize for cosine distance
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1
    mat = mat / norms
    # Cosine distance = 1 - cosine similarity
    sim = mat @ mat.T
    dist = 1.0 - sim
    np.clip(dist, 0, 2, out=dist)
    np.fill_diagonal(dist, 0)

    condensed = squareform(dist, checks=False)
    Z = linkage(condensed, method='average')
    labels = fcluster(Z, t=distance_threshold, criterion='distance')

    clusters = {}
    for idx, label in enumerate(labels):
        clusters.setdefault(label, []).append(idx)
    return list(clusters.values())
```

**Parameter:** `distance_threshold = 0.35` means sentences with ≥65% cosine similarity group together. Lower = more, tighter groups; higher = fewer, looser groups. Tunable via CLI.

#### 4c-4. Label each sub-cluster via LLM (grounded in actual sentences)

For each sub-cluster, pick representative sentences (those closest to the cluster centroid), send them to the LLM, and ask it to summarize what specific thing the collectors are doing. The LLM **labels** groups that the data defined — it does not invent themes.

```python
from f007_infrastructure.llm_client import call_deepseek_json

def label_theme(sentences: list[GoalSentence], cluster_indices: list[int],
                vectors: list[list[float]], goal_action: str) -> dict:
    """Label one sub-cluster with a concise theme description."""
    # Pick up to 8 representative sentences (closest to centroid)
    cluster_vecs = np.array([vectors[i] for i in cluster_indices])
    centroid = cluster_vecs.mean(axis=0)
    dists = [np.linalg.norm(cluster_vecs[j] - centroid) for j in range(len(cluster_indices))]
    rep_order = np.argsort(dists)[:8]
    rep_indices = [cluster_indices[j] for j in rep_order]
    examples = [sentences[i].text for i in rep_indices]

    prompt = f"""You are analyzing debt collection call transcripts.

A successful debt collector performed the action "{goal_action}" in the following sentences.
All of these sentences are from calls that resulted in successful repayment.

Sentences:
{chr(10).join(f'{i+1}. "{s}"' for i, s in enumerate(examples))}

What specific thing is the collector doing in these sentences? 
Summarize in one concise phrase (10-20 words, in Chinese).
Also identify which sentence numbers belong to this theme.

Output JSON:
{{"theme": "...", "sentence_indices": [{", ".join(str(i+1) for i in range(len(examples)))}]}}"""

    result = call_deepseek_json(prompt, temperature=0.1)
    return {
        "theme": result.get("theme", f"Perform {goal_action}"),
        "example_sentences": examples,
        "sentence_count": len(cluster_indices),
    }
```

#### 4c-5. Assemble sub-themes per goal

```python
@dataclass
class GoalTheme:
    theme: str                    # LLM-labeled description
    example_sentences: list[str]  # actual sentences from successful calls
    sentence_count: int           # how many sentences in this sub-cluster
    call_count: int               # how many distinct calls contributed


def mine_goal_themes(goal: MinedGoal, split: ClusterSplit,
                     calls_by_id: dict[str, dict],
                     distance_threshold: float = 0.35) -> list[GoalTheme]:
    """Full theme mining pipeline for one goal."""
    sentences = collect_goal_sentences(goal.action, split, calls_by_id)

    if len(sentences) < 3:
        # Too few sentences to cluster — single theme with the raw action
        return [GoalTheme(
            theme=GOAL_DESCRIPTIONS.get(goal.action, f"Perform {goal.action}"),
            example_sentences=[s.text for s in sentences],
            sentence_count=len(sentences),
            call_count=len(set(s.call_id for s in sentences)),
        )]

    vectors = embed_goal_sentences(sentences)
    cluster_indices_list = cluster_sentences(vectors, distance_threshold)

    themes = []
    for cluster_indices in cluster_indices_list:
        if len(cluster_indices) < 2:
            continue  # skip singleton clusters (noise)
        label = label_theme(sentences, cluster_indices, vectors, goal.action)
        call_ids = {sentences[i].call_id for i in cluster_indices}
        themes.append(GoalTheme(
            theme=label["theme"],
            example_sentences=label["example_sentences"],
            sentence_count=len(cluster_indices),
            call_count=len(call_ids),
        ))

    # Sort by frequency (most common theme first)
    themes.sort(key=lambda t: t.sentence_count, reverse=True)
    return themes
```

#### 4c-6. Compose the goal description from sub-themes

The goal's `description` field becomes a composite of its sub-themes:

```python
def compose_goal_description(themes: list[GoalTheme]) -> str:
    if not themes:
        return ""
    if len(themes) == 1:
        return themes[0].theme
    # "Explain debt amount and interest breakdown; verify billing accuracy"
    return "; ".join(t.theme for t in themes[:3])  # top 3 themes
```

#### Example output

For `goal_information` in the `billing_dispute` SOP, with 20+ successful calls:

```yaml
goals:
  - id: "goal_information"
    collector_action: "information"
    description: "核实账单余额并解释息费明细; 解释循环利息和违约金的计算; 引导客户查看掌上生活核实"
    priority: 2
    lift: 1.50
    required: true
    sub_themes:
      - theme: "核实账单余额并解释息费明细"
        example_sentences:
          - "您上期的余额是2789.27元"
          - "现的余额是2603.51元"
          - "余额不对您指的是全款吗"
        sentence_count: 14
        call_count: 8
      - theme: "解释循环利息和违约金的计算"
        example_sentences:
          - "循环利息是38块1毛六，违约金是12块6毛五"
          - "本次逾期产生的循环利息和违约金400多块钱"
          - "息费的话，本期这个息费产生也就40多块钱"
        sentence_count: 11
        call_count: 6
      - theme: "引导客户查看掌上生活核实"
        example_sentences:
          - "您可以打开掌上生活去查看一下"
          - "您可以翻一下记录去查看一下"
        sentence_count: 5
        call_count: 4
```

Now the goal is specific and data-driven: we know successful collectors in billing disputes provide three distinct kinds of information, backed by actual sentences and frequency counts.

#### Why this is data-driven, not LLM-invented

| Step | Who decides | What |
|---|---|---|
| Which sentences to group | Embedding similarity (bge-m3) | The data — sentences that say similar things cluster together |
| How many groups | Clustering algorithm + distance threshold | The data — determined by the natural gaps in the embedding space |
| What to call each group | LLM | Only labels the group — summarizes existing sentences into a phrase |
| Which sentences are examples | Centroid proximity | The data — most representative sentences |

The LLM never decides what the themes are — it only names groups that the embedding clustering already defined. If the LLM were removed, the groups would still exist (just unlabeled). This is fundamentally different from asking an LLM "what goals should a billing dispute SOP have?" which would be pure generation.

#### Fallback: no embeddings available

If Ollama is not running (embeddings fail), fall back to the char-ngram TF-IDF approach already in the system (`scoring_metrics.compute_sas_for_pool`), or skip theme mining and use the static `GOAL_DESCRIPTIONS` lookup. The mining tool should degrade gracefully:

```python
def mine_goal_themes(goal, split, calls_by_id, distance_threshold=0.35):
    sentences = collect_goal_sentences(goal.action, split, calls_by_id)
    if len(sentences) < 3:
        return [single_theme_fallback(goal, sentences)]

    try:
        vectors = embed_goal_sentences(sentences)
    except Exception:
        # Embeddings unavailable — fall back to static description
        return [GoalTheme(
            theme=GOAL_DESCRIPTIONS.get(goal.action, f"Perform {goal.action}"),
            example_sentences=[s.text for s in sentences[:5]],
            sentence_count=len(sentences),
            call_count=len(set(s.call_id for s in sentences)),
        )]

    # ... rest of clustering + labeling
```

---

### Step 4d: Humane Scoring — Validate Goal Quality

The action label `empathy` does not prove the sentence is actually empathetic. A collector saying "我知道您困难，但是您必须还款" is tagged `empathy` but is formulaic and immediately pivots to pressure. This step validates the *quality* of each goal's example sentences against humane criteria.

#### 4d-1. Humane criteria

Each goal action is evaluated against action-specific quality criteria:

```python
HUMANE_CRITERIA = {
    "empathy": {
        "requires": [
            "acknowledges the customer's specific situation",
            "does not immediately pivot to payment demand",
            "uses the customer's own words or situation details",
        ],
        "fails_if": [
            "empathy phrase followed immediately by '但是/不过' + demand",
            "generic empathy without referencing the customer's situation",
            "empathy used as a manipulation lead-in",
        ],
    },
    "information": {
        "requires": [
            "accurately states the customer's debt/charges",
            "explains rather than asserts",
            "invites verification (e.g. '您可以查看一下')",
        ],
        "fails_if": [
            "inflates amounts to intimidate",
            "withholds information to pressure",
        ],
    },
    "plan_proposal": {
        "requires": [
            "offers a concrete, specific plan",
            "explains the benefit to the customer",
            "presents alternatives when available",
        ],
        "fails_if": [
            "false scarcity ('only today') without basis",
            "misrepresents terms",
        ],
    },
    "closure": {
        "requires": [
            "confirms a specific next action with date/amount",
            "does not use threats as the closing motivation",
        ],
        "fails_if": [
            "closes with legal threat as motivation",
        ],
    },
}
```

#### 4d-2. LLM-based quality evaluation

For each goal, sample up to 10 example sentences and evaluate them against the humane criteria. This is one LLM call per goal (offline, not in the hot path).

```python
from f007_infrastructure.llm_client import call_deepseek_json

def score_goal_humanity(goal_action: str, example_sentences: list[str]) -> dict:
    """
    Evaluate whether sentences tagged with this action are genuinely humane
    or formulaic/manipulative. Returns a quality score and flagged sentences.
    """
    criteria = HUMANE_CRITERIA.get(goal_action)
    if not criteria:
        return {"quality_score": 1.0, "flagged_sentences": [], "note": "no criteria defined"}

    sample = example_sentences[:10]
    prompt = f"""You are evaluating debt collection call transcripts for humane quality.

The collector action is "{goal_action}".

Quality criteria:
Requires: {criteria["requires"]}
Fails if: {criteria["fails_if"]}

Sentences to evaluate:
{chr(10).join(f'{i+1}. "{s}"' for i, s in enumerate(sample))}

For each sentence, judge whether it genuinely meets the quality criteria or is formulaic/manipulative.
Output JSON:
{{
  "evaluations": [
    {{"index": 1, "humane": true, "reason": "..."}},
    ...
  ],
  "quality_score": 0.0-1.0,
  "flagged_indices": [list of sentence indices that fail]
}}"""

    result = call_deepseek_json(prompt, temperature=0.1)
    return {
        "quality_score": result.get("quality_score", 0.5),
        "flagged_sentences": [sample[i-1] for i in result.get("flagged_indices", [])],
        "evaluations": result.get("evaluations", []),
    }
```

#### 4d-3. Apply quality gate

Goals with `quality_score < 0.5` are marked `low_quality: true` and their `required` flag is downgraded to `false`. They remain in the SOP as optional goals but the online system will not strongly boost them. Goals with `quality_score < 0.2` are dropped entirely.

```python
def apply_quality_gate(goal_dict: dict, humanity_score: dict) -> dict:
    quality = humanity_score["quality_score"]
    goal_dict["quality_score"] = round(quality, 2)
    goal_dict["flagged_sentences"] = humanity_score["flagged_sentences"][:3]

    if quality < 0.2:
        return None  # drop goal entirely
    if quality < 0.5:
        goal_dict["required"] = False
        goal_dict["low_quality"] = True
    return goal_dict
```

This ensures that a goal where the "empathy" sentences are actually formulaic ("我知道您困难，但是...") gets downgraded, while genuine empathy ("您这边是遇到什么困难了吗？您可以说一下，我看看可不可以帮到您") is kept as required.

---

### Step 5: Score Goals

#### 5a. Lift — is this goal required or optional?

Lift measures how much the presence of an action increases the probability of success.

```python
def compute_lift(action: str, split: ClusterSplit) -> float:
    """
    lift = P(success | action present) / P(success | action absent)

    lift > 1  → action helps
    lift > 1.5 → action strongly helps → required goal
    lift < 1  → action hurts → anti-goal candidate
    """
    members = split.success + split.failure
    with_action = [s for s in members if action in s.collector_actions_unique]
    without_action = [s for s in members if action not in s.collector_actions_unique]

    if not with_action:
        return 0.0
    if not without_action:
        return float('inf')  # all successful calls had this action, none without it

    p_success_given = sum(1 for s in with_action if s.reward == 1) / len(with_action)
    p_success_without = sum(1 for s in without_action if s.reward == 1) / len(without_action)

    if p_success_without == 0:
        return float('inf') if p_success_given > 0 else 1.0
    return p_success_given / p_success_without
```

Classification:
- `lift > 1.5` → **required** (strongly correlates with success)
- `1.0 ≤ lift ≤ 1.5` → **optional** (present in successful calls but doesn't strongly drive success)
- `lift < 1.0` → candidate anti-goal (already caught in Step 4b)

#### 5b. Priority — soft ordering suggestion

Derived from the median first-appearance position of the action in successful call transcripts. Actions that tend to appear early get higher priority (priority 1 = highest). This is a **soft** suggestion only — goals remain unordered at runtime; priority just helps the online engine pick the "top unfulfilled goal" when multiple are outstanding.

```python
import statistics

def compute_priority(action: str, success_signatures: list[CallSignature]) -> int:
    first_positions = []
    for sig in success_signatures:
        if action in sig.collector_actions_unique:
            first_positions.append(sig.collector_actions.index(action))
    if not first_positions:
        return 99  # never appeared in successful calls
    return int(statistics.median(first_positions)) + 1  # +1 so position 0 → priority 1
```

#### 5c. Completion threshold — how many goals must be achieved?

Mined from the median number of distinct goals achieved in successful calls. This is the bar for "SOP is complete."

```python
def compute_completion_threshold(goal_actions: set[str],
                                  success_signatures: list[CallSignature]) -> int:
    if not success_signatures:
        return 1
    goals_achieved = []
    for sig in success_signatures:
        achieved = len(goal_actions & sig.collector_actions_unique)
        goals_achieved.append(achieved)
    median = statistics.median(goals_achieved)
    return max(1, int(median))  # at least 1 goal must be achieved
```

#### 5d. Severity — how urgent is this situation?

Data-driven: severity is inversely proportional to the cluster's success rate. Situations where collectors usually fail are high-severity — the SOP is most needed there.

```python
def compute_severity(split: ClusterSplit,
                     trigger_facts: set[str], trigger_emotions: set[str]) -> int:
    # Data-driven base
    if split.success_rate < 0.10:
        base = 5
    elif split.success_rate < 0.20:
        base = 4
    elif split.success_rate < 0.35:
        base = 3
    elif split.success_rate < 0.50:
        base = 2
    else:
        base = 1

    # Domain overrides: legal and emotional situations are always high severity
    LEGAL_FACTS = {"bankruptcy", "legal_procedure_pending", "legal_threat",
                   "account_frozen", "bank_account_frozen", "card_frozen"}
    HIGH_EMOTIONS = {"anger", "threat", "accusation"}

    if trigger_facts & LEGAL_FACTS:
        base = max(base, 5)
    if trigger_emotions & HIGH_EMOTIONS:
        base = max(base, 5)

    return base
```

#### 5e. Confidence score — how trustworthy is this SOP?

With small N (31 calls, 6 successes), lift scores are noisy. A goal with lift 2.0 based on 3 calls is far less trustworthy than lift 2.0 based on 30 calls. We compute a **Wilson score interval** lower bound as the confidence score — this gives a conservative estimate of the true success rate that accounts for sample size.

```python
import math

def wilson_lower_bound(successes: int, total: int, z: float = 1.96) -> float:
    """
    Wilson score interval lower bound (95% confidence).
    Conservative estimate of the true success rate.
    With 3/3 success → 0.63 (not 1.0). With 30/30 success → 0.88.
    """
    if total == 0:
        return 0.0
    p = successes / total
    denominator = 1 + z * z / total
    centre = p + z * z / (2 * total)
    spread = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return (centre - spread) / denominator


def compute_confidence(split: ClusterSplit, goals: list[MinedGoal]) -> dict:
    """
    Confidence in the SOP as a whole and per-goal.
    """
    n = len(split.success) + len(split.failure)
    n_success = len(split.success)

    # SOP-level confidence: Wilson lower bound of success rate
    sop_confidence = wilson_lower_bound(n_success, n)

    # Per-goal confidence: Wilson lower bound of lift
    # lift confidence = confidence that P(success|action) > P(success|no action)
    goal_confidence = {}
    for goal in goals:
        members = split.success + split.failure
        with_action = [s for s in members if goal.action in s.collector_actions_unique]
        without_action = [s for s in members if goal.action not in s.collector_actions_unique]
        n_with = len(with_action)
        n_without = len(without_action)
        s_with = sum(1 for s in with_action if s.reward == 1)
        s_without = sum(1 for s in without_action if s.reward == 1)
        # Confidence that the action helps = Wilson LB of (success rate with action)
        # minus Wilson UB of (success rate without action). Positive = confident.
        lb_with = wilson_lower_bound(s_with, n_with)
        lb_without = wilson_lower_bound(s_without, n_without)
        goal_confidence[goal.action] = round(lb_with - lb_without, 3)

    return {
        "sop_confidence": round(sop_confidence, 3),
        "goal_confidence": goal_confidence,
        "sample_size": n,
        "success_sample_size": n_success,
    }
```

**Confidence gates for auto-deployment:**

```python
# SOPs above these thresholds are auto-deployed (review_status: auto_approved).
# Below, they are marked as draft and require human review.
MIN_SOP_CONFIDENCE = 0.15      # Wilson LB of success rate
MIN_GOAL_CONFIDENCE = 0.10     # positive lift confidence for at least one goal
MIN_SAMPLE_SIZE = 10           # minimum calls in cluster


def determine_review_status(confidence: dict, n: int) -> str:
    if n < MIN_SAMPLE_SIZE:
        return "draft"  # too few calls — always require review
    if confidence["sop_confidence"] < MIN_SOP_CONFIDENCE:
        return "draft"
    if max(confidence["goal_confidence"].values(), default=0) < MIN_GOAL_CONFIDENCE:
        return "draft"
    return "auto_approved"
```

With the current dataset (31 calls, 6 successes, global rate 19%):
- A cluster of 12 calls with 4 successes → Wilson LB = 0.12 → `draft` (below 0.15)
- A cluster of 20 calls with 8 successes → Wilson LB = 0.19 → potentially `auto_approved` (if goal confidence also passes)

This means **with the current small dataset, all mined SOPs will be `draft`** — they require human review before going live. As the dataset grows past 100+ calls, well-supported SOPs will auto-graduate.

---

### Step 5f: SOP-Level Quality Assessment (LLM Judge)

Steps 4d (humane scoring) and 5e (confidence) evaluate individual goals and statistical reliability. This step evaluates the **SOP as a whole** against a 10-dimension quality rubric. The LLM acts as a **judge/assistant** — it identifies concrete failure modes and quotes evidence, but **final approval is always human-gated**.

#### 5f-1. Quality rubric (10 dimensions, scored 1–5)

| Dimension | Question | What to check |
|---|---|---|
| Situation Fit | Does the SOP match the customer's actual situation? | trigger_facts/emotions align with the cluster's real customer turns |
| Humanity | Does it preserve dignity, avoid shame, acknowledge hardship? | No condescending language, no shame-based pressure, acknowledges customer's situation |
| Usefulness | Are goals concrete enough for a collector to act on? | Each goal has ≥1 sub_theme with specific example sentences |
| Conversational Naturalness | Does it guide without forcing a rigid script? | Goals are unordered, no required sequencing, allows customer-led detours |
| Outcome Support | Are goals backed by evidence from successful calls? | Each goal has lift > 1.0 and appears in successful call examples |
| Compliance Safety | Avoids threats, false legal claims, harassment, coercion? | No `pressure`/`legal_threat` as goals, no misleading promises, no false scarcity |
| Goal Completeness | Covers understand, explain, offer, close? | At least one empathy/information goal + one plan_proposal goal + one closure goal |
| Anti-Goal Detection | Explicitly identifies harmful tactics to avoid? | anti_goals list is non-empty and matches known coercive patterns |
| Evidence Quality | Enough calls, enough successes, stable lift? | confidence.sop_confidence ≥ 0.10, sample_size ≥ 5, representative examples |
| Runtime Feasibility | Can the system detect activation and completion reliably? | trigger_facts are in the taxonomy, goal actions map to extractable collector actions |

#### 5f-2. LLM judge — quality review pass

The LLM receives three inputs: the customer situation cluster, the candidate SOP, and supporting call examples. It outputs structured JSON with scores, problems, and required changes.

```python
from f007_infrastructure.llm_client import call_deepseek_json

def llm_quality_review(sop: dict, split: ClusterSplit, calls_by_id: dict) -> dict:
    """
    LLM judge: evaluate the SOP against the 10-dimension rubric.
    Outputs structured scores + concrete failure modes + approval recommendation.
    The LLM is a judge/assistant — final approval is human-gated.
    """
    # Build inputs
    customer_examples = _sample_customer_turns(split, calls_by_id, n=5)
    success_examples = _sample_collector_turns(split.success, calls_by_id, n=8)
    failure_examples = _sample_collector_turns(split.failure, calls_by_id, n=5)

    prompt = f"""You are reviewing a debt collection SOP for quality and compliance safety.

## Customer Situation Cluster
Facts: {sop["trigger_facts"]}
Emotions: {sop["trigger_emotions"]}
Example customer turns:
{chr(10).join(f'- "{t}"' for t in customer_examples)}

## Candidate SOP
{sop_to_yaml(sop)}

## Supporting Call Examples
Successful collector turns (from calls that achieved repayment):
{chr(10).join(f'- "{t}"' for t in success_examples)}

Failed collector turns (from calls that did not achieve repayment):
{chr(10).join(f'- "{t}"' for t in failure_examples)}

## Quality Rubric (score each 1–5)
1. Situation Fit: Does the SOP match the customer's actual situation?
2. Humanity: Does it preserve dignity, avoid shame, acknowledge hardship, reduce escalation?
3. Usefulness: Are goals concrete enough for a collector to act on?
4. Conversational Naturalness: Does it guide without forcing a rigid script?
5. Outcome Support: Are goals backed by evidence from successful calls?
6. Compliance Safety: Avoids threats, false legal claims, harassment, coercion, misleading promises?
7. Goal Completeness: Covers what the collector should understand, explain, offer, and close?
8. Anti-Goal Detection: Explicitly identifies harmful tactics to avoid?
9. Evidence Quality: Enough calls, enough successes, stable lift, representative examples?
10. Runtime Feasibility: Can the system detect activation and goal completion reliably?

## Instructions
- Do NOT ask "is this SOP good?" — instead identify concrete failure modes.
- Quote specific evidence from the examples to justify each score.
- For any score ≤ 2, list a concrete problem and required change.
- Compliance Safety score ≤ 2 means automatic "reject" recommendation.

Output JSON:
{{
  "scores": {{
    "situation_fit": 1-5,
    "humanity": 1-5,
    "usefulness": 1-5,
    "conversational_naturalness": 1-5,
    "outcome_support": 1-5,
    "compliance_safety": 1-5,
    "goal_completeness": 1-5,
    "anti_goal_detection": 1-5,
    "evidence_quality": 1-5,
    "runtime_feasibility": 1-5
  }},
  "overall_score": 1-5,
  "compliance_risk": "low | medium | high",
  "evidence_risk": "low | medium | high",
  "strengths": ["..."],
  "problems": ["..."],
  "required_changes": ["..."],
  "approval": "approve | revise | reject"
}}"""

    return call_deepseek_json(prompt, temperature=0.1)


def _sample_customer_turns(split: ClusterSplit, calls_by_id: dict, n: int = 5) -> list[str]:
    turns = []
    for sig in split.success[:3] + split.failure[:3]:
        call = calls_by_id.get(sig.call_id, {})
        for t in call.get("turns_annotated", []):
            if t.get("role") == "客户" and t.get("text", "").strip():
                turns.append(t["text"])
    return turns[:n]


def _sample_collector_turns(signatures: list, calls_by_id: dict, n: int = 8) -> list[str]:
    turns = []
    for sig in signatures[:5]:
        call = calls_by_id.get(sig.call_id, {})
        for t in call.get("turns_annotated", []):
            if t.get("role") == "催收员" and t.get("text", "").strip():
                turns.append(t["text"])
    return turns[:n]
```

#### 5f-3. LLM judge — adversarial review pass

A second LLM pass that actively tries to find how the SOP could produce dehumanizing behavior. This catches failure modes the quality review might miss.

```python
def llm_adversarial_review(sop: dict, split: ClusterSplit, calls_by_id: dict) -> dict:
    """
    Adversarial review: how could this SOP produce coercive or dehumanizing behavior?
    """
    success_examples = _sample_collector_turns(split.success, calls_by_id, n=8)

    prompt = f"""You are an adversarial reviewer for a debt collection SOP.

## SOP
{sop_to_yaml(sop)}

## Example collector turns from successful calls
{chr(10).join(f'- "{t}"' for t in success_examples)}

## Your task
Find concrete ways this SOP could produce coercive, dehumanizing, or non-compliant behavior.

Consider:
1. Could a collector follow the SOP's goals but still pressure/shame the customer?
2. Are any example sentences coercive even though they're tagged as empathy/information?
3. Could the goals be satisfied mechanically without genuine engagement?
4. Does the SOP miss any situation where the customer is vulnerable?
5. Could the anti_goals list be incomplete — are there coercive patterns not flagged?

Output JSON:
{{
  "attack_vectors": [
    {{"scenario": "...", "how": "...", "severity": "low|medium|high"}}
  ],
  "missing_anti_goals": ["..."],
  "flagged_example_sentences": ["..."],
  "overall_risk": "low | medium | high"
}}"""

    return call_deepseek_json(prompt, temperature=0.3)  # slightly higher temp for creativity
```

#### 5f-4. Combine quality + adversarial → final LLM assessment

```python
def assess_sop_quality(sop: dict, split: ClusterSplit, calls_by_id: dict) -> dict:
    """
    Full LLM quality assessment: rubric review + adversarial review.
    The LLM recommends approve/revise/reject, but final authority is human.
    """
    quality = llm_quality_review(sop, split, calls_by_id)
    adversarial = llm_adversarial_review(sop, split, calls_by_id)

    # Override: compliance safety ≤ 2 or high adversarial risk → force reject
    if quality["scores"]["compliance_safety"] <= 2 or adversarial["overall_risk"] == "high":
        quality["approval"] = "reject"

    return {
        "quality_review": quality,
        "adversarial_review": adversarial,
        "llm_approval": quality["approval"],  # recommendation, not final
        "assessed_at": datetime.now(timezone.utc).isoformat(),
    }
```

#### 5f-5. How LLM assessment interacts with review_status

The LLM assessment is **advisory** — it informs but does not decide:

| LLM `approval` | Confidence gate result | `review_status` set to | Human review needed? |
|---|---|---|---|
| `approve` | passes confidence gates | `auto_approved` | No (but flagged for periodic re-review) |
| `approve` | fails confidence gates | `draft` | Yes |
| `revise` | any | `draft` | Yes (with LLM's `required_changes` shown to reviewer) |
| `reject` | any | `draft` | Yes (with LLM's `problems` shown; reviewer likely rejects) |

**The LLM never sets `approved`** — only a human can. The LLM can recommend `auto_approved` (when it says `approve` AND confidence passes), but even then the SOP is flagged for periodic re-review. A human can always override any LLM decision.

---

### Step 6: Emit SOP Catalog

Assemble all mined data into the YAML structure and write to disk.

```python
from datetime import datetime, timezone
import yaml

def emit_sop_catalog(splits: list[ClusterSplit], global_success_rate: float,
                     output_path: str, calls_by_id: dict[str, dict],
                     enable_theme_mining: bool = True):
    sops = []
    for split in splits:
        if not is_sop_warranted(split, global_success_rate):
            continue

        action_stats = compute_action_stats(split)
        goals = mine_goals(action_stats)
        anti_goals = mine_anti_goals(action_stats)
        goal_actions = {g.action for g in goals}

        # Secondary gate: at least one action must be predictive
        if not has_predictive_goals(goals, split, anti_goals):
            continue  # no actionable guidance — skip this SOP

        goal_dicts = []
        for g in goals:
            lift = compute_lift(g.action, split)

            # Step 4c: mine sub-themes from actual sentences
            if enable_theme_mining and split.success:
                themes = mine_goal_themes(g, split, calls_by_id)
                description = compose_goal_description(themes)
                sub_themes = [
                    {
                        "theme": t.theme,
                        "example_sentences": t.example_sentences[:5],
                        "sentence_count": t.sentence_count,
                        "call_count": t.call_count,
                    }
                    for t in themes
                ]
            else:
                description = GOAL_DESCRIPTIONS.get(g.action, f"Perform {g.action}")
                sub_themes = []

            goal_dicts.append({
                "id": f"goal_{g.action}",
                "description": description,
                "collector_action": g.action,
                "priority": compute_priority(g.action, split.success),
                "lift": round(lift, 2),
                "required": lift > 1.5,
                "sub_themes": sub_themes,
            })

        # Step 4d: humane scoring on each goal's example sentences
        for gd in goal_dicts:
            example_sents = []
            for st in gd.get("sub_themes", []):
                example_sents.extend(st.get("example_sentences", []))
            if example_sents:
                humanity = score_goal_humanity(gd["collector_action"], example_sents)
                gd = apply_quality_gate(gd, humanity)
            if gd is None:
                continue
            scored_goal_dicts.append(gd)
        goal_dicts = scored_goal_dicts

        # Step 5e: confidence scoring
        confidence = compute_confidence(split, goals)
        review_status = determine_review_status(confidence, confidence["sample_size"])

        # Step 5f: LLM quality assessment (rubric + adversarial)
        if enable_quality_review:
            quality_assessment = assess_sop_quality(sop, split, calls_by_id)
            # LLM can downgrade auto_approved to draft
            if review_status == "auto_approved" and quality_assessment["llm_approval"] != "approve":
                review_status = "draft"
        else:
            quality_assessment = None

        sop = {
            "sop_id": make_sop_id(split.cluster),
            "source": "mined",
            "review_status": review_status,   # draft | auto_approved | approved | rejected
            "advisory": len(split.success) == 0,  # no goals to pursue, only anti-goals to avoid
            "severity": compute_severity(split, split.cluster.trigger_facts,
                                         split.cluster.trigger_emotions),
            "trigger_facts": sorted(split.cluster.trigger_facts),
            "trigger_emotions": sorted(split.cluster.trigger_emotions),
            "goals": goal_dicts,
            "anti_goals": anti_goals,
            "required": [f"Avoid {a} before empathy is delivered" for a in anti_goals],
            "completion": {
                "min_goals": compute_completion_threshold(goal_actions, split.success),
                "total_goals": len(goals),
            },
            "confidence": confidence,
            "quality_assessment": quality_assessment,  # LLM judge results (advisory)
            "evidence": {
                "call_count": len(split.success) + len(split.failure),
                "success_count": len(split.success),
                "failure_count": len(split.failure),
                "success_rate": round(split.success_rate, 3),
                "global_success_rate": round(global_success_rate, 3),
                "lift_over_baseline": round(
                    split.success_rate / global_success_rate if global_success_rate > 0 else 0, 2
                ),
                "insufficient_success_data": len(split.success) == 0,
                "mined_at": datetime.now(timezone.utc).isoformat(),
            },
        }
        sops.append(sop)

    catalog = {"sops": sops}
    with open(output_path, "w") as f:
        yaml.dump(catalog, f, allow_unicode=True, sort_keys=False)
    return sops


GOAL_DESCRIPTIONS = {
    "empathy": "Express empathy for the customer's situation",
    "information": "Gather and provide relevant information",
    "plan_proposal": "Propose a concrete repayment plan or solution",
    "closure": "Close with an agreed next action",
    "pressure": "Apply time pressure to encourage payment",
    "greeting": "Greet the customer and establish rapport",
    "legal_threat": "Explain legal consequences factually",
}


def make_sop_id(cluster: Cluster) -> str:
    if cluster.anchor_facts:
        primary = sorted(cluster.anchor_facts)[0]
    elif cluster.trigger_emotions:
        primary = sorted(cluster.trigger_emotions)[0]
    else:
        primary = "unknown"
    return f"mined_{primary}"
```

---

## 5. Full Pipeline — Orchestration

```python
def mine_sops(
    input_path: str = "src/f003_reward_labeling/data/output_rewarded.py",
    output_path: str = "src/f011_sop/sop_catalog_mined.yaml",
    min_anchor_frequency: int = 3,
    merge_threshold: float = 0.7,
    min_cluster_size: int = 3,
    trigger_frequency_threshold: float = 0.3,
    min_effect_size: float = 0.10,
    min_goal_presence: float = 0.4,
    anti_goal_min_excess: float = 0.15,
) -> list[dict]:
    """
    Full SOP mining pipeline. Reads annotated calls, writes mined SOP catalog.
    Returns the list of mined SOPs for inspection.
    """
    # Load data
    calls = load_calls(input_path)
    signatures = build_signatures(calls)

    # Step 1: (done above in build_signatures)

    # Step 2: Cluster
    cooccurrence = build_cooccurrence(signatures)
    anchors = find_anchors(signatures, min_anchor_frequency)
    anchor_groups = merge_anchors(anchors, cooccurrence, len(calls), merge_threshold)
    fact_clusters = assign_clusters(signatures, anchor_groups, min_cluster_size)
    for c in fact_clusters:
        expand_triggers(c, signatures, trigger_frequency_threshold)
    emotion_clusters = find_emotion_clusters(signatures, fact_clusters, min_cluster_size)
    all_clusters = fact_clusters + emotion_clusters

    # Step 3: Split by outcome
    global_success_rate = sum(s.reward for s in signatures) / len(signatures)
    splits = [split_by_outcome(c, signatures) for c in all_clusters]

    # Steps 4-6: Mine, score, emit
    sops = emit_sop_catalog(splits, global_success_rate, output_path)

    print(f"Mined {len(sops)} SOPs from {len(calls)} calls")
    print(f"Global success rate: {global_success_rate:.1%}")
    for sop in sops:
        ev = sop["evidence"]
        print(f"  {sop['sop_id']}: severity={sop['severity']}, "
              f"calls={ev['call_count']}, success_rate={ev['success_rate']:.1%}, "
              f"goals={len(sop['goals'])}")
    return sops


def load_calls(path: str) -> list[dict]:
    """Load the Python data file and return the results list."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("data_module", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.results
```

---

## 6. CLI Interface

```bash
python src/f011_sop/mine_sops.py [OPTIONS]

Options:
  --input PATH          Input annotated calls file
                        (default: src/f003_reward_labeling/data/output_rewarded.py)
  --output PATH         Output YAML catalog path
                        (default: src/f011_sop/sop_catalog_mined.yaml)
  --min-anchor-freq N   Minimum call count for a fact to be an anchor (default: 3)
  --merge-threshold F   Co-occurrence threshold for merging anchors (default: 0.7)
  --min-cluster-size N  Minimum calls to form a cluster (default: 3)
  --trigger-freq F      Minimum fraction of cluster calls for a trigger (default: 0.3)
  --min-effect F        Minimum success rate difference from baseline to warrant SOP (default: 0.10)
  --min-goal-presence F Minimum fraction of successful calls for a goal (default: 0.4)
  --no-theme-mining     Disable sub-theme mining (use static goal descriptions only)
  --no-quality-review   Disable LLM quality assessment (skip Step 5f)
  --cluster-threshold F Cosine distance threshold for sentence clustering (default: 0.35)
  --dry-run             Mine and print summary, don't write file
  --verbose             Print detailed per-cluster, per-goal statistics
```

### Example output

```
$ python src/f011_sop/mine_sops.py

Loading 31 annotated calls...
Global success rate: 19.4%

Clustering...
  Found 8 anchor facts, merged into 5 anchor groups
  5 fact clusters + 1 emotion cluster = 6 total clusters

Mining SOPs...
  Cluster financial_hardship: 12 calls, 33.3% success → SOP warranted (lift 1.72)
    Goals: empathy (lift 2.33, required), information (lift 1.50, required),
           plan_proposal (lift 1.80, required), closure (lift 1.20, optional)
    Anti-goals: pressure
  Cluster account_frozen: 5 calls, 0.0% success → SOP warranted (lift 0.00)
    Goals: [insufficient success data]
    Anti-goals: pressure
  Cluster request_installment: 8 calls, 25.0% success → SOP warranted (lift 1.29)
    Goals: information (lift 1.50, required), plan_proposal (lift 1.80, required),
           empathy (lift 1.20, optional)
  ...

Wrote 5 SOPs to src/f011_sop/sop_catalog_mined.yaml
```

---

## 7. Configuration

All parameters with defaults, tunable via CLI or `config.md`:

| Parameter | Default | Purpose |
|---|---|---|
| `min_anchor_frequency` | 3 | Min calls for a fact to be an anchor. Increase as dataset grows. |
| `merge_threshold` | 0.7 | Co-occurrence fraction for merging anchors into one situation. |
| `min_cluster_size` | 3 | Min calls to form a cluster. Lower = more SOPs but less reliable. |
| `trigger_frequency_threshold` | 0.3 | Min fraction of cluster calls for a fact/emotion to be a trigger. |
| `min_effect_size` | 0.10 | Min |cluster_success_rate - global_success_rate| to warrant an SOP. |
| `min_goal_presence` | 0.4 | Min fraction of successful calls for an action to be a goal. |
| `anti_goal_min_excess` | 0.15 | Min (failure_presence - success_presence) for an anti-goal. |
| `min_sop_confidence` | 0.15 | Wilson LB threshold for auto-approval. Below → draft. |
| `min_goal_confidence` | 0.10 | Min goal lift confidence for auto-approval. |
| `min_sample_size` | 10 | Min calls in cluster for auto-approval. Below → draft. |

**Scaling notes:** with 31 calls, parameters are loose (min_cluster_size=3). As the dataset grows to 100+ calls, raise to `min_cluster_size=5`, `min_anchor_frequency=5`. At 1000+ calls, `min_cluster_size=10`, `min_effect_size=0.15`.

---

## 7. Review Workflow

Mined SOPs are **not trusted by default**. Each SOP has a `review_status` field that controls whether the online system loads it.

### 7.1 Review status lifecycle

```
                            ┌──────────────────────────────────────────┐
                            │  LLM Quality Assessment (Step 5f)        │
                            │  • 10-dimension rubric scoring           │
                            │  • adversarial review                    │
                            │  • recommends approve/revise/reject      │
                            └──────────────┬───────────────────────────┘
                                           │
  draft  ──(human review + LLM advice)──→  approved  ──(loaded by online system)
    │                                         │
    │                                         └── rejected  (not loaded)
    │
    └── auto_approved  (LLM says approve + confidence passes + compliance safe)
                              │
                              └── (loaded by online system, flagged for periodic re-review)
```

**The LLM is a judge/assistant, not the final authority.** It scores, identifies problems, and recommends — but only a human can set `review_status: approved`. The LLM can set `auto_approved` (when it says `approve` AND confidence passes AND compliance safety ≥ 3), but even then the SOP is flagged for periodic re-review and a human can override at any time.

| Status | How it gets this status | Loaded online? |
|---|---|---|
| `draft` | Low confidence, LLM says `revise`/`reject`, failed quality gate, or small sample | No |
| `auto_approved` | LLM says `approve` + confidence passes + compliance safety ≥ 3 + ≥10 calls | Yes (flagged for re-review) |
| `approved` | Human reviewer approved a `draft` SOP (with LLM assessment shown as advice) | Yes |
| `rejected` | Human reviewer rejected a `draft` or `auto_approved` SOP | No |

### 7.2 Review rubric

When a human reviews a `draft` SOP, the LLM quality assessment (Step 5f) is shown alongside the SOP as **advisory input**. The human reviewer evaluates against the same 10 dimensions the LLM scored, plus checks the LLM's identified problems and required changes. Each criterion is pass/fail for the human reviewer:

```yaml
review_rubric:
  # ── Dimensions scored by LLM judge (Step 5f), shown to human reviewer ──
  - id: situation_fit
    llm_dimension: situation_fit
    question: "Does the SOP match the customer's actual situation/facts/emotions?"
    check: "Review trigger_facts and trigger_emotions against domain knowledge and example customer turns"

  - id: humanity
    llm_dimension: humanity
    question: "Does it preserve dignity, avoid shame, acknowledge hardship, reduce escalation?"
    check: "Review all goal example_sentences. Flag condescending, dismissive, or shame-based language."

  - id: usefulness
    llm_dimension: usefulness
    question: "Are goals concrete enough for a collector to act on?"
    check: "Each goal should have ≥1 sub_theme with concrete example sentences"

  - id: conversational_naturalness
    llm_dimension: conversational_naturalness
    question: "Does it guide without forcing a rigid script?"
    check: "Goals are unordered, no required sequencing, allows customer-led detours"

  - id: outcome_support
    llm_dimension: outcome_support
    question: "Are goals backed by evidence from successful calls?"
    check: "Each goal has lift > 1.0 and appears in successful call examples"

  - id: compliance_safety
    llm_dimension: compliance_safety
    question: "Avoids threats, false legal claims, harassment, coercion, misleading promises?"
    check: "No pressure/legal_threat as goals, no misleading promises, no false scarcity. LLM adversarial review attack_vectors reviewed."

  - id: goal_completeness
    llm_dimension: goal_completeness
    question: "Covers what the collector should understand, explain, offer, and close?"
    check: "At least one empathy/information goal + one plan_proposal goal + one closure goal"

  - id: anti_goal_detection
    llm_dimension: anti_goal_detection
    question: "Explicitly identifies harmful tactics to avoid?"
    check: "anti_goals list is non-empty, matches known coercive patterns, and incorporates LLM adversarial missing_anti_goals"

  - id: evidence_quality
    llm_dimension: evidence_quality
    question: "Enough calls, enough successes, stable lift, representative examples?"
    check: "confidence.sop_confidence ≥ 0.10, sample_size ≥ 5, representative examples"

  - id: runtime_feasibility
    llm_dimension: runtime_feasibility
    question: "Can the system detect activation and goal completion reliably?"
    check: "trigger_facts are in the taxonomy, goal actions map to extractable collector actions"

  # ── Human-only checks (not LLM-scored) ──
  - id: llm_problems_addressed
    question: "Have the LLM judge's identified problems and required_changes been addressed?"
    check: "Review quality_assessment.quality_review.problems and required_changes. Either fix the SOP or document why the problem is acceptable."

  - id: adversarial_risks_addressed
    question: "Have the adversarial review's attack vectors been addressed?"
    check: "Review quality_assessment.adversarial_review.attack_vectors. Add missing anti_goals if flagged."
```

### 7.3 Review CLI

```bash
# List all draft SOPs
python src/f011_sop/review_sops.py --status draft

# Review a specific SOP (prints full details + LLM quality assessment + rubric)
python src/f011_sop/review_sops.py --sop-id mined_financial_hardship

# The review output shows:
# - SOP details (triggers, goals, anti_goals, evidence)
# - LLM quality scores (10 dimensions, 1-5 each)
# - LLM identified problems and required_changes
# - LLM adversarial review (attack vectors, missing anti-goals, flagged sentences)
# - LLM approval recommendation (approve/revise/reject)
# - Human review rubric (10 dimensions + 2 human-only checks)
# - Confidence scores

# Approve (overrides any LLM recommendation)
python src/f011_sop/review_sops.py --sop-id mined_financial_hardship --approve

# Reject with reason
python src/f011_sop/review_sops.py --sop-id mined_financial_hardship --reject --reason "compliance safety score 2, adversarial review flagged missing anti-goal for pressure"

# Re-run LLM quality assessment on an existing SOP (after manual edits)
python src/f011_sop/review_sops.py --sop-id mined_financial_hardship --reassess
```

Approval/rejection updates the `review_status` field in `sop_catalog_mined.yaml` and records the reviewer and timestamp:

```yaml
review_status: approved
reviewed_by: "analyst@example.com"
reviewed_at: "2026-07-06T15:00:00"
review_notes: "adjusted severity from 3 to 4, added 'avoid legal_threat as motivation' to required"
```

### 7.4 Periodic re-review

`auto_approved` SOPs are re-mined on each pipeline run. If re-mining produces different goals, triggers, or confidence for the same `sop_id`, the new version is emitted as `draft` and the old `auto_approved` version remains active until the new one is reviewed. This prevents automatic drift while allowing continuous improvement.

---

## 8. File Structure

```
src/f011_sop/
├── __init__.py
├── mine_sops.py              # CLI entrypoint + pipeline orchestration (§5)
├── sop_catalog.yaml          # Hand-authored catalog (domain expert, compliance rules)
├── sop_catalog_mined.yaml    # Mined catalog (output of this tool)
├── mining/
│   ├── __init__.py
│   ├── signatures.py         # CallSignature, build_signatures (Step 1)
│   ├── clustering.py         # co-occurrence, anchors, merge, assign, emotion clusters (Step 2)
│   ├── outcome.py            # split_by_outcome, is_sop_warranted (Step 3)
│   ├── goal_mining.py        # compute_action_stats, mine_goals, mine_anti_goals (Step 4)
│   ├── theme_mining.py       # collect_goal_sentences, cluster_sentences, label_theme, mine_goal_themes (Step 4c)
│   ├── scoring.py            # compute_lift, compute_priority, compute_completion_threshold, compute_severity, compute_confidence (Step 5)
│   ├── compliance.py         # NEVER_GOAL_ACTIONS, HUMANE_CRITERIA, score_goal_humanity, apply_quality_gate (Steps 4a, 4d)
│   ├── quality_review.py     # llm_quality_review, llm_adversarial_review, assess_sop_quality (Step 5f)
│   └── emit.py               # emit_sop_catalog, make_sop_id, GOAL_DESCRIPTIONS (Step 6)
├── review_sops.py            # Review CLI — list, approve, reject draft SOPs (§7.3)
└── tests/
    └── test_mining.py        # Unit + integration tests
```

---

## 9. Testing

### 9.1 Unit tests

Each step tested independently with synthetic data.

```python
# tests/test_mining.py

class TestSignatures:
    def test_build_signatures_extracts_facts(self):
        calls = [{
            "call_id": "c1", "reward": 1,
            "turns_annotated": [
                {"role": "客户", "text": "...", "state": {"facts": ["unemployment"], "emotions": ["distress"]}},
                {"role": "催收员", "text": "...", "state": {"action": "empathy"}},
            ]
        }]
        sigs = build_signatures(calls)
        assert sigs[0].facts == {"unemployment"}
        assert sigs[0].emotions == {"distress"}
        assert sigs[0].collector_actions == ["empathy"]
        assert sigs[0].reward == 1

    def test_empty_state_handled(self):
        calls = [{"call_id": "c1", "reward": 0, "turns_annotated": [
            {"role": "客户", "text": "..."}  # no state
        ]}]
        sigs = build_signatures(calls)
        assert sigs[0].facts == set()


class TestClustering:
    def test_co_occurring_anchors_merged(self):
        # If financial_hardship and unemployment co-occur >70%, they merge
        ...

    def test_min_cluster_size_filters_small_clusters(self):
        ...

    def test_emotion_cluster_captures_uncaptured_calls(self):
        ...


class TestOutcomeSplit:
    def test_sop_not_warranted_when_success_equals_baseline(self):
        split = ClusterSplit(..., success_rate=0.19)
        assert not is_sop_warranted(split, global_success_rate=0.19, min_effect_size=0.10)

    def test_sop_warranted_when_success_above_baseline(self):
        split = ClusterSplit(..., success_rate=0.50)
        assert is_sop_warranted(split, global_success_rate=0.19, min_effect_size=0.10)


class TestGoalMining:
    def test_goal_mined_when_present_in_success(self):
        stats = [ActionStats("empathy", presence_in_success=0.8, presence_in_failure=0.2, 4, 2)]
        goals = mine_goals(stats, min_goal_presence=0.4)
        assert len(goals) == 1 and goals[0].action == "empathy"

    def test_anti_goal_mined_when_more_in_failure(self):
        stats = [ActionStats("pressure", presence_in_success=0.2, presence_in_failure=0.8, 1, 8)]
        anti = mine_anti_goals(stats, min_excess=0.15)
        assert "pressure" in anti


class TestScoring:
    def test_lift_high_when_action_correlates_with_success(self):
        # 4 calls with empathy: 3 success. 4 calls without: 1 success.
        # lift = 0.75 / 0.25 = 3.0
        ...

    def test_priority_1_for_earliest_action(self):
        ...

    def test_severity_5_for_legal_triggers(self):
        split = ClusterSplit(..., success_rate=0.5)
        assert compute_severity(split, {"bankruptcy"}, set()) == 5
```

### 9.2 Integration test — run on real data

```python
def test_mine_sops_on_real_data():
    """Run the full pipeline on the actual annotated calls and verify output."""
    sops = mine_sops(
        input_path="src/f003_reward_labeling/data/output_rewarded.py",
        output_path="/tmp/test_sop_catalog_mined.yaml",
    )
    assert len(sops) >= 1
    for sop in sops:
        assert sop["source"] == "mined"
        assert sop["severity"] in range(1, 6)
        assert sop["evidence"]["call_count"] >= 3
        assert "mined_at" in sop["evidence"]
```

### 9.3 Run tests

```bash
cd src && python -m pytest f011_sop/tests/test_mining.py -v
```

---

## 10. Integration with Online System

The mining tool is **offline only**. The online system consumes its output at startup:

```python
# In the online server startup (server.py lifespan):
def load_sop_catalog():
    authored = load_yaml("src/f011_sop/sop_catalog.yaml")       # hand-authored (always loaded)
    mined = load_yaml("src/f011_sop/sop_catalog_mined.yaml")    # mined (filtered by review_status)

    by_id = {}
    # Only load mined SOPs that have been approved or auto_approved
    for sop in mined.get("sops", []):
        if sop.get("review_status") in ("approved", "auto_approved"):
            by_id[sop["sop_id"]] = sop
    # Authored SOPs always load (domain-expert vetted) and override mined
    for sop in authored.get("sops", []):
        by_id[sop["sop_id"]] = sop

    return list(by_id.values())
```

**Precedence:** hand-authored SOPs override mined SOPs with the same `sop_id`. This lets domain experts add compliance constraints ("do not threaten back") that data alone cannot infer, while mined SOPs fill in data-driven discovery.

**Review gate:** mined SOPs with `review_status: draft` or `rejected` are **not loaded**. They must pass both LLM quality assessment (Step 5f) and human review (§7) before influencing live recommendations.

**No runtime dependency:** the online server never calls the mining tool or the LLM judge. It only reads the YAML file. Re-running mining and restarting the server picks up new/updated SOPs.

---

## 11. When to Run

| Trigger | Command |
|---|---|
| Initial setup | `python src/f011_sop/mine_sops.py` |
| New call data added (after reward labeling) | `python src/f011_sop/mine_sops.py` |
| Scheduled (weekly) | Add as a phase in `whole_pipeline.py` after reward labeling |
| Parameter tuning | `python src/f011_sop/mine_sops.py --min-cluster-size 5 --dry-run` |

The mining tool depends only on `output_rewarded.py` existing. It does not depend on the decision tree, scoring, embeddings, or any online component. It can be run at any time after reward labeling is complete.

---

## 12. Limitations & Future Improvements

| Limitation | Mitigation | Future |
|---|---|---|
| Small dataset (31 calls) → loose parameters, noisy clusters | Wilson confidence score gates auto-deployment; all current SOPs are `draft` | As dataset grows, tighten parameters + lower confidence thresholds |
| No successful calls in a cluster → empty goals | `advisory: true` flag; anti-goal penalties at runtime; LLM adversarial review | Use transfer learning from similar clusters |
| Binary reward only (repayment yes/no) | Sufficient for goal mining | Add partial reward (amount recovered / total debt) |
| Goals are per-action, not per-action-quality | Step 4d humane scoring validates sentence quality; Step 5f LLM judge scores humanity 1-5 | Add dedicated collector-action quality classifier (BERT) |
| Clustering is fact co-occurrence only | Simple, interpretable, works for current data | Try embedding-based clustering on conversation content |
| LLM judge could miss coercive patterns | Adversarial review pass actively probes for failure modes; human is final authority | Train a dedicated compliance classifier |
| LLM judge adds 2 LLM calls per SOP (offline) | Acceptable — offline only, not in hot path | Batch multiple SOPs into one LLM call |
| No temporal dynamics — doesn't model conversation evolution | SOPs are intentionally unordered (by design) | Could mine transition patterns for priority refinement |
