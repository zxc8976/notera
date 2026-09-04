"""Media path management service.

This module centralises loading and saving of ``paths_config.json`` as well as
host/container path resolution for video and image libraries.  It replaces the
previous ad-hoc helpers inside ``main.py`` so that both API routes and
background workers can share the same logic.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence

from modules.utils.path_utils import normalize_host_path, resolve_container_path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_PATH_CANDIDATES: Sequence[str] = (
    "/app/source/backend/app/paths_config.json",
    str(_BACKEND_ROOT / "app" / "paths_config.json"),
    "/app/paths_config.json",
    "paths_config.json",
    "/app/data/paths_config.json",
    "/tmp/paths_config.json",
)


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)


@dataclass
class PathResolution:
    """Stores the resolution information for a host path."""

    raw_path: str
    container_path: str
    normalized_path: str
    accessible_path: Optional[str]
    file_count: int = 0

    def as_response_payload(self) -> Dict[str, object]:
        return {
            "path": self.raw_path,
            "container_path": self.container_path,
            "normalized_path": self.normalized_path,
            "resolved_path": self.accessible_path,
            "file_count": self.file_count,
        }


class MediaPathService:
    """Handles media path configuration and resolution."""

    def __init__(self, path_candidates: Sequence[str] | None = None) -> None:
        self._path_candidates = tuple(path_candidates or _PATH_CANDIDATES)
        self._paths: Dict[str, str] = {"video_path": "", "image_path": ""}
        self.refresh()

    # ------------------------------------------------------------------
    # public properties
    # ------------------------------------------------------------------
    @property
    def paths_config(self) -> Dict[str, str]:
        return self._paths

    def get(self, key: str, default: str = "") -> str:
        return self._paths.get(key, default)

    # ------------------------------------------------------------------
    # configuration management
    # ------------------------------------------------------------------
    def refresh(self) -> Dict[str, str]:
        self._paths = self._read_paths_config()
        return self._paths

    def save(self) -> None:
        self._write_paths_config(self._paths)

    def set_path(self, key: str, value: str) -> None:
        self._paths[key] = value
        self.save()

    # ------------------------------------------------------------------
    # resolution helpers
    # ------------------------------------------------------------------
    def resolve(self, raw_path: str) -> PathResolution:
        container_path, _ = resolve_container_path(raw_path, fallback_root="/app")
        normalized_path = normalize_host_path(raw_path)
        candidates = self._unique_candidates(container_path, normalized_path)
        accessible_path = self._first_existing(candidates)
        return PathResolution(
            raw_path=raw_path,
            container_path=container_path,
            normalized_path=normalized_path,
            accessible_path=accessible_path,
        )

    def set_media_path(self, key: str, raw_path: str, extensions: Iterable[str]) -> PathResolution:
        resolution = self.resolve(raw_path)
        if resolution.accessible_path and os.path.isdir(resolution.accessible_path):
            resolution.file_count = self._count_files(resolution.accessible_path, tuple(extensions))
        self.set_path(key, raw_path)
        return resolution

    def validate_media_path(self, raw_path: str, extensions: Iterable[str]) -> PathResolution:
        resolution = self.resolve(raw_path)
        if resolution.accessible_path and os.path.isdir(resolution.accessible_path):
            resolution.file_count = self._count_files(resolution.accessible_path, tuple(extensions))
        return resolution

    def accessible_path(self, raw_path: str) -> Optional[str]:
        return self.resolve(raw_path).accessible_path

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------
    def _read_paths_config(self) -> Dict[str, str]:
        for path in self._path_candidates:
            try:
                if os.path.isdir(path):
                    continue
                if os.path.isfile(path):
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            return json.load(f)
                    except json.JSONDecodeError:
                        with open(path, "r", encoding="utf-8-sig") as f:
                            return json.load(f)
            except Exception:
                continue
        return {"video_path": "", "image_path": ""}

    def _write_paths_config(self, config: Dict[str, str]) -> None:
        last_err: Exception | None = None
        for path in self._path_candidates:
            try:
                if os.path.isdir(path):
                    continue
                _ensure_parent(path)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                return
            except Exception as exc:  # pragma: no cover - best effort across candidates
                last_err = exc
                continue
        if last_err:
            raise last_err

    @staticmethod
    def _unique_candidates(*paths: str) -> Sequence[str]:
        seen = set()
        ordered = []
        for path in paths:
            if not path:
                continue
            if path not in seen:
                ordered.append(path)
                seen.add(path)
        return tuple(ordered)

    @staticmethod
    def _first_existing(paths: Sequence[str]) -> Optional[str]:
        for path in paths:
            if path and os.path.exists(path):
                return path
        return None

    @staticmethod
    def _count_files(root: str, extensions: Sequence[str]) -> int:
        count = 0
        for current_root, _dirs, files in os.walk(root):
            for file in files:
                if any(file.lower().endswith(ext) for ext in extensions):
                    count += 1
        return count


_default_service: Optional[MediaPathService] = None


def get_media_path_service(force_refresh: bool = False) -> MediaPathService:
    """Return the shared MediaPathService instance."""
    global _default_service
    if _default_service is None:
        _default_service = MediaPathService()
    elif force_refresh:
        _default_service.refresh()
    return _default_service


def set_media_path_service(service: Optional[MediaPathService]) -> None:
    """Inject a MediaPathService for testing or specialised contexts."""
    global _default_service
    _default_service = service


__all__ = [
    "MediaPathService",
    "PathResolution",
    "get_media_path_service",
    "set_media_path_service",
]
