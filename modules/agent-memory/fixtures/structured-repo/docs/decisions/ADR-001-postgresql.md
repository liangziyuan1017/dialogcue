---
id: ADR-001
title: "Use PostgreSQL 16 as primary database"
doc_kind: decision
feature_ids: [F001]
topics: [database, persistence]
status: accepted
created: 2026-01-15
updated: 2026-02-01
schema_version: 1
---

# ADR-001: Use PostgreSQL 16 as Primary Database

## What

Use PostgreSQL 16 as the primary relational database for all persistent storage.

## Why

ACID compliance, robust JSONB support, mature replication, and strong community support.
Compared to MySQL, PostgreSQL offers better JSON handling and stricter SQL compliance.

## Tradeoff

| Alternative | Why Rejected |
|---|---|
| MySQL 8.4 | Weaker JSON support; less mature full-text search |
| SQLite | Not suitable for multi-writer concurrent workloads |
| MongoDB | Document model is attractive but ACID across collections is weaker |
