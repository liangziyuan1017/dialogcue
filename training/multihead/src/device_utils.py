"""Device selection: NPU (Ascend) > CUDA > CPU.

Mirrors training/src/train_utils.get_device so multihead stays self-contained.
"""

from __future__ import annotations

from typing import Any


def get_device(config: dict[str, Any] | None = None):
    """Pick NPU > CUDA > CPU. Optional config['device'] overrides (e.g. npu:0)."""
    import torch

    if config and config.get("device"):
        device = torch.device(str(config["device"]))
        _maybe_init_npu(device)
        return device

    if _npu_available():
        device = torch.device("npu:0")
        _maybe_init_npu(device)
        return device
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


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
    try:
        import torch_npu  # noqa: F401
    except ImportError as e:
        raise RuntimeError("device is npu but torch_npu is not installed") from e
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
