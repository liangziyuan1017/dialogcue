import os
from pathlib import Path

import yaml

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config.md"
_cache = None
_validated = False


class ConfigError(ValueError):
    pass

_VALIDATION_RULES = [
    ("ranking_weights.win_rate", (0.0, 1.0)),
    ("ranking_weights.vec_score", (0.0, 1.0)),
    ("ranking_weights.sas", (0.0, 1.0)),
    ("ranking_weights.bg_boost", (0.0, 1.0)),
    ("bg_boost.education_match", (0.0, 1.0)),
    ("bg_boost.risk_level_match", (0.0, 1.0)),
    ("bg_boost.complaint_proximity_match", (0.0, 1.0)),
    ("bg_boost.complaint_proximity_threshold", (0, 100000)),
    ("bg_boost.delinquent_proximity_match", (0.0, 1.0)),
    ("bg_boost.delinquent_proximity_threshold", (0, 100000)),
    ("bg_boost.recent_contact_signal", (0.0, 1.0)),
    ("bg_boost.digits_proximity_match", (0.0, 1.0)),
    ("bg_boost.digits_proximity_threshold", (0, 100000)),
    ("confidence.subset_drop_penalty", (0.0, 1.0)),
    ("confidence.root_fallback", (0.0, 1.0)),
    ("confidence.descend_penalty", (0.0, 1.0)),
    ("confidence.context_missing_penalty", (0.0, 1.0)),
    ("confidence.bitmask_mismatch_penalty", (0.0, 1.0)),
    ("confidence.embed_fallback_penalty", (0.0, 1.0)),
    ("keyword_confidence.base", (0.0, 1.0)),
    ("keyword_confidence.per_match", (0.0, 1.0)),
    ("keyword_confidence.ceiling", (0.0, 1.0)),
    ("keyword_confidence.no_match", (0.0, 1.0)),
    ("hwr.default", (0.0, 1.0)),
    ("search.trigram_threshold", (0.0, 1.0)),
    ("search.taxonomy_trigram_threshold", (0.0, 1.0)),
    ("pool_cap", (1, 1000)),
    ("db.pool_max", (1, 100)),
    ("retry.max_retries", (0, 100)),
    ("retry.min_sleep", (0, 3600)),
    ("retry.max_sleep", (0, 3600)),
    ("hnsw.m", (1, 256)),
    ("hnsw.ef_construction", (1, 1024)),
    ("sas.ngram_size", (1, 10)),
    ("decision_tree.max_merged_words", (1, 10000)),
    ("decision_tree.ack_max_words", (1, 1000)),
    ("decision_tree.find_node_max_levels", (1, 100)),
    ("reward.explanation_max_words", (1, 10000)),
    ("context_window.conversation_turns", (1, 1000)),
    ("context_window.script_prefix_length", (1, 10000)),
    ("context_window.reward_last_n_turns", (1, 100)),
    ("context_window.analysis_turns_before", (1, 100)),
    ("search.vector_limit", (1, 10000)),
    ("search.keyword_limit", (1, 10000)),
    ("search.taxonomy_limit", (1, 10000)),
    ("batch_size.data_cleaning", (1, 1000)),
    ("batch_size.analysis", (1, 1000)),
    ("batch_size.keyword_discovery", (1, 1000)),
    ("server.tree_explorer_port", (1, 65535)),
    ("server.request_max_chars", (1, 1000000)),
    ("server.rate_limit_rps", (0, 100000)),
    ("server.rate_limit_burst", (1, 100000)),
    ("server.session_ttl", (1, 86400)),
    ("server.session_max", (1, 1000000)),
    ("extraction.cache_size", (0, 1000000)),
    ("extraction.max_labels", (1, 1000)),
    ("decision_tree.max_subset_combinations", (1, 10000000)),
    ("pipeline.scheduler_interval", (0, 86400)),
    ("embedding.dimension", (1, 8192)),
    ("embedding.batch_size", (1, 10000)),
    ("llm.timeout", (1, 3600)),
    ("llm.max_tokens", (1, 1000000)),
]


def _validate(cfg):
    errors = []
    ranking_keys = ["win_rate", "vec_score", "sas", "bg_boost", "bitmask_score"]
    rw = cfg.get("ranking_weights", {})
    if isinstance(rw, dict) and all(k in rw for k in ranking_keys):
        total = sum(float(rw.get(k, 0)) for k in ranking_keys)
        if abs(total - 1.0) > 0.01:
            errors.append(f"ranking_weights sum = {total:.4f}, expected 1.0")
    for key, (lo, hi) in _VALIDATION_RULES:
        parts = key.split(".")
        node = cfg
        for p in parts:
            if isinstance(node, dict):
                node = node.get(p)
            else:
                node = None
                break
        if node is None:
            continue
        try:
            val = float(node)
        except (ValueError, TypeError):
            errors.append(f"{key} = {node!r} is not a number")
            continue
        if val < lo or val > hi:
            errors.append(f"{key} = {val} outside range [{lo}, {hi}]")
    provider = (cfg.get("extraction") or {}).get("provider") if isinstance(cfg.get("extraction"), dict) else None
    if provider is not None and str(provider).strip().lower() not in ("llm", "bert"):
        errors.append(f"extraction.provider = {provider!r} must be 'llm' or 'bert'")
    return errors


def _parse_frontmatter(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if not text.startswith("---"):
        return {}
    try:
        end = text.index("---", 3)
    except ValueError:
        raise ConfigError(f"config file {path} has opening '---' but no closing '---' fence") from None
    return yaml.safe_load(text[3:end]) or {}


def load_config():
    global _cache, _validated
    if _cache is not None:
        return _cache
    path = os.environ.get("CONFIG_PATH", str(_CONFIG_PATH))
    _cache = _parse_frontmatter(path)
    if not _validated:
        errors = _validate(_cache)
        if errors:
            msg = "config.md validation errors:\n  " + "\n  ".join(errors)
            raise ValueError(msg)
        _validated = True
    return _cache


def reload_config():
    global _cache, _validated
    _cache = None
    _validated = False
    return load_config()


def get(key, default=None):
    cfg = load_config()
    parts = key.split(".")
    for p in parts:
        if isinstance(cfg, dict):
            cfg = cfg.get(p)
        else:
            return default
        if cfg is None:
            return default
    return cfg
