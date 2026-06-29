import numpy as np
from unittest.mock import patch, MagicMock
from infra.embeddings import embed_single, embed_texts, EMBEDDING_MODEL


def _mock_embedding_response(vectors):
    data = []
    for i, vec in enumerate(vectors):
        item = MagicMock()
        item.embedding = vec
        item.index = i
        data.append(item)
    resp = MagicMock()
    resp.data = data
    return resp


DUMMY_VEC = [0.1] * 768


def test_embed_single_returns_768_dim_vector():
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = _mock_embedding_response([DUMMY_VEC])
    with patch("infra.embeddings._get_client", return_value=mock_client):
        result = embed_single("测试")
    assert isinstance(result, list)
    assert len(result) == 768
    assert all(isinstance(v, float) for v in result)


def test_embed_single_nonzero_norm():
    vec = [0.0] * 767 + [1.0]
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = _mock_embedding_response([vec])
    with patch("infra.embeddings._get_client", return_value=mock_client):
        result = embed_single("测试")
    norm = np.linalg.norm(result)
    assert norm > 0


def test_embed_single_calls_correct_model():
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = _mock_embedding_response([DUMMY_VEC])
    with patch("infra.embeddings._get_embed_client", return_value=mock_client):
        embed_single("hello")
    call_kwargs = mock_client.embeddings.create.call_args
    assert call_kwargs[1]["model"] == EMBEDDING_MODEL
    assert call_kwargs[1]["input"] == "hello"


def test_embed_texts_returns_list_of_vectors():
    vecs = [DUMMY_VEC, [0.2] * 768]
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = _mock_embedding_response(vecs)
    with patch("infra.embeddings._get_client", return_value=mock_client):
        result = embed_texts(["hello", "world"])
    assert isinstance(result, list)
    assert len(result) == 2
    assert len(result[0]) == 768
    assert len(result[1]) == 768


def test_embed_texts_empty_list_returns_empty():
    result = embed_texts([])
    assert result == []


def test_embed_texts_preserves_order():
    vec_a = [1.0] + [0.0] * 767
    vec_b = [0.0] * 767 + [1.0]
    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = _mock_embedding_response([vec_a, vec_b])
    with patch("infra.embeddings._get_client", return_value=mock_client):
        result = embed_texts(["a", "b"])
    assert result[0][0] == 1.0
    assert result[1][767] == 1.0
