#!/usr/bin/env python3
"""
hybrid-fuse — Reciprocal-rank fusion of lexical and semantic search results.

Purpose: Combine two ranked lists using RRF (k=60 default).
Invoker: memory-search workflow.
Related tests: tests/test_search_memory.py

Input:  --lexical <JSON>        Lexical search results JSON
        --semantic <JSON>       Semantic search results JSON
        --k <N>                 RRF constant (default: 60)

Output: JSON fused results to stdout.
Exit:   0 on success.
"""
import argparse
import sys
import json


def rrf_fuse(lexical: list[dict], semantic: list[dict], k: int = 60) -> list[dict]:
    """Fuse two ranked lists using Reciprocal Rank Fusion."""
    scores = {}

    for rank, item in enumerate(lexical):
        doc_id = item.get("doc_id", "")
        if doc_id not in scores:
            scores[doc_id] = {"item": item, "rrf_score": 0.0}
        scores[doc_id]["rrf_score"] += 1.0 / (k + rank + 1)
        scores[doc_id]["item"]["lexical_rank"] = rank + 1

    for rank, item in enumerate(semantic):
        doc_id = item.get("doc_id", "")
        if doc_id not in scores:
            scores[doc_id] = {"item": item, "rrf_score": 0.0}
        scores[doc_id]["rrf_score"] += 1.0 / (k + rank + 1)
        scores[doc_id]["item"]["semantic_rank"] = rank + 1

    # Sort by RRF score descending
    fused = sorted(scores.values(), key=lambda x: x["rrf_score"], reverse=True)

    results = []
    for entry in fused:
        item = entry["item"]
        item["rrf_score"] = round(entry["rrf_score"], 6)
        results.append(item)

    return results


def main():
    parser = argparse.ArgumentParser(description="RRF fusion of search results")
    parser.add_argument("--lexical", required=True, help="Lexical results JSON")
    parser.add_argument("--semantic", required=True, help="Semantic results JSON")
    parser.add_argument("--k", type=int, default=60, help="RRF constant")
    args = parser.parse_args()

    try:
        lexical_data = json.loads(args.lexical)
        semantic_data = json.loads(args.semantic)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"invalid JSON: {e}"}))
        sys.exit(1)

    lex_results = lexical_data.get("results", [])
    sem_results = semantic_data.get("results", [])

    fused = rrf_fuse(lex_results, sem_results, args.k)

    print(json.dumps({
        "results": fused,
        "count": len(fused),
        "fusion_method": f"RRF (k={args.k})",
    }, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
