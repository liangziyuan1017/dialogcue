from infra.llm_client import _get_client


def embed_single(text: str) -> list[float]:
    client = _get_client()
    resp = client.embeddings.create(model="deepseek-chat", input=text)
    return resp.data[0].embedding


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    client = _get_client()
    resp = client.embeddings.create(model="deepseek-chat", input=texts)
    return [d.embedding for d in sorted(resp.data, key=lambda d: d.index)]
