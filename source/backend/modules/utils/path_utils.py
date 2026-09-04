"""Utility helpers for mapping host paths to container paths.

Provides consistent conversions for Windows host paths (e.g. ``F:/`` and
``C:/``) to the Docker container mount points used in this project. The helper
also normalises path separators and expands environment variables so backend
endpoints can share one implementation.
"""
from __future__ import annotations

import os
import posixpath
from typing import Dict, Optional, Tuple

_HOST_TO_CONTAINER: Dict[str, str] = {
    "F:/": "/app/data/external/f/",
    "f:/": "/app/data/external/f/",
    "/mnt/f/": "/app/data/external/f/",
    "C:/": "/app/data/external/c/",
    "c:/": "/app/data/external/c/",
    "/mnt/c/": "/app/data/external/c/",
}


def normalize_host_path(path: Optional[str]) -> str:
    """Expand environment variables and normalise slashes for a host path."""
    if not path:
        return ""
    expanded = os.path.expandvars(path)
    return expanded.replace("\\", "/")


def resolve_container_path(path: Optional[str], fallback_root: Optional[str] = None) -> Tuple[str, str]:
    """Convert a host path into the container-mapped path.

    Returns a tuple ``(container_path, normalized_host_path)``. If the incoming
    path is empty, both values will be empty strings.
    """
    normalized = normalize_host_path(path)
    if not normalized:
        return "", ""

    for prefix, mount in _HOST_TO_CONTAINER.items():
        if normalized.startswith(prefix):
            return normalized.replace(prefix, mount, 1), normalized

    if normalized.startswith("/"):
        # Already a container path (absolute)
        return normalized, normalized

    if fallback_root:
        fallback = fallback_root.rstrip("/") or "/app"
        relative = normalized.lstrip("./")
        return posixpath.join(fallback, relative), normalized

    return normalized, normalized


def describe_mount(path: Optional[str]) -> str:
    """Return a human-friendly description of the mount used for *path*."""
    normalized = normalize_host_path(path)
    if not normalized:
        return ""
    for prefix, mount in _HOST_TO_CONTAINER.items():
        if normalized.startswith(prefix):
            return f"{mount} (from {prefix})"
    if normalized.startswith("/"):
        return normalized
    return f"/app/{normalized.lstrip('./')}"


__all__ = [
    "normalize_host_path",
    "resolve_container_path",
    "describe_mount",
]
