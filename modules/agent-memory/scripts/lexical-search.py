#!/usr/bin/env python3
"""
lexical-search — Exact and fuzzy text search over indexed documents.

Purpose: Search document titles, IDs, and body text using exact matching.
Invoker: memory-search, decision-record, lesson-capture workflows.
Related tests: tests/test_search_memory.py

Input:  --query <STRING>        Search query
        --doc-kind <KIND>       (optional) Filter by doc_kind
        --feature-id <ID>       (optional) Filter by feature_id
        --topic <TOPIC>         (optional) Filter by topic
        --authority <LEVEL>     (optional) Filter by authority
        --limit <N>             Max results (default: 50)
        --index-file <PATH>     Index file path (default: src/.agent-memory/index.json)

Output: JSON ranked results to stdout.
Exit:   0 on success, 1 on error.
"""
import argparse
import sys
import json
from pathlib import Path


def load_index(index_file: Path) -> dict:
    """Load the searchable index."""
    if not index_file.exists():
        return {"entries": {}}
    with open(index_file, "r") as f:
        return json.load(f)


def score_entry(entry: dict, query: str) -> float:
    """Score an index entry against a query string."""
    score = 0.0
    query_lower = query.lower()

    if entry.get("id", "").lower() == query_lower:
        return 100.0

    if query_lower in entry.get("id", "").lower():
        score += 50.0

    title = entry.get("title", "").lower()
    if query_lower in title:
        score += 30.0
    for word in query_lower.split():
        if word in title:
            score += 5.0

    body = entry.get("body_preview", "").lower()
    if query_lower in body:
        score += 10.0
    for word in query_lower.split():
        if word in body:
            score += 2.0

    topics = entry.get("topics", "")
    if isinstance(topics, str) and query_lower in topics.lower():
        score += 8.0

    return score


def search(query: str, filters: dict, limit: int = 50, index_file: Path = None) -> list[dict]:
    """Search the index and return ranked results."""
    index = load_index(index_file)
    results = []

    for doc_id, entry in index.get("entries", {}).items():
        if filters.get("doc_kind") and entry.get("doc_kind") != filters["doc_kind"]:
            continue
        if filters.get("feature_id"):
            fids = entry.get("feature_ids", "")
            if filters["feature_id"] not in str(fids):
                continue
        if filters.get("topic"):
            topics = entry.get("topics", "")
            if filters["topic"] not in str(topics):
                continue

        score = score_entry(entry, query)
        if score > 0:
            results.append({
                "doc_id": entry.get("id", doc_id),
                "title": entry.get("title", ""),
                "doc_kind": entry.get("doc_kind", ""),
                "score": score,
                "snippet": entry.get("body_preview", "")[:200],
                "path": entry.get("path", ""),
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]


def main():
    parser = argparse.ArgumentParser(description="Lexical search over memory index")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--doc-kind", default=None, help="Filter by doc_kind")
    parser.add_argument("--feature-id", default=None, help="Filter by feature_id")
    parser.add_argument("--topic", default=None, help="Filter by topic")
    parser.add_argument("--authority", default=None, help="Filter by authority")
    parser.add_argument("--limit", type=int, default=50, help="Max results")
    parser.add_argument("--index-file", default="src/.agent-memory/index.json", help="Index file path")
    args = parser.parse_args()

    filters = {
        "doc_kind": args.doc_kind,
        "feature_id": args.feature_id,
        "topic": args.topic,
        "authority": args.authority,
    }
    filters = {k: v for k, v in filters.items() if v is not None}

    results = search(args.query, filters, args.limit, Path(args.index_file))

    print(json.dumps({
        "query": args.query,
        "mode": "lexical",
        "results": results,
        "count": len(results),
    }, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
