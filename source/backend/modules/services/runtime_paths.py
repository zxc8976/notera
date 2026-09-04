"""Centralised workspace path utilities for the refactored repository layout."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

# Base directories -----------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SOURCE_ROOT = PROJECT_ROOT / "source"
BACKEND_ROOT = SOURCE_ROOT / "backend"
FRONTEND_ROOT = SOURCE_ROOT / "frontend"
APP_ROOT = BACKEND_ROOT / "app"
VAR_ROOT = PROJECT_ROOT / "var"
DATA_ROOT = PROJECT_ROOT / "data"
ARCHIVE_ROOT = PROJECT_ROOT / "archive"

# Runtime directories --------------------------------------------------------

OUTPUT_ROOT = VAR_ROOT / "output"
NOTES_ROOT = VAR_ROOT / "notes"
LOG_ROOT = VAR_ROOT / "log"
TMP_ROOT = VAR_ROOT / "tmp"

FRONTEND_DIST_DIR = FRONTEND_ROOT / "dist"
FRONTEND_PUBLIC_IMAGES_DIR = FRONTEND_ROOT / "public" / "images"


def ensure_runtime_dirs(extra: Iterable[Path] | None = None) -> None:
    """Ensure common runtime directories exist."""
    default_paths = (
        OUTPUT_ROOT,
        OUTPUT_ROOT / "images",
        OUTPUT_ROOT / "tmp",
        NOTES_ROOT,
        LOG_ROOT,
        TMP_ROOT,
        FRONTEND_PUBLIC_IMAGES_DIR,
    )
    for path in (*default_paths, *(extra or ())):
        path.mkdir(parents=True, exist_ok=True)


def output_path(*parts: str) -> Path:
    """Return a path under the output directory."""
    return OUTPUT_ROOT.joinpath(*parts)


def notes_path(*parts: str) -> Path:
    """Return a path under the notes directory."""
    return NOTES_ROOT.joinpath(*parts)


__all__ = [
    "PROJECT_ROOT",
    "SOURCE_ROOT",
    "BACKEND_ROOT",
    "FRONTEND_ROOT",
    "APP_ROOT",
    "VAR_ROOT",
    "DATA_ROOT",
    "ARCHIVE_ROOT",
    "OUTPUT_ROOT",
    "NOTES_ROOT",
    "LOG_ROOT",
    "TMP_ROOT",
    "FRONTEND_DIST_DIR",
    "FRONTEND_PUBLIC_IMAGES_DIR",
    "ensure_runtime_dirs",
    "output_path",
    "notes_path",
]
