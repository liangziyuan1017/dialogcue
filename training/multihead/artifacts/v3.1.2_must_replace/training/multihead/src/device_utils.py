"""Device selection: NPU (Ascend) > CUDA > CPU.

Mirrors training/src/train_utils.get_device so multihead stays self-contained.

Important (Ascend): ``import torch_npu`` MUST happen before ``torch.device("npu:…")``,
otherwise the npu backend is not registered and callers may silently end up on CPU.
"""

from __future__ import annotations

from typing import Any


def _normalize_device_spec(raw: Any) -> str:
    """YAML `device: npu:0` may parse as str or as {'npu': 0} depending on loader."""
    if raw is None:
        return ""
    if isinstance(raw, dict):
        if len(raw) == 1:
            k, v = next(iter(raw.items()))
            return f"{k}:{v}"
        raise ValueError(f"invalid device mapping: {raw!r}")
    return str(raw).strip()


def _ensure_torch_npu_imported() -> None:
    """Register Ascend private-use backend before constructing npu devices."""
    try:
        import torch_npu  # noqa: F401
    except ImportError as e:
        raise RuntimeError(
            "NPU requested but torch_npu is not installed in this Python. "
            "Use the same env as training; source Ascend set_env.sh first."
        ) from e


def get_device(config: dict[str, Any] | None = None):
    """Pick NPU > CUDA > CPU. Optional config['device'] overrides (e.g. npu:0)."""
    import torch

    if config and config.get("device") not in (None, ""):
        spec = _normalize_device_spec(config.get("device"))
        if spec.startswith("npu"):
            _ensure_torch_npu_imported()
            if not (hasattr(torch, "npu") and torch.npu.is_available()):
                raise RuntimeError(
                    f"config device={spec!r} but torch.npu.is_available() is False. "
                    "Check: source Ascend set_env.sh; "
                    '`python -c "import torch,torch_npu; print(torch.npu.is_available())"`; '
                    "same Python as training."
                )
        device = torch.device(spec)
        _maybe_init_npu(device)
        return device

    if _npu_available():
        # _npu_available already imported torch_npu
        device = torch.device("npu:0")
        _maybe_init_npu(device)
        return device
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def describe_device_env() -> str:
    """One-line diagnostic for logs (safe if torch_npu missing)."""
    import torch

    npu_import = False
    npu_ok = False
    npu_count = 0
    try:
        import torch_npu  # noqa: F401

        npu_import = True
        npu_ok = bool(hasattr(torch, "npu") and torch.npu.is_available())
        if npu_ok:
            npu_count = int(torch.npu.device_count())
    except Exception as e:  # noqa: BLE001
        return (
            f"torch={torch.__version__} torch_npu_import={npu_import} "
            f"npu_available={npu_ok} err={type(e).__name__}:{e}"
        )
    return (
        f"torch={torch.__version__} torch_npu_import={npu_import} "
        f"npu_available={npu_ok} npu_count={npu_count} "
        f"cuda_available={torch.cuda.is_available()}"
    )


def _npu_available() -> bool:
    try:
        import torch_npu  # noqa: F401
    except ImportError:
        return False
    import torch

    return hasattr(torch, "npu") and torch.npu.is_available()


def _maybe_init_npu(device) -> None:
    import torch

    if device.type != "npu":
        return
    _ensure_torch_npu_imported()
    idx = device.index if device.index is not None else 0
    torch.npu.set_device(idx)


def seed_all(seed: int) -> None:
    import random

    import torch

    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if _npu_available():
        torch.npu.manual_seed_all(seed)
