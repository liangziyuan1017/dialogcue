# F018: Production Recommendation Platform — Implementation Plan

**Feature:** F018 — `docs/features/F018-production-recommendation-platform.md`
**Goal:** Make ingestion, recommendation safety, evaluation, and operations explicit, versioned, resumable, and testable around F017.
**Architecture:** Add a small platform control plane in PostgreSQL and deterministic service contracts around the existing pipeline. Keep model providers replaceable and keep live recommendation fail-soft for availability but fail-closed for safety.
**Tech Stack:** Python, FastAPI, PostgreSQL, asyncpg, JSONL, pytest

## Acceptance criteria

- Versioned ingest manifest and idempotent job creation
- Record/stage checkpoints with dead-letter replay
- Immutable corpus/knowledge/policy/model/ranking versions
- Pre-ranking policy checks and explicit abstention
- Recommendation trace with versions, scores, policy result, and fallbacks
- Deterministic safe fallback for provider failures
- Offline evaluation harness with quality, safety, calibration, latency, and slice metrics
- Feedback/outcome event capture and controlled promotion/rollback contracts
- PII-safe logging and tenant/version isolation

## Phase 1: Contracts and persistence

### Task 1: Define version and trace contracts

**Files:**
- Create: `src/f018_platform/contracts.py`
- Test: `src/tests/f018_platform/test_contracts.py`

**Steps:**
1. Write failing tests for `VersionContext`, `IngestManifest`, `RecommendationTrace`, `PolicyDecision`, and `AbstentionReason` validation.
2. Run the focused tests and verify they fail for missing contracts.
3. Implement immutable dataclasses or Pydantic models with explicit version IDs and tenant/campaign scope.
4. Run the focused tests.
5. Update the F018 feature document and commit.

### Task 2: Add control-plane schema and repositories

**Files:**
- Modify: `src/f007_infrastructure/migrations/runner.py`
- Create: `src/f018_platform/repositories.py`
- Test: `src/tests/f018_platform/test_repositories.py`

**Steps:**
1. Write tests for idempotent ingest jobs, stage checkpoints, dead-letter records, version manifests, recommendation traces, and feedback events.
2. Run tests to verify the repository/schema methods are missing.
3. Add migrations for `ingest_jobs`, `ingest_records`, `knowledge_versions`, `recommendation_traces`, and `feedback_events`; implement async repository methods.
4. Run focused repository tests.
5. Update F018 docs and commit.

## Phase 2: Easy, resumable ingestion

### Task 3: Build the ingest service and CLI/API

**Files:**
- Create: `src/f018_platform/ingest_service.py`
- Create: `src/f018_platform/cli.py`
- Modify: `src/f009_api_server/server.py`
- Test: `src/tests/f018_platform/test_ingest_service.py`

**Steps:**
1. Write tests for JSONL validation, corpus fingerprinting, idempotency, checkpoint resume, progress, pause/cancel, and dead-letter replay.
2. Run tests red.
3. Implement the service around F017 loaders and existing stage functions; expose `ingest`, job status, replay, pause, resume, and cancel operations.
4. Run focused tests and a small fixture corpus end to end.
5. Update F018 docs and commit.

### Task 4: Add version promotion and tenant isolation

**Files:**
- Create: `src/f018_platform/version_service.py`
- Modify: `src/f006_retrieval_engine/retrieval_engine.py`
- Modify: `src/f009_api_server/server.py`
- Test: `src/tests/f018_platform/test_version_isolation.py`

**Steps:**
1. Write tests proving unapproved, expired, and cross-tenant versions cannot be retrieved.
2. Run tests red.
3. Add approval/promotion/rollback APIs and require approved `VersionContext` in retrieval.
4. Run focused tests.
5. Update F018 docs and commit.

## Phase 3: Safety and recommendation traceability

### Task 5: Implement policy evaluation and abstention

**Files:**
- Create: `src/f018_platform/policy.py`
- Modify: `src/f006_retrieval_engine/retrieval_engine.py`
- Modify: `src/f009_api_server/server.py`
- Test: `src/tests/f018_platform/test_policy.py`

**Steps:**
1. Write tests for blocked scripts, required human review, safe fallback, abstention, and policy-version traceability.
2. Run tests red.
3. Implement deterministic policy checks before final ranking and explicit abstention responses.
4. Run focused tests.
5. Update F018 docs and commit.

### Task 6: Add deterministic provider resilience

**Files:**
- Create: `src/f018_platform/resilience.py`
- Modify: `src/f007_infrastructure/llm_client.py`
- Modify: `src/f007_infrastructure/embeddings.py`
- Modify: `src/f009_api_server/server.py`
- Test: `src/tests/f018_platform/test_resilience.py`

**Steps:**
1. Write tests for timeout, retry budget, circuit opening, bounded concurrency, cache hit, and safe fallback behavior.
2. Run tests red.
3. Implement provider adapters with explicit timeout/circuit/cache policies.
4. Run focused tests.
5. Update F018 docs and commit.

## Phase 4: Evaluation, feedback, and operations

### Task 7: Build offline recommendation evaluation

**Files:**
- Create: `src/f018_platform/evaluation.py`
- Create: `src/scripts/evaluate_recommendations.py`
- Test: `src/tests/f018_platform/test_evaluation.py`

**Steps:**
1. Write tests for deterministic fixture evaluation, top-k metrics, policy violations, abstention quality, calibration, latency, and slice reports.
2. Run tests red.
3. Implement JSONL evaluation cases and machine-readable report output.
4. Run the fixture evaluation and add a CI threshold command.
5. Update F018 docs and commit.

### Task 8: Capture feedback and drift signals

**Files:**
- Create: `src/f018_platform/feedback.py`
- Modify: `src/f009_api_server/server.py`
- Create: `src/scripts/report_drift.py`
- Test: `src/tests/f018_platform/test_feedback.py`

**Steps:**
1. Write tests for immutable shown/accepted/edited/rejected/override/outcome events and drift aggregation.
2. Run tests red.
3. Implement event capture and JSON/SQL drift reports.
4. Run focused tests.
5. Update F018 docs and commit.

### Task 9: Add observability and privacy controls

**Files:**
- Modify: `src/f007_infrastructure/logging.py`
- Modify: `src/f009_api_server/server.py`
- Create: `src/f018_platform/privacy.py`
- Test: `src/tests/f018_platform/test_observability_privacy.py`

**Steps:**
1. Write tests for trace propagation, PII redaction, tenant isolation, retention classification, and health metrics.
2. Run tests red.
3. Implement structured trace fields, redaction, and operational metrics.
4. Run focused tests.
5. Update F018 docs and commit.

## Final verification

- Run all `src/tests/f018_platform` tests.
- Run the full repository suite.
- Run the fixture ingest → version promotion → recommendation → policy → trace → feedback flow.
- Run the offline evaluation threshold command.
- Do not run the F017 100k RSS benchmark unless explicitly requested.
- Update the F018 feature document after each phase; do not mark complete until every P0 criterion has executable evidence.
