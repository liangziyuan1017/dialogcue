from unittest.mock import MagicMock, patch

import openai

from f007_infrastructure.embeddings import EMBEDDING_DIM, embed_texts


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


def test_call_deepseek_passes_max_tokens():
    from f007_infrastructure.llm_client import call_deepseek

    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="ok"))]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp
    with patch("f007_infrastructure.llm_client._get_client", return_value=mock_client):
        call_deepseek("hello")
    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert "max_tokens" in call_kwargs
    assert call_kwargs["max_tokens"] == 16384


def test_call_deepseek_passes_timeout():
    from f007_infrastructure.llm_client import call_deepseek

    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="ok"))]
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp
    with patch("f007_infrastructure.llm_client._get_client", return_value=mock_client):
        call_deepseek("hello")
    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert "timeout" in call_kwargs
    assert call_kwargs["timeout"] == 60


def test_embed_texts_chunks_by_batch_size():
    with patch("f007_infrastructure.embeddings._cfg", side_effect=lambda k, d=None: 2 if k == "embedding.batch_size" else d):
        vecs = [[0.1] * EMBEDDING_DIM, [0.2] * EMBEDDING_DIM, [0.3] * EMBEDDING_DIM]
        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = [
            _mock_embedding_response(vecs[0:2]),
            _mock_embedding_response(vecs[2:3]),
        ]
        with patch("f007_infrastructure.embeddings._get_embed_client", return_value=mock_client):
            result = embed_texts(["a", "b", "c"])
    assert len(result) == 3
    assert mock_client.embeddings.create.call_count == 2


def test_embed_texts_zero_fills_failed_batch():
    err = openai.InternalServerError("batch failed", response=MagicMock(), body=None)
    with patch("f007_infrastructure.embeddings._cfg", side_effect=lambda k, d=None: 2 if k == "embedding.batch_size" else d), \
         patch("f007_infrastructure.retry.time.sleep"):
        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = [
            _mock_embedding_response([[0.1] * EMBEDDING_DIM, [0.2] * EMBEDDING_DIM]),
            err, err, err, err,
        ]
        with patch("f007_infrastructure.embeddings._get_embed_client", return_value=mock_client):
            result = embed_texts(["a", "b", "c"])
    assert len(result) == 3
    assert result[2] == [0.0] * EMBEDDING_DIM
