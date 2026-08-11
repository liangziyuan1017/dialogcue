"""Loss mask + model forward smoke."""

from __future__ import annotations

import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dataset import MultitaskDataset, collate_multitask, iter_mock_samples  # noqa: E402
from labels import emotion_labels, willingness_labels  # noqa: E402
from losses import fact_masked_ce_loss, multitask_loss  # noqa: E402
from model import MultitaskV1Model  # noqa: E402
from paths import load_fact_schema  # noqa: E402
from torch.utils.data import DataLoader  # noqa: E402


def test_unknown_masked_out_of_fact_loss():
    schema = load_fact_schema()
    h0 = schema.heads[0].name
    n0 = schema.heads[0].n_classes
    logits = {h.name: torch.zeros(2, h.n_classes) for h in schema.heads}
    logits[h0] = torch.randn(2, n0)
    target = {h.name: torch.zeros(2, dtype=torch.long) for h in schema.heads}
    # row0 masked out, row1 supervised
    mask = {h.name: torch.tensor([0.0, 0.0]) for h in schema.heads}
    mask[h0] = torch.tensor([0.0, 1.0])
    target[h0] = torch.tensor([0, 0])
    loss = fact_masked_ce_loss(logits, target, mask)
    assert torch.isfinite(loss)
    # all-masked head should yield zero-ish total when every head masked
    mask_all = {h.name: torch.zeros(2) for h in schema.heads}
    loss0 = fact_masked_ce_loss(logits, target, mask_all)
    assert float(loss0.item()) == 0.0


def test_model_forward_and_step():
    schema = load_fact_schema()
    emo = emotion_labels()
    will = willingness_labels()
    samples = list(
        iter_mock_samples(schema, emotion_vocab=emo, willingness_vocab=will, n=4)
    )
    # force one emotion unknown
    samples[0].emotion = None
    ds = MultitaskDataset(
        samples, fact_schema=schema, emotion_vocab=emo, willingness_vocab=will
    )
    loader = DataLoader(ds, batch_size=2, collate_fn=collate_multitask)
    model = MultitaskV1Model(
        "__mock__", fact_schema=schema, emotion_vocab=emo, willingness_vocab=will
    )
    device = torch.device("cpu")
    batch = next(iter(loader))
    out = model(batch["texts"], device)
    assert len(out["fact_logits"]) == schema.n_heads
    assert out["emotion_logits"].shape[-1] == 11
    assert out["willingness_logits"].shape[-1] == 5
    loss, parts = multitask_loss(
        fact_logits=out["fact_logits"],
        fact_target=batch["fact_target"],
        fact_mask=batch["fact_mask"],
        emotion_logits=out["emotion_logits"],
        emotion_target=batch["emotion_target"],
        emotion_mask=batch["emotion_mask"],
        willingness_logits=out["willingness_logits"],
        willingness_target=batch["willingness_target"],
        willingness_mask=batch["willingness_mask"],
    )
    assert torch.isfinite(loss)
    assert "fact" in parts and "emotion" in parts
    loss.backward()


def test_unlabeled_emotion_is_masked_not_class_zero():
    schema = load_fact_schema()
    emo = emotion_labels()
    will = willingness_labels()
    samples = list(
        iter_mock_samples(schema, emotion_vocab=emo, willingness_vocab=will, n=2)
    )
    samples[0].emotion = None
    samples[0].willingness = None
    ds = MultitaskDataset(
        samples, fact_schema=schema, emotion_vocab=emo, willingness_vocab=will
    )
    item = ds[0]
    assert item["emotion_mask"] == 0.0
    assert item["willingness_mask"] == 0.0
    assert item["task_mask"]["emotion"] == 0.0
    assert item["task_mask"]["willingness"] == 0.0
    # placeholder index may be 0, but mask keeps it out of loss
    assert item["emotion_target"] == 0
