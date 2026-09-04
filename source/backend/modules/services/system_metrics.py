"""Host-level system metrics collection utilities."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover - psutil may be absent in tests
    psutil = None  # type: ignore

try:
    import pynvml  # type: ignore
except ImportError:  # pragma: no cover - NVML optional
    pynvml = None  # type: ignore


def _round(value: Optional[float], digits: int = 1) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except Exception:
        return None


def _collect_cpu() -> Dict[str, Any]:
    if not psutil:
        return {"percent": None, "per_cpu": [], "load_avg": None}

    per_cpu = psutil.cpu_percent(interval=0.1, percpu=True)
    avg = sum(per_cpu) / len(per_cpu) if per_cpu else psutil.cpu_percent(interval=None)

    load_avg = None
    if hasattr(os, "getloadavg"):
        try:
            load_avg = os.getloadavg()
        except OSError:
            load_avg = None

    return {
        "percent": _round(avg),
        "per_cpu": [_round(v) for v in per_cpu] if per_cpu else [],
        "load_avg": load_avg,
    }


def _collect_ram() -> Dict[str, Any]:
    if not psutil:
        return {"percent": None, "total_mb": None, "used_mb": None, "available_mb": None}
    vm = psutil.virtual_memory()
    return {
        "percent": _round(vm.percent),
        "total_mb": _round(vm.total / (1024 * 1024), 1),
        "used_mb": _round(vm.used / (1024 * 1024), 1),
        "available_mb": _round(vm.available / (1024 * 1024), 1),
    }


def _collect_swap() -> Dict[str, Any]:
    if not psutil:
        return {"percent": None, "total_mb": None, "used_mb": None}
    sm = psutil.swap_memory()
    return {
        "percent": _round(sm.percent),
        "total_mb": _round(sm.total / (1024 * 1024), 1),
        "used_mb": _round(sm.used / (1024 * 1024), 1),
    }


def _collect_gpu_via_nvml() -> Tuple[List[Dict[str, Any]], Optional[str]]:
    if not pynvml:
        return [], "pynvml_missing"
    try:
        pynvml.nvmlInit()
    except Exception as exc:  # pragma: no cover - NVML init may fail
        return [], f"nvml_init_failed:{exc}"

    gpus: List[Dict[str, Any]] = []
    try:
        count = pynvml.nvmlDeviceGetCount()
        for index in range(count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(index)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            temp = pynvml.nvmlDeviceGetTemperature(
                handle, pynvml.NVML_TEMPERATURE_GPU
            )
            name = pynvml.nvmlDeviceGetName(handle)
            gpus.append(
                {
                    "index": index,
                    "name": name.decode("utf-8") if isinstance(name, bytes) else name,
                    "util_percent": _round(util.gpu),
                    "mem_percent": _round(util.memory),
                    "mem_mb": {
                        "used": _round(mem.used / (1024 * 1024), 1),
                        "total": _round(mem.total / (1024 * 1024), 1),
                    },
                    "temp_c": _round(temp),
                }
            )
    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:  # pragma: no cover - ignore
            pass
    return gpus, None


def _collect_gpu_via_nvidia_smi() -> Tuple[List[Dict[str, Any]], Optional[str]]:
    query = ",".join(
        [
            "index",
            "name",
            "utilization.gpu",
            "utilization.memory",
            "memory.total",
            "memory.used",
            "temperature.gpu",
        ]
    )
    cmd = ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"]
    try:
        proc = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception as exc:
        return [], f"nvidia_smi_failed:{exc}"

    gpus: List[Dict[str, Any]] = []
    for line in proc.stdout.strip().splitlines():
        if not line:
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 7:
            continue
        try:
            index = int(parts[0])
        except ValueError:
            index = None
        gpus.append(
            {
                "index": index,
                "name": parts[1],
                "util_percent": _round(parts[2]),
                "mem_percent": _round(parts[3]),
                "mem_mb": {
                    "total": _round(parts[4]),
                    "used": _round(parts[5]),
                },
                "temp_c": _round(parts[6]),
            }
        )
    return gpus, None


def _collect_gpu() -> Tuple[List[Dict[str, Any]], Optional[str]]:
    gpus, error = _collect_gpu_via_nvml()
    if gpus:
        return gpus, error
    return _collect_gpu_via_nvidia_smi()


def _disk_usage_for(path: Path) -> Dict[str, Any]:
    try:
        resolved = path.resolve()
    except Exception:
        resolved = path

    if not resolved.exists():
        return {
            "path": str(resolved),
            "status": "missing",
        }

    try:
        if psutil:
            usage = psutil.disk_usage(str(resolved))
        else:
            usage = shutil.disk_usage(str(resolved))
    except Exception as exc:
        return {"path": str(resolved), "status": "error", "error": str(exc)}

    return {
        "path": str(resolved),
        "status": "ok",
        "percent": _round(usage.used / usage.total * 100) if usage.total else None,
        "free_gb": _round(usage.free / (1024 * 1024 * 1024), 2),
        "total_gb": _round(usage.total / (1024 * 1024 * 1024), 2),
    }


def resolve_monitored_paths() -> Dict[str, str]:
    base_dir = Path(os.getenv("NOTEGEN_ROOT", Path.cwd()))
    mapping: Dict[str, str] = {
        "data": os.getenv("NOTEGEN_DATA_DIR", str(base_dir / "data")),
        "logs": os.getenv("NOTEGEN_LOG_DIR", str(base_dir / "logs")),
        "media": os.getenv("NOTEGEN_MEDIA_DIR", str(base_dir / "media")),
    }
    return {key: value for key, value in mapping.items() if value}


def _collect_application_metrics() -> Dict[str, Any]:
    process_info: Dict[str, Any] = {}
    if psutil:
        try:
            proc = psutil.Process(os.getpid())
            with proc.oneshot():
                process_info = {
                    "pid": proc.pid,
                    "rss_mb": _round(proc.memory_info().rss / (1024 * 1024), 1),
                    "cpu_percent": _round(proc.cpu_percent(interval=None)),
                    "threads": proc.num_threads(),
                    "open_files": len(proc.open_files()),
                }
        except Exception:
            process_info = {}
    return process_info


def capture_snapshot(
    monitored_paths: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    timestamp = time.time()
    host_cpu = _collect_cpu()
    host_ram = _collect_ram()
    host_swap = _collect_swap()
    gpu_metrics, gpu_error = _collect_gpu()

    paths = monitored_paths or resolve_monitored_paths()
    disks = {
        label: _disk_usage_for(Path(path))
        for label, path in paths.items()
    }

    missing: List[str] = []
    if host_cpu["percent"] is None:
        missing.append("cpu")
    if host_ram["percent"] is None:
        missing.append("ram")
    if not gpu_metrics:
        missing.append("gpu")
    if host_swap["percent"] is None:
        missing.append("swap")

    summary = {
        "cpu_percent": host_cpu["percent"],
        "ram_percent": host_ram["percent"],
        "gpu_util_percent": gpu_metrics[0]["util_percent"] if gpu_metrics else None,
        "gpu_mem_used_mb": (
            gpu_metrics[0]["mem_mb"]["used"] if gpu_metrics else None
        ),
        "gpu_mem_total_mb": (
            gpu_metrics[0]["mem_mb"]["total"] if gpu_metrics else None
        ),
    }

    snapshot: Dict[str, Any] = {
        "ts": timestamp,
        "timestamp": datetime.utcnow().isoformat(),
        "host": {
            "cpu": host_cpu,
            "ram": host_ram,
            "swap": host_swap,
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
            },
        },
        "gpu": gpu_metrics,
        "disk": disks,
        "application": _collect_application_metrics(),
        "status": "ok" if not missing else "degraded",
        "missing": missing,
        "gpu_error": gpu_error,
        "summary": summary,
    }
    return snapshot


def snapshot_to_json(snapshot: Dict[str, Any]) -> str:
    return json.dumps(snapshot, ensure_ascii=False)

