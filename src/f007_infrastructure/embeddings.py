import os

from f007_infrastructure.config import get as _cfg
from f007_infrastructure.llm_client import _get_client

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
    resp = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return resp.data[0].embedding


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    client = _get_embed_client()
    resp = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [d.embedding for d in sorted(resp.data, key=lambda d: d.index)]
