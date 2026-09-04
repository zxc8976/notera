"""Utilities for releasing GPU caches after heavy inference stages."""
from __future__ import annotations

import gc
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def _torch_memory_snapshot() -> Dict[str, Optional[int]]:
    """Capture current torch CUDA allocation metrics if available."""
    snapshot: Dict[str, Optional[int]] = {}
    try:
        import torch

        if torch.cuda.is_available():
            device = torch.cuda.current_device()
            snapshot["device"] = device
            snapshot["allocated"] = torch.cuda.memory_allocated(device)
            snapshot["reserved"] = torch.cuda.memory_reserved(device)
        else:
            snapshot["device"] = None
            snapshot["allocated"] = 0
            snapshot["reserved"] = 0
    except Exception as exc:  # pragma: no cover - optional dependency
        snapshot["error"] = str(exc)
    return snapshot


def release_cuda_cache(reason: str | None = None, *, log_usage: bool = True) -> None:
    """Attempt to free cached CUDA memory for both Paddle and PyTorch."""
    before = _torch_memory_snapshot() if log_usage else None
    freed = []
    try:
        import paddle

        if paddle.device.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0:
            paddle.device.cuda.empty_cache()
            freed.append("paddle")
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.debug("[GPU] paddle empty_cache failed: %s", exc)

    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            freed.append("torch")
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.debug("[GPU] torch empty_cache failed: %s", exc)

    gc.collect()
    after = _torch_memory_snapshot() if log_usage else None

    if freed:
        logger.debug("[GPU] Released caches for %s (%s)", ",".join(freed), reason or "no reason given")

    if log_usage and before and after and not before.get("error") and not after.get("error"):
        logger.info(
            "[GPU] release_cuda_cache(%s) allocated %s → %s bytes, reserved %s → %s bytes",
            reason or "-",
            before.get("allocated"),
            after.get("allocated"),
            before.get("reserved"),
            after.get("reserved"),
        )


def prepare_llm_inference(stage: str) -> None:
    """Release caches and log usage before invoking an LLM."""
    release_cuda_cache(reason=f"before_llm:{stage}")
