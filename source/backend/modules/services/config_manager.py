"""Centralised configuration loading and runtime acceleration detection."""
from __future__ import annotations

import copy
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

LOGGER = logging.getLogger(__name__)
_CONFIG_LOCK = threading.RLock()
_CONFIG_CACHE: Optional[Dict[str, Any]] = None
_RUNTIME_CACHE: Optional[Dict[str, Any]] = None
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = _BACKEND_ROOT / "app" / "config.yaml"


def load_config(force_reload: bool = False) -> Dict[str, Any]:
    """Load configuration and enrich with runtime metadata."""
    global _CONFIG_CACHE, _RUNTIME_CACHE
    with _CONFIG_LOCK:
        if _CONFIG_CACHE is None or force_reload:
            if not _CONFIG_PATH.exists():
                raise FileNotFoundError(f"config.yaml not found at {_CONFIG_PATH}")
            with _CONFIG_PATH.open("r", encoding="utf-8") as handle:
                config = yaml.safe_load(handle) or {}
            config = _apply_defaults(config)
            runtime = _detect_runtime(config)
            config["_runtime"] = runtime
            _CONFIG_CACHE = config
            _RUNTIME_CACHE = runtime
        return copy.deepcopy(_CONFIG_CACHE)


def save_config(config: Dict[str, Any]) -> None:
    """Persist configuration to disk and refresh cache."""
    global _CONFIG_CACHE, _RUNTIME_CACHE
    with _CONFIG_LOCK:
        sanitized = copy.deepcopy(config)
        sanitized.pop("_runtime", None)
        for key in [k for k in sanitized.keys() if isinstance(k, str) and k.startswith("_")]:
            sanitized.pop(key, None)

        llm_cfg = sanitized.get("llm")
        if isinstance(llm_cfg, dict):
            scene = llm_cfg.get("scene_model")
            image = llm_cfg.get("image_model")
            final = llm_cfg.get("final_model")
            dedup_models = sorted({m for m in (scene, image, final) if m})

            ollama_cfg = llm_cfg.get("ollama")
            if isinstance(ollama_cfg, dict):
                models = ollama_cfg.get("models")
                if not models and dedup_models:
                    ollama_cfg["models"] = dedup_models

        with _CONFIG_PATH.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(sanitized, handle, allow_unicode=True, sort_keys=False)

        load_config(force_reload=True)


def refresh_runtime() -> Dict[str, Any]:
    """Re-run runtime probing against the cached configuration."""
    with _CONFIG_LOCK:
        if _CONFIG_CACHE is None:
            load_config(force_reload=True)
        else:
            runtime = _detect_runtime(_CONFIG_CACHE)
            _CONFIG_CACHE["_runtime"] = runtime
            _RUNTIME_CACHE = runtime
        return copy.deepcopy(_RUNTIME_CACHE)


def get_runtime_state() -> Dict[str, Any]:
    """Return the latest runtime detection state."""
    with _CONFIG_LOCK:
        if _RUNTIME_CACHE is None:
            refresh_runtime()
        return copy.deepcopy(_RUNTIME_CACHE)


def runtime_summary() -> Dict[str, Any]:
    """Return a compact summary of runtime acceleration state."""
    runtime = get_runtime_state()
    return {
        "requested_device": runtime.get("requested_device"),
        "active_device": runtime.get("active_device"),
        "fallback_reason": runtime.get("fallback_reason"),
        "prefer_gpu": runtime.get("prefer_gpu"),
        "ocr": runtime.get("ocr"),
        "vlm": runtime.get("vlm"),
        "torch": {
            "available": runtime.get("torch", {}).get("available", False),
            "version": runtime.get("torch", {}).get("version"),
        },
        "paddle": {
            "available": runtime.get("paddle", {}).get("available", False),
            "version": runtime.get("paddle", {}).get("version"),
        },
        "timestamp": runtime.get("timestamp"),
    }


def _apply_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    runtime_cfg = config.setdefault("runtime", {})
    runtime_cfg.setdefault("prefer_gpu", True)
    runtime_cfg.setdefault("fallback_to_cpu", True)
    runtime_cfg.setdefault("gpu_device", 0)
    runtime_cfg.setdefault("log_summary", True)
    thermal_cfg = runtime_cfg.setdefault("thermal_guard", {})
    thermal_cfg.setdefault("warn_temp_c", 80)
    thermal_cfg.setdefault("force_temp_c", 85)
    thermal_cfg.setdefault("recover_temp_c", 75)
    thermal_cfg.setdefault("sustain_seconds", 30)
    thermal_cfg.setdefault("check_interval_sec", 5)
    thermal_cfg.setdefault("ocr_batch_reduction_ratio", 0.5)
    thermal_cfg.setdefault("min_ocr_batch_size", 2)
    thermal_cfg.setdefault("max_concurrency_cap", 4)

    system_cfg = config.setdefault("system", {})
    system_cfg.setdefault("num_workers", 4)

    ocr_cfg = config.setdefault("ocr", {})
    ocr_cfg.setdefault("enabled", True)
    ocr_cfg.setdefault("engine", "paddleocr-vl")
    ocr_cfg.setdefault("primary_lang", "japan")
    ocr_cfg.setdefault("languages", ["japan", "ch", "en"])
    ocr_cfg.setdefault("use_gpu", "auto")
    ocr_cfg.setdefault("device_id", runtime_cfg.get("gpu_device", 0))
    ocr_cfg.setdefault("batch_size", 8)
    ocr_cfg.setdefault("enable_angle_cls", True)
    ocr_cfg.setdefault("min_confidence", 0.35)
    layout_cfg = ocr_cfg.setdefault("layout", {})
    layout_cfg.setdefault("enabled", True)
    layout_cfg.setdefault("ocr_version", "PP-OCRv5")
    layout_cfg.setdefault("detect_tables", True)
    layout_cfg.setdefault("score_threshold", 0.3)
    model_root_env = os.getenv("PADDLEOCR_VL_MODEL_ROOT")
    if model_root_env:
        ocr_cfg["model_root"] = model_root_env
        layout_cfg.setdefault("model_dir", os.path.join(model_root_env, "PP-DocLayoutV2"))
    layout_dir_env = os.getenv("PADDLEOCR_VL_LAYOUT_DIR")
    if layout_dir_env:
        layout_cfg["model_dir"] = layout_dir_env

    llm_cfg = config.setdefault("llm", {})
    llm_cfg.setdefault("prefer_gpu", runtime_cfg.get("prefer_gpu", True))
    llm_cfg.setdefault("provider", os.getenv("LLM_PROVIDER", llm_cfg.get("provider", "ollama")))

    ollama_cfg = llm_cfg.setdefault("ollama", {})
    ollama_cfg.setdefault("base_url", os.getenv("OLLAMA_BASE", ollama_cfg.get("base_url", "http://ollama:11434")))
    ollama_cfg.setdefault("timeout", ollama_cfg.get("timeout", llm_cfg.get("timeout", 600)))
    ollama_cfg.setdefault("supports_images", True)
    ollama_cfg.setdefault("title", ollama_cfg.get("title", "Ollama Qwen3-VL-3B"))
    if "models" not in ollama_cfg:
        models = [llm_cfg.get("scene_model"), llm_cfg.get("image_model"), llm_cfg.get("final_model")]
        ollama_cfg["models"] = sorted({m for m in models if m})

    qwen_model_env = os.getenv("QWEN_VL_MODEL")
    if qwen_model_env:
        llm_cfg["scene_model"] = qwen_model_env
        llm_cfg["image_model"] = qwen_model_env
        llm_cfg["final_model"] = qwen_model_env

    return config


def _detect_runtime(config: Dict[str, Any]) -> Dict[str, Any]:
    runtime_cfg = config.get("runtime", {})
    prefer_gpu = bool(runtime_cfg.get("prefer_gpu", True))
    fallback = bool(runtime_cfg.get("fallback_to_cpu", True))
    device_id = int(runtime_cfg.get("gpu_device", 0) or 0)

    ocr_cfg = config.setdefault("ocr", {})
    ocr_use_raw = ocr_cfg.get("use_gpu")
    ocr_mode = "auto"
    if ocr_use_raw is None:
        ocr_mode = "auto"
        ocr_cfg["use_gpu"] = ocr_mode
    elif isinstance(ocr_use_raw, str):
        ocr_mode = ocr_use_raw.strip().lower()
    elif isinstance(ocr_use_raw, bool):
        ocr_mode = "gpu" if ocr_use_raw else "cpu"
    else:
        ocr_mode = "gpu" if bool(ocr_use_raw) else "cpu"
    ocr_cfg.setdefault("device_id", device_id)
    ocr_wants_gpu = (ocr_mode in {"auto", "gpu", "true", "1", "yes", "on"})

    llm_cfg = config.setdefault("llm", {})
    if "prefer_gpu" not in llm_cfg:
        llm_cfg["prefer_gpu"] = prefer_gpu
    llm_prefer_gpu = bool(llm_cfg.get("prefer_gpu", prefer_gpu))

    torch_info: Dict[str, Any] = {"available": False}
    paddle_info: Dict[str, Any] = {"available": False}

    cuda_env = {
        "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "NVIDIA_VISIBLE_DEVICES": os.environ.get("NVIDIA_VISIBLE_DEVICES"),
    }

    gpu_ok = False
    if prefer_gpu:
        try:
            import torch

            torch_info["version"] = torch.__version__
            torch_info["available"] = torch.cuda.is_available()
            torch_info["device_count"] = torch.cuda.device_count() if torch_info["available"] else 0
            gpu_ok = gpu_ok or torch_info["available"]
        except Exception as exc:  # pragma: no cover - torch missing
            torch_info["error"] = str(exc)

        try:
            import paddle

            paddle_info["version"] = paddle.__version__
            paddle_info["compiled_with_cuda"] = paddle.device.is_compiled_with_cuda()
            paddle_info["device_count"] = (
                paddle.device.cuda.device_count() if paddle_info["compiled_with_cuda"] else 0
            )
            paddle_info["available"] = (
                paddle_info.get("compiled_with_cuda") and paddle_info.get("device_count", 0) > 0
            )
            if paddle_info["available"]:
                try:
                    paddle.device.set_device(f"gpu:{device_id}")
                except Exception as exc:  # pragma: no cover - ignore binding failure
                    paddle_info["set_device_error"] = str(exc)
            gpu_ok = gpu_ok or paddle_info["available"]
        except Exception as exc:  # pragma: no cover - paddle missing
            paddle_info["error"] = str(exc)

    active_device = "gpu" if (prefer_gpu and gpu_ok) else "cpu"
    fallback_reason = None
    if prefer_gpu and active_device != "gpu":
        fallback_reason = "cuda_unavailable"
        if not fallback:
            LOGGER.warning(
                "GPU requested in configuration but CUDA runtime unavailable."
                " Continuing in CPU mode because fallback_to_cpu is disabled."
            )

    # Align OCR device with computed decision (OCR may opt out even if runtime uses GPU)
    ocr_device = "gpu" if (ocr_wants_gpu and gpu_ok) else "cpu"
    ocr_fallback_reason = None
    if ocr_wants_gpu and ocr_device != "gpu":
        ocr_fallback_reason = "cuda_unavailable"
    ocr_cfg["device_id"] = device_id if ocr_device == "gpu" else None

    provider_name = (llm_cfg.get("provider") or "ollama").lower()
    if provider_name != "ollama":
        LOGGER.warning(
            "Unsupported LLM provider '%s' detected in configuration; defaulting to Ollama (qwen3-vl:4b).",
            provider_name,
        )
        provider_name = "ollama"
        llm_cfg["provider"] = "ollama"
    ollama_cfg = llm_cfg.get("ollama", {})
    provider_base = ollama_cfg.get("base_url")
    provider_notes = (
        "Ollama manages GPU execution outside this container; "
        "set llm.prefer_gpu=false to indicate CPU execution."
    )

    runtime = {
        "prefer_gpu": prefer_gpu,
        "fallback_to_cpu": fallback,
        "requested_device": "gpu" if prefer_gpu else "cpu",
        "active_device": active_device,
        "fallback_reason": fallback_reason,
        "timestamp": datetime.utcnow().isoformat(),
        "torch": torch_info,
        "paddle": paddle_info,
        "cuda_env": cuda_env,
        "ocr": {
            "device": ocr_device,
            "requested_device": "gpu" if ocr_wants_gpu else "cpu",
            "device_id": device_id if ocr_device == "gpu" else None,
            "fallback_reason": ocr_fallback_reason,
        },
        "vlm": {
            "driver": provider_name,
            "mode": "gpu" if llm_prefer_gpu else "cpu",
            "requested_device": "gpu" if llm_prefer_gpu else "cpu",
            "base_url": provider_base,
            "notes": provider_notes,
        },
    }

    if prefer_gpu and active_device != "gpu":
        LOGGER.warning(
            "CUDA device not detected; PaddleOCR-VL will run in CPU mode. "
            "torch_cuda=%s paddle_cuda=%s env=%s",
            torch_info.get("available"),
            paddle_info.get("available"),
            cuda_env,
        )
    elif active_device == "gpu" and runtime_cfg.get("log_summary", True):
        LOGGER.info(
            "GPU acceleration enabled (device_id=%s, torch_cuda=%s, paddle_cuda=%s)",
            device_id,
            torch_info.get("available"),
            paddle_info.get("available"),
        )

    return runtime

def is_ocr_enabled(config: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(config, dict):
        return True
    ocr_cfg = config.get("ocr")
    if not isinstance(ocr_cfg, dict):
        return True
    return bool(ocr_cfg.get("enabled", True))


__all__ = ["load_config", "refresh_runtime", "get_runtime_state", "runtime_summary", "save_config"]


