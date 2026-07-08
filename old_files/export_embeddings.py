"""
Export embeddings from PostgreSQL sentences table to a JSON cache file.
One-time operation to seed the embedding cache before re-running the pipeline.
"""
import json
import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
CACHE_DIR = _PROJECT_ROOT / "src" / "f007_infrastructure" / "data"
CACHE_FILE = CACHE_DIR / "embedding_cache.json"


def main() -> None:
    from f007_infrastructure.db import SentenceDB

    dsn = os.environ.get("PG_DSN", "dbname=icbc user=jiani")
    db = SentenceDB(dsn)

    print("Querying sentences table...")
    with db.connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT script_id, script_text, embedding FROM sentences")
        rows = cur.fetchall()
        cur.close()

    cache = {}
    for script_id, script_text, embedding in rows:
        vec = embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
        cache[script_id] = {
            "script_text": script_text,
            "embedding": vec,
        }

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f)

    db.close()
    print(f"Exported {len(cache)} embeddings to {CACHE_FILE}")


if __name__ == "__main__":
    main()
