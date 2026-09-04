"""Backend helper to expose shared Cornell prompt manifest."""
from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from shared.prompts import get_prompt_manifest, load_manifest, PromptManifest  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - local dev fallback
    from source.shared.prompts import get_prompt_manifest, load_manifest, PromptManifest  # type: ignore


_MANIFEST_CACHE: Optional[PromptManifest] = None


def _ensure_manifest() -> PromptManifest:
    global _MANIFEST_CACHE
    if _MANIFEST_CACHE is None:
        _MANIFEST_CACHE = load_manifest()
    return _MANIFEST_CACHE


def manifest_dict() -> Dict[str, Any]:
    """Return manifest as plain dict (copy)."""
    return get_prompt_manifest()


def manifest_hash() -> str:
    return _ensure_manifest().hash


def manifest_version() -> str:
    return _ensure_manifest().version


def manifest_id() -> str:
    return _ensure_manifest().id


def final_prompt_template() -> str:
    return _ensure_manifest().templates["final_prompt"]


def verification_prompt_template() -> str:
    return _ensure_manifest().templates["verification_prompt"]


__all__ = [
    "manifest_dict",
    "manifest_hash",
    "manifest_version",
    "manifest_id",
    "final_prompt_template",
    "verification_prompt_template",
]
