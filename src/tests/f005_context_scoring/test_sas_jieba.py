import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from f005_context_scoring.scoring_metrics import compute_sas_for_pool, _word_ngrams

pools = [
    [
        {"script_text": "您可以尽快还款吗，逾期会产生额外费用", "win_rate": 0.9},
        {"script_text": "您可以尽快办理还款，避免逾期", "win_rate": 0.5},
        {"script_text": "建议您分期还款减轻压力", "win_rate": 0.3},
        {"script_text": "我们完全不同的话题关于理财", "win_rate": 0.1},
    ],
    [
        {"script_text": "你好请问有什么可以帮您", "win_rate": 0.7},
    ],
    [
        {"script_text": "您的账户已逾期", "win_rate": 0.8},
        {"script_text": "您的账户已逾期", "win_rate": 0.4},
    ],
    [
        {"script_text": "请确认您的身份信息", "win_rate": 0.8},
        {"script_text": "今天天气真不错", "win_rate": 0.2},
    ],
    [
        {"script_text": "", "win_rate": 0.5},
        {"script_text": "", "win_rate": 0.3},
    ],
]

for i, pool in enumerate(pools, 1):
    scores = compute_sas_for_pool(pool)
    print(f"\nPool {i}:")
    for s, sc in zip(pool, scores):
        print(f"  [{sc:.4f}] {s['script_text'][:30] or '(empty)'}  (win_rate={s['win_rate']})")
