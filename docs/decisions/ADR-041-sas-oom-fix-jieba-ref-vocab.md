---
id: ADR-041
title: "SAS OOM fix: jieba word segmentation + reference-vocabulary restriction"
doc_kind: decision
feature_ids: [F005]
topics: [scoring, sas, tf-idf, oom, chinese-text, jieba]
status: accepted
created: 2026-07-15
updated: 2026-07-15
schema_version: 2
---

# SAS OOM Fix: Jieba Word Segmentation + Reference-Vocabulary Restriction

## What

Replace character bigram TF-IDF with jieba word bigram TF-IDF, and restrict the TF-IDF vocabulary to ngrams present in the reference document only.

Two changes in `scoring_metrics.py`:

1. **`_char_ngrams` → `_word_ngrams`**: Uses `jieba.cut()` for Chinese word segmentation, then builds word-level bigrams. Vocabulary drops from millions to ~10K-50K.

2. **Removed `_build_tfidf_matrix`**: `compute_sas_for_pool` now builds TF-IDF inline, restricted to the reference document's ngrams. Each candidate's ngrams are filtered to only those present in the reference vocabulary before counting. Matrix shape becomes `(n_docs, |ref_ngrams|)` instead of `(n_docs, millions)`.

## Why

Character bigrams on Chinese text create a massive vocabulary. Every consecutive character pair is a feature:

```
"公司上个月倒闭了" → ["公司", "司上", "上个月", "个月", "月倒", "倒闭", "闭了"]
```

With ~2,134 TurnSamples × avg 50-200 chars each, the full corpus produces millions of unique character bigrams. The sparse TF-IDF matrix `(2134, millions)` causes OOM (~1.96G non-zero entries or densification).

### Specific bottlenecks eliminated

| Operation | Before (char bigrams) | After (jieba + ref-vocab) |
|-----------|----------------------|--------------------------|
| vocab dict | millions of unique char bigrams | hundreds of ref word bigrams |
| df / idf arrays | `np.zeros(millions)` → 16MB+ | `np.zeros(hundreds)` → KBs |
| TF-IDF matrix | `(2134, millions)` sparse | `(2134, hundreds)` sparse |
| `_sparse_norm(axis=1)` | risk of densification OOM | tiny, no OOM risk |

### Why not just min_df/max_df filtering?

min_df/max_df (Option A) reduces vocabulary but still builds a full-corpus TF-IDF. Since SAS only computes similarity against one reference document, the full vocabulary is wasteful — ngrams absent from the reference contribute zero to all cosine similarities.

## Tradeoff

| Alternative | Rejected Because |
|-------------|-----------------|
| Character bigrams + min_df/max_df (Option A) | Still builds full-corpus TF-IDF; vocabulary still large; ngrams absent from ref contribute nothing |
| Character bigrams + ref-vocab only | Char bigrams on Chinese still produce noisy features; word segmentation is more meaningful |
| jieba + full-corpus TF-IDF (Option C alone) | Better vocab size but still wasteful — full corpus vocab unnecessary for single-reference cosine |
| Keep `_build_tfidf_matrix` function | No longer needed; inline construction is clearer and avoids building unused full-corpus structures |

## Impact

- **`scoring_metrics.py`**: New `_word_ngrams()` using jieba. Removed `_char_ngrams()` and `_build_tfidf_matrix()`. `compute_sas_for_pool()` builds ref-vocabulary-restricted TF-IDF inline.
- **Dependencies**: Added `jieba` (pip package). First call triggers dictionary build (~0.2s), cached thereafter.
- **SAS values**: May differ slightly from previous char-bigram SAS due to different tokenization. This is expected — word bigrams are more semantically meaningful.
- **Memory**: OOM eliminated. Matrix size reduced by ~1000x.
- **ADR-020**: Updated SAS description from "char bigram" to "jieba word bigram + ref-vocab-restricted".
- **F005 feature doc**: Updated SAS description, acceptance criteria, and design decisions.
