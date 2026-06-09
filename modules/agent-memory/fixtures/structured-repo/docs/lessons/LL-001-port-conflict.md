---
id: LL-001
title: "Port 8080 conflict between API and dashboard services"
doc_kind: lesson
feature_ids: []
topics: [ops, networking, ports]
status: accepted
created: 2026-01-20
schema_version: 1
authority: validated
---

# LL-001: Port 8080 Conflict

## 1. Pitfall

Both the API service and dashboard service were configured with default port 8080,
causing a bind conflict on startup.

## 2. Root Cause

Both services used framework defaults without a centralized port allocation strategy.
No pre-flight port conflict check existed.

## 3. Trigger Conditions

Any time two services are configured with default ports that overlap. Most common
when adding new services to an existing deployment.

## 4. Fix

Changed dashboard to port 8081. Added port allocation table to `docs/operations/ports.md`.

## 5. Guard (Executable)

`scripts/port-check.py` — runs before any service start; scans for port conflicts and
blocks startup if overlap is detected.

## 6. Source Anchors

- commit:abc123def — "Fix port 8080 conflict between api and dashboard"
- `docs/operations/ports.md` — Centralized port allocation table
