
import pytest

from f006_retrieval_engine import retrieval_ranking as rr


def _pool_with(win_rate=0.0, vec_score=0.0, sas=0.0):
    return [
        {"script_id": "s1", "script_text": "t", "win_rate": win_rate, "sas": sas, "bg_background": {}, "_bitmask_score": 1.0},
    ]


def _patch_cfg(monkeypatch, **overrides):
    base = {
        "ranking_weights.win_rate": 0.0,
        "ranking_weights.vec_score": 0.0,
        "ranking_weights.sas": 0.0,
        "ranking_weights.bg_boost": 0.0,
        "ranking_weights.bitmask_score": 0.0,
    }
    base.update(overrides)

    def fake(key, default=None):
        return base.get(key, default)

    monkeypatch.setattr(rr, "_cfg", fake)


def test_get_ranking_weights_reads_live(monkeypatch):
    _patch_cfg(monkeypatch, **{"ranking_weights.win_rate": 1.0})
    w = rr.get_ranking_weights()
    assert w["win_rate"] == 1.0


async def test_rank_sentences_uses_live_weights(monkeypatch):
    _patch_cfg(monkeypatch, **{"ranking_weights.win_rate": 1.0})
    pool = _pool_with(win_rate=0.5)
    ranked = await rr.rank_sentences(pool, query_vec=None, db=None, query_bg={}, conversation_context="", context_missing=True)
    assert ranked[0]["final_score"] == pytest.approx(0.5, abs=1e-9)


async def test_rank_sentences_reflects_changed_weights_without_restart(monkeypatch):
    _patch_cfg(monkeypatch, **{"ranking_weights.win_rate": 1.0})
    pool = _pool_with(win_rate=0.5)
    ranked = await rr.rank_sentences(pool, query_vec=None, db=None, query_bg={}, conversation_context="", context_missing=True)
    assert ranked[0]["final_score"] == pytest.approx(0.5, abs=1e-9)

    _patch_cfg(monkeypatch, **{"ranking_weights.sas": 1.0})
    pool2 = _pool_with(win_rate=0.5, sas=0.8)
    ranked2 = await rr.rank_sentences(pool2, query_vec=None, db=None, query_bg={}, conversation_context="", context_missing=True)
    assert ranked2[0]["final_score"] == pytest.approx(0.8, abs=1e-9)
