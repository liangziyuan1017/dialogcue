#!/usr/bin/env python3
"""
result-format — Format ranked search results with source anchors.

Purpose: Present search results in a readable format with metadata.
         --apply-boost reorders results by authority and status.
Invoker: memory-search workflow.
Related tests: tests/test_search_memory.py

Input:  --results <JSON>        Search results to format
        --limit <N>             Max results to display (default: 10)
        --apply-boost           Reorder by authority (constitutional > validated > candidate > observed)
                                and status (accepted > draft > review > superseded > archived)

Output: Formatted results to stdout.
Exit:   0 always.
"""
import argparse
import sys
import json

AUTHORITY_RANK = {"constitutional": 4, "validated": 3, "candidate": 2, "observed": 1}
STATUS_RANK = {"accepted": 5, "draft": 4, "review": 3, "superseded": 2, "archived": 1}


def apply_boost(results: list[dict]) -> list[dict]:
    """Boost results by authority and status, then by original score."""
    def boost_key(r):
        auth = AUTHORITY_RANK.get(r.get("authority", "observed"), 0)
        status = STATUS_RANK.get(r.get("status", "draft"), 0)
        score = r.get("score", r.get("rrf_score", 0))
        return (auth + status, score)
    return sorted(results, key=boost_key, reverse=True)


def main():
    parser = argparse.ArgumentParser(description="Format search results")
    parser.add_argument("--results", required=True, help="Search results JSON")
    parser.add_argument("--limit", type=int, default=10, help="Max results to display")
    parser.add_argument("--apply-boost", action="store_true", help="Reorder by authority and status")
    args = parser.parse_args()

    try:
        data = json.loads(args.results)
    except json.JSONDecodeError:
        print("ERROR: invalid JSON input")
        sys.exit(1)

    results = data.get("results", [])

    if args.apply_boost:
        results = apply_boost(results)

    results = results[:args.limit]

    if not results:
        print("No results found.")
        sys.exit(0)

    print(f"Found {data.get('count', len(results))} results (showing top {len(results)}):\n")

    for i, r in enumerate(results):
        doc_id = r.get("doc_id", "unknown")
        title = r.get("title", "Untitled")
        doc_kind = r.get("doc_kind", "")
        snippet = r.get("snippet", "")
        score = r.get("score", r.get("rrf_score", 0))
        path = r.get("path", "")

        print(f"{i+1}. [{doc_id}] {title}")
        print(f"   kind: {doc_kind}  score: {score}")
        if snippet:
            print(f"   {snippet[:150]}...")
        print()

    sys.exit(0)


if __name__ == "__main__":
    main()
