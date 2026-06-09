#!/usr/bin/env python3
"""
semantic-search — Vector similarity search over indexed documents.

STUB: Not yet fully implemented. Requires pre-computed embedding index.

Purpose: Semantic search using embedding service. Degrades gracefully if unavailable.
Invoker: memory-search workflow.
Related tests: tests/test_search_memory.py

Input:  --query <STRING>        Search query
        --limit <N>             Max results (default: 50)
        --health                Check if embedding service is reachable
        --endpoint <URL>        Embedding service endpoint (or set AGENT_MEMORY_EMBEDDING_ENDPOINT env var)

Output: JSON results or health status to stdout.
Exit:   0 on success, 1 if service unreachable (--health mode), 1 on error.
"""
import argparse
import sys
import json
import os
import urllib.request
import urllib.error


def _get_endpoint(args_endpoint: str | None) -> str:
    """Resolve endpoint from arg or env var."""
    if args_endpoint:
        return args_endpoint
    env = os.environ.get("AGENT_MEMORY_EMBEDDING_ENDPOINT")
    if env:
        return env
    print(json.dumps({"error": "--endpoint or AGENT_MEMORY_EMBEDDING_ENDPOINT env var is required"}), file=sys.stderr)
    sys.exit(1)


def check_health(endpoint: str) -> bool:
    """Check if embedding service is reachable."""
    try:
        req = urllib.request.Request(endpoint + "/health" if not endpoint.endswith("/health") else endpoint)
        urllib.request.urlopen(req, timeout=5)
        return True
    except (urllib.error.URLError, Exception):
        return False


def embed_query(query: str, endpoint: str) -> list[float] | None:
    """Get embedding vector for a query string."""
    try:
        data = json.dumps({"input": query, "model": "Qwen3-Embedding-0.6B"}).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if "data" in result and len(result["data"]) > 0:
                return result["data"][0].get("embedding", [])
    except Exception:
        pass
    return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def main():
    parser = argparse.ArgumentParser(description="Semantic search via embeddings (stub — requires pre-computed index)")
    parser.add_argument("--query", default=None, help="Search query")
    parser.add_argument("--limit", type=int, default=50, help="Max results")
    parser.add_argument("--health", action="store_true", help="Check embedding service health")
    parser.add_argument("--endpoint", default=None, help="Embedding service endpoint (or set AGENT_MEMORY_EMBEDDING_ENDPOINT)")
    args = parser.parse_args()

    endpoint = _get_endpoint(args.endpoint)

    if args.health:
        healthy = check_health(endpoint)
        if healthy:
            print("healthy")
        else:
            print("unreachable")
        sys.exit(0 if healthy else 1)

    if not args.query:
        print(json.dumps({"error": "--query is required"}))
        sys.exit(1)

    query_vec = embed_query(args.query, endpoint)
    if query_vec is None:
        print(json.dumps({
            "query": args.query,
            "mode": "semantic",
            "error": "embedding service unreachable",
            "results": [],
            "count": 0,
        }))
        sys.exit(1)

    print(json.dumps({
        "query": args.query,
        "mode": "semantic",
        "note": "semantic search requires pre-computed index; returning empty for now",
        "results": [],
        "count": 0,
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
