import importlib
import logging
from dataclasses import dataclass
from typing import Callable, Dict, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PromptBundle:
    """Container for prompt factories used across note generation."""

    image_prompt: Callable[..., str]
    video_prompt: Callable[..., str]


PROMPT_SETS: Dict[str, Dict[str, str]] = {
    "legacy": {
        "image_prompt": "modules.llm_prompts_optimized:get_optimized_image_note_prompt",  # 回退到優化版
        "video_prompt": "modules.detailed_note_prompts:build_detailed_prompt",  # 回退到詳細版
    },
    "optimized": {
        "image_prompt": "modules.llm_prompts_optimized:get_optimized_image_note_prompt",
        "video_prompt": "modules.llm_prompts_optimized:get_optimized_image_note_prompt",
    },
}


def _import_callable(path: str) -> Callable:
    module_path, attribute = path.split(":")
    module = importlib.import_module(module_path)
    return getattr(module, attribute)


def resolve_prompt_bundle(config: Dict) -> Tuple[PromptBundle, str]:
    """
    Pick prompt bundle according to runtime configuration.

    Preference order:
    1. config['output']['prompt_profile']
    2. config['output']['use_optimized_format'] -> 'optimized'
    3. fallback to 'legacy'
    """

    output_cfg = (config or {}).get("output", {}) if config else {}
    requested = output_cfg.get("prompt_profile")

    if not requested:
        requested = "optimized" if output_cfg.get("use_optimized_format") else "legacy"

    if requested not in PROMPT_SETS:
        logger.warning(
            "[PromptRegistry] Unknown prompt profile '%s', falling back to legacy",
            requested,
        )
        requested = "legacy"

    callable_map = {
        key: _import_callable(path) for key, path in PROMPT_SETS[requested].items()
    }

    bundle = PromptBundle(
        image_prompt=callable_map["image_prompt"],
        video_prompt=callable_map["video_prompt"],
    )
    return bundle, requested
