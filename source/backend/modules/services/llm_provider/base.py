from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class LLMResponse:
    """Container for raw LLM response content."""

    content: str
    provider: str
    model: str
    cache_hit: bool = False


class LLMProvider(ABC):
    """Abstract interface all LLM providers must implement."""

    name: str

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        image: Optional[str] = None,
        language: str = "zh-TW",
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate content from the provider."""

    @property
    def default_model(self) -> Optional[str]:
        return self.config.get("model")

    @property
    def supports_images(self) -> bool:
        return bool(self.config.get("supports_images", True))
