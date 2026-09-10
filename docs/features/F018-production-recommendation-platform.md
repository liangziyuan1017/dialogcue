---
REMOVED_FIELD_id: F018
name: Production Recommendation Platform
status: planned
owner: agent
related_features: [F000, F005, F006, F007, F008, F009, F014, F015, F017]
topics: [ingestion, safety, evaluation, observability, versioning, feedback, adaptability]
doc_kind: feature
created: 2026-07-31
updated: 2026-07-31
decisions: []
---

# F018: Production Recommendation Platform

> **Status**: kickoff | **Owner**: agent | **Priority**: P0
>
> **Goal**: Make the debt-dialogue system easy to operate, robust under dependency
> failure, adaptable across corpus/model/policy versions, and safe enough to
> recommend or abstain in real time.

## Why

F017 makes ingestion and serving bounded, but the system is still a collection
of pipeline scripts and a recommendation endpoint. A production operator needs
one resumable ingest workflow, reproducible versions, durable failure handling,
policy-aware ranking, measurable recommendation quality, and feedback that can
improve future versions without silently changing live behavior.

## What

F018 is a staged platform layer around the existing F000-F017 pipeline:

1. **Ingest control plane**: one validated, idempotent, resumable job interface
   with manifests, checkpoints, progress, and dead-letter records.
2. **Versioned knowledge**: corpus, schema, taxonomy, prompt, model, embedding,
   ranking, and policy versions attached to every artifact and recommendation.
3. **Safety and abstention**: policy checks before ranking, explicit unsafe/no-fit
   outcomes, deterministic safe fallback behavior, and auditable decisions.
4. **Evaluation harness**: versioned offline cases, quality/safety/calibration/
   latency metrics, slice analysis, and regression gates.
5. **Runtime resilience**: dependency timeouts, circuit breakers, bounded
   concurrency, caches, structured traces, health/readiness signals, and SLOs.
6. **Feedback and adaptation**: capture shown/accepted/edited/rejected scripts,
   collector overrides, customer outcomes, drift signals, and controlled version
   promotion/rollback.
7. **Operator experience**: CLI/API status, validation previews, replay controls,
   recommendation traces, and tenant/campaign configuration.

## Product principles

- **Recommend or abstain**: never force a low-confidence or policy-invalid script.
- **Every REMOVED_FIELD_result is explainable**: expose source, score components, policy checks,
  versions, and fallback reasons.
- **Immutable inputs, replaceable versions**: new knowledge is promoted as a
  version; it does not silently rewrite historical evidence.
- **Fail closed for safety, fail soft for availability**: unsafe output is blocked;
  model outages fall back to deterministic policy-safe behavior.
- **Tenant and domain boundaries are explicit**: no accidental cross-corpus,
  cross-policy, or cross-customer retrieval.

## Acceptance criteria

### P0: must ship before production pilot

- [ ] One `ingest` command/API accepts a corpus, validates it, fingerprints it,
  creates an idempotent job, and reports status.
- [ ] Ingestion is resumable at record/stage boundaries; failures are replayable
  from a dead-letter queue without reprocessing successful records.
- [ ] Every corpus, artifact, taxonomy, prompt, model, ranking config, and policy
  has an immutable version manifest.
- [ ] Recommendation requests carry tenant/campaign/version context and cannot
  retrieve from another tenant or unapproved version.
- [ ] Policy checks execute before final ranking and can block or require human
  review; the API supports explicit abstention.
- [ ] Every recommendation response has a trace ID, decision ID, versions,
  candidate count, score components, policy REMOVED_FIELD_result, and fallback reasons.
- [ ] A deterministic safe fallback is returned when extraction, embedding, or DB
  dependencies fail, unless policy requires abstention.
- [ ] A versioned evaluation set measures top-1/top-k quality, policy violations,
  abstention quality, calibration, latency, and important data slices.
- [ ] CI blocks promotion when critical safety or regression thresholds fail.
- [ ] PII is redacted from logs and prompts where possible; retention, deletion,
  and access-control behavior is tested.

### P1: must ship before broad rollout

- [ ] Collector feedback and downstream outcomes are stored as immutable events.
- [ ] Taxonomy/model/policy versions support shadow evaluation, promotion,
  rollback, and tenant/campaign scoping.
- [ ] Drift reports cover taxonomy coverage, unknown labels, outcome shifts,
  latency, fallback rates, and policy-block rates.
- [ ] Runtime SLO dashboards expose p50/p95/p99 latency, error rate, dependency
  health, queue depth, and recommendation/abstention rates.
- [ ] Operators can preview, pause, resume, replay, cancel, and inspect ingest
  jobs without reading source code.

## Dependencies

- F017 for JSONL, bounded memory, DB-backed lookup, batching, and provenance.
- F009/F014 for the external recommendation/API boundary.
- Existing config, logging, retry, async DB, and embedding infrastructure.

## Out of scope for the first implementation slice

- Automatic online model training or unreviewed policy changes.
- Guaranteed causal attribution of repayment to a recommendation.
- The 100k-record RSS benchmark explicitly skipped by the F017 request.
- Replacing PostgreSQL, pgvector, or the current extraction/ranking models.

## Design gate

**Proposed architecture**: add a platform layer with four explicit contracts:
`IngestRecord`, `KnowledgeVersion`, `PolicyAndRanker`, and `RecommendationTrace`.
Persist job/event/version state in PostgreSQL, keep pipeline artifacts in JSONL,
and make the existing recommendation engine consume an approved version context.
Use deterministic adapters around model calls so failure, timeout, and fallback
behavior can be tested without live providers.

**Meta-aesthetics check**: coordinate transformation. The design creates stable
control-plane contracts around the existing pipeline instead of adding more
stage-specific flags and ad hoc scripts.

**Discussion record (2026-07-31)**:

- Human goal: an easy-to-use, robust, adaptable system that ingests debt
  collection dialogs and makes the best real-time collector recommendation.
- Agent assessment: F017 is necessary infrastructure but is insufficient without
  ingestion control, safety policy, evaluation, versioning, resilience, feedback,
  observability, and privacy controls.
- Proposed first slice: implement P0 contracts and a fixture-backed vertical
  path before broad UI or automatic adaptation.
- Open design question for Human sign-off: approve the four-contract boundary and
  the P0/P1 sequencing in `F018-implementation-plan.md`.

## Related documents

- [F017 scalability hardening](F017-corpus-scalability-hardening.md)
- [F009 API server](F009-api-server.md)
- [F006 retrieval ranking](F006-retrieval-ranking-engine.md)
- [F012 runtime robustness](F012-runtime-robustness-hardening.md)

## Implementation plan

→ `docs/features/F018-implementation-plan.md`
