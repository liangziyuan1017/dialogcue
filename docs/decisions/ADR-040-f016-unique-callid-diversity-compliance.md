---
REMOVED_FIELD_id: ADR-040
title: "F016 unique call_id + LLM diversity + compliance guardrails"
doc_kind: decision
feature_ids: [F016]
topics: [augmentation, call_id, llm, prompt, compliance, diversity]
status: accepted
created: 2026-07-10
updated: 2026-07-10
schema_version: 1
---

# F016 Unique call_id + LLM Diversity + Compliance Guardrails

## What

Three fixes to F016 sentence pool augmentation, found during end-to-end testing:

1. **call_id collision**: `generate_fake_call_id()` was called once with no collision check. With `--seed N`, the first `random` call is deterministic → same call_id every run → silently overwrites existing DB rows via `ON CONFLICT DO UPDATE`.
2. **Low diversity**: `temperature=0.7` produced templated, robotic sentences with formulaic openings ("您好，我是XX机构的...").
3. **Compliance violations**: Generated sentences exposed internal labels ("还款意愿不强"), quoted customer dismissively ("光说知道了过两天"), and referenced system internals ("挂上'有还款意愿'的标签").

## Why

- **Collision**: Plan §7 specified "Regenerate if script_id already in overlay or DB" but it was never implemented. The `--seed 42` test produced `9999104332181960013` which collided with a prior run, silently corrupting DB rows (changing `node_id` and `script_text` of existing augmented sentences).
- **Diversity**: The original prompt asked the LLM to "generate collector sentences" in isolation — no customer utterance to respond to, no conversational context. Result was templated greeting-style output.
- **Compliance**: Real collectors never say "您的还款意愿不强" to a customer's face, never quote the customer back dismissively, and never expose internal classification tags. These are regulatory and professionalism violations.

## Decision

### 1. `generate_unique_call_id()` with collision detection

Added to `random_profile.py`:

```python
def generate_unique_call_id(existing_script_ids: set[str], count: int, max_retries: int = 100) -> str:
```

Retries up to 100×, checking all turn indices (`{call_id}_t1`, `{call_id}_t2`, ...) against existing script_ids from overlay + DB. The caller (`augment_sentences.py`) loads existing `9999%` script_ids before generating.

### 2. Temperature 0.7 → 1.1

DeepSeek supports temperature up to 2.0. 1.1 gives strong diversity without losing coherence. The new "imagine → respond" prompt format provides enough structural grounding to keep output coherent at this temperature.

### 3. Prompt G — "imagine customer → respond" with guardrails

Redesigned `generate_prompts.py` to a conversational format:

- **Structure**: LLM first imagines what the customer would say (based on node states + profile), then generates a collector response to that utterance.
- **Compliance guardrails** (禁忌 section):
  - No quoting/paraphrasing customer's words to反驳
  - No internal labels/classification terms (还款意愿, 风险等级, 标签)
  - No system concept exposure (挂标签, 系统报警)
  - No judgmental statements — use guided questions instead
  - No "您好" opening — direct conversational接话
- **Natural language**: Permits 口语化停顿词 (嗯, 呃, 那个), adjusts tone by risk level
- **Risk descriptor**: `risk_level` int → Chinese descriptor (极低/较低/中等/较高/极高)

## Alternatives considered

- **Timestamp-based call_id**: Rejected — would break the 19-digit numeric format invariant (real call_ids are all numeric).
- **Temperature 0.9**: Tested but still somewhat templated. 1.1 was the sweet spot.
- **Temperature 1.3+**: Considered but risked incoherent output and JSON parse failures.
- **Prompt A (real-context)**: Used actual `conversation_context` utterances. Good realism but tied to existing threads — less novel diversity.
- **Prompt B (state-simulated)**: LLM imagines customer from state labels. Good diversity but responses didn't explicitly reference a customer utterance.
- **Prompt C (profile-grounded)**: Hardcoded customer utterances in prompt. Natural but not dynamic, and had JSON parse issues at high temp.
- **Prompt H/I**: Good results but exposed system internals ("让系统看到", "在系统里做个记录").

Prompt G was selected: best balance of diversity (from B's imagine-first approach), naturalness (from C's scenario grounding), and compliance (from explicit guardrails).

## Consequences

- `--seed` is now safe to use repeatedly — collision check guarantees unique call_ids.
- Generated sentences are conversational responses to imagined customer utterances, not standalone scripts.
- Compliance guardrails prevent regulatory violations in generated content.
- 78 tests pass (was 68; +7 for `generate_unique_call_id` and +3 for prompt guardrails).
