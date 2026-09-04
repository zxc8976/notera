#!/usr/bin/env python3
"""
Collect CPU / RAM / Disk / GPU information and dump to docs/infra reports.

Usage:
  python ops/scripts/collect_system_info.py [--output docs/infra/system_report.json]
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

try:
    import psutil  # type: ignore
except ImportError:
    psutil = None

try:
    import pynvml  # type: ignore
except ImportError:
    pynvml = None


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True).strip()
    except Exception as exc:  # pragma: no cover
        return f"error: {exc}"


def collect_cpu() -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "hostname": socket.gethostname(),
    }
    if psutil:
        info.update(
            {
                "physical_cores": psutil.cpu_count(logical=False),
                "logical_cores": psutil.cpu_count(logical=True),
                "current_freq_mhz": getattr(psutil.cpu_freq(), "current", None),
                "load": psutil.getloadavg() if hasattr(psutil, "getloadavg") else None,
            }
        )
    return info


def collect_memory() -> Dict[str, Any]:
    if not psutil:
        return {"error": "psutil not available"}
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "total_gb": round(vm.total / 1024**3, 2),
        "available_gb": round(vm.available / 1024**3, 2),
        "percent": vm.percent,
        "swap_total_gb": round(swap.total / 1024**3, 2),
        "swap_used_gb": round(swap.used / 1024**3, 2),
        "swap_percent": swap.percent,
    }


def collect_disk(path: str = "/") -> Dict[str, Any]:
    usage = shutil.disk_usage(path)
    return {
        "mount": path,
        "total_gb": round(usage.total / 1024**3, 2),
        "used_gb": round(usage.used / 1024**3, 2),
        "free_gb": round(usage.free / 1024**3, 2),
    }


def collect_gpu() -> Dict[str, Any]:
    if pynvml is None:
        return {"available": False, "error": "pynvml not installed"}
    try:
        pynvml.nvmlInit()
    except Exception as exc:  # pragma: no cover
        return {"available": False, "error": str(exc)}

    device_count = pynvml.nvmlDeviceGetCount()
    devices = []
    for idx in range(device_count):
        handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
        memory = pynvml.nvmlDeviceGetMemoryInfo(handle)
        devices.append(
            {
                "index": idx,
                "name": pynvml.nvmlDeviceGetName(handle).decode(),
                "total_gb": round(memory.total / 1024**3, 2),
                "free_gb": round(memory.free / 1024**3, 2),
                "used_gb": round(memory.used / 1024**3, 2),
                "driver_version": pynvml.nvmlSystemGetDriverVersion().decode(),
                "cuda_version": _run(["nvidia-smi", "--query-gpu=cuda_version", "--format=csv,noheader"]).splitlines()[0]
                if shutil.which("nvidia-smi")
                else None,
            }
        )
    pynvml.nvmlShutdown()
    return {"available": bool(devices), "devices": devices}


def collect_summary() -> Dict[str, Any]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cpu": collect_cpu(),
        "memory": collect_memory(),
        "disk": {
            "root": collect_disk("/"),
            "workspace": collect_disk(str(Path.cwd().resolve().anchor or "/")),
        },
        "gpu": collect_gpu(),
        "env": {
            "CUDA_VISIBLE_DEVICES": os.getenv("CUDA_VISIBLE_DEVICES"),
            "NVIDIA_VISIBLE_DEVICES": os.getenv("NVIDIA_VISIBLE_DEVICES"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect system resource information.")
    default_output = Path("docs/infra") / f"system_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    parser.add_argument("--output", "-o", type=Path, default=default_output, help="Output JSON path")
    args = parser.parse_args()

    report = collect_summary()
    output_path: Path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[collect_system_info] report written to {output_path}")


if __name__ == "__main__":
    main()
