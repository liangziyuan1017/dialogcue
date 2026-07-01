import os

from f007_infrastructure.config import get as _cfg
from f007_infrastructure.llm_client import RETRYABLE_LLM_ERRORS, _get_client
from f007_infrastructure.logging import get_logger as _get_logger
from f007_infrastructure.retry import retry_call

_log = _get_logger(__name__)

EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", _cfg("embedding.model", "bge-m3"))
EMBEDDING_BASE_URL = os.environ.get("EMBEDDING_BASE_URL", _cfg("embedding.api_base", "http://localhost:11434/v1"))
EMBEDDING_API_KEY = os.environ.get("EMBEDDING_API_KEY", _cfg("embedding.api_key", "ollama"))
EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM", str(_cfg("embedding.dimension", 1024))))


def _get_embed_client():
    from openai import OpenAI
    if EMBEDDING_BASE_URL:
        return OpenAI(api_key=EMBEDDING_API_KEY, base_url=EMBEDDING_BASE_URL)
    return _get_client()


def embed_single(text: str) -> list[float]:
    client = _get_embed_client()
    resp = retry_call(
        client.embeddings.create,
        model=EMBEDDING_MODEL,
        input=text,
        retryable=RETRYABLE_LLM_ERRORS,
    )
    return resp.data[0].embedding


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    client = _get_embed_client()
    batch_size = _cfg("embedding.batch_size", 64)
    results: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        try:
            resp = retry_call(
                client.embeddings.create,
                model=EMBEDDING_MODEL,
                input=batch,
                retryable=RETRYABLE_LLM_ERRORS,
            )
            batch_vecs = [d.embedding for d in sorted(resp.data, key=lambda d: d.index)]
        except RETRYABLE_LLM_ERRORS as e:
            _log.warning("embedding batch %d failed after retries: %s; zero-filling", i // batch_size, e)
            batch_vecs = [[0.0] * EMBEDDING_DIM for _ in batch]
        results.extend(batch_vecs)
    return results
