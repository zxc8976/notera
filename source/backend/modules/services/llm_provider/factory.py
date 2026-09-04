from __future__ import annotations

from typing import Any, Dict

from .base import LLMProvider
from .ollama import OllamaProvider

PROVIDER_MAP = {
    "ollama": OllamaProvider,
}


def create_provider(config: Dict[str, Any]) -> LLMProvider:
    provider_name = (config.get("llm", {}).get("provider") or "ollama").lower()
    if provider_name != "ollama":
        raise ValueError(
            "Unsupported LLM provider '{0}'. The deployment now only maintains the Ollama provider "
            "with qwen3-vl:4b. To experiment with other backends, reintroduce a dedicated provider "
            "implementation in a separate change.".format(provider_name)
        )
    provider_cfg = config.get("llm", {}).get(provider_name, {})
    provider_cls = PROVIDER_MAP.get(provider_name)
    if not provider_cls:
        available = ", ".join(PROVIDER_MAP.keys())
        raise ValueError(f"Unsupported LLM provider '{provider_name}'. Available: {available}")
    return provider_cls(provider_cfg)
