"""Paths and read-only bridge into training/multihead (no edits there)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

MT_ROOT = Path(__file__).resolve().parents[1]
CONFIGS = MT_ROOT / "configs"
MULTIHEAD_ROOT = MT_ROOT.parent / "multihead"
MULTIHEAD_SRC = MULTIHEAD_ROOT / "src"
DEFAULT_FACT_SCHEMA = MULTIHEAD_ROOT / "configs" / "schema_v3.1.yaml"


def resolve_under_mt(maybe: str | Path, *, base: Path | None = None) -> Path:
    p = Path(maybe)
    if p.is_absolute():
        return p
    root = base or MT_ROOT
    cand = (root / p).resolve()
    if cand.exists():
        return cand
    # also try relative to configs/
    alt = (CONFIGS / p).resolve()
    if alt.exists():
        return alt
    return cand


def load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_module_from_file(mod_name: str, file_path: Path) -> ModuleType:
    """Load a multihead src file without polluting package name `models`/`datasets`."""
    if not file_path.exists():
        raise FileNotFoundError(file_path)
    # Ensure sibling imports inside multihead modules resolve
    if str(MULTIHEAD_SRC) not in sys.path:
        sys.path.insert(0, str(MULTIHEAD_SRC))
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {file_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


_schema_mod: ModuleType | None = None
_metrics_mod: ModuleType | None = None
_ctx_mod: ModuleType | None = None


def multihead_schema_loader() -> ModuleType:
    global _schema_mod
    if _schema_mod is None:
        _schema_mod = _load_module_from_file(
            "mh_schema_loader_mt", MULTIHEAD_SRC / "schema_loader.py"
        )
    return _schema_mod


def multihead_state_metrics() -> ModuleType:
    global _metrics_mod
    if _metrics_mod is None:
        # state_metrics imports schema_loader — ensure that name is available
        if "schema_loader" not in sys.modules:
            sys.modules["schema_loader"] = multihead_schema_loader()
        _metrics_mod = _load_module_from_file(
            "mh_state_metrics_mt", MULTIHEAD_SRC / "metrics" / "state_metrics.py"
        )
    return _metrics_mod


def multihead_context_encode() -> ModuleType:
    global _ctx_mod
    if _ctx_mod is None:
        _ctx_mod = _load_module_from_file(
            "mh_context_encode_mt", MULTIHEAD_SRC / "context_encode.py"
        )
    return _ctx_mod


def load_fact_schema(path: str | Path | None = None):
    loader = multihead_schema_loader()
    p = Path(path) if path else DEFAULT_FACT_SCHEMA
    if not p.is_absolute():
        p = resolve_under_mt(p)
    if not p.exists():
        p = DEFAULT_FACT_SCHEMA
    return loader.load_schema(str(p))


def ensure_multihead_on_path() -> Path:
    """Allow `import conversation_parser` etc. (read-only use of multihead/src)."""
    if str(MULTIHEAD_SRC) not in sys.path:
        sys.path.insert(0, str(MULTIHEAD_SRC))
    return MULTIHEAD_SRC


def resolve_from_cfg(cfg_dir: Path, maybe: str | Path) -> Path:
    """Resolve path relative to config file directory, then multitask root."""
    p = Path(maybe)
    if p.is_absolute():
        return p
    cand = (cfg_dir / p).resolve()
    if cand.exists():
        return cand
    return resolve_under_mt(p)