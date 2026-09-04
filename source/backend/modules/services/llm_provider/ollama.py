from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import socket
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx

from .base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, config: Dict[str, Any]) -> None:
        super().__init__(config)
        env_base = os.getenv("OLLAMA_BASE")
        configured_base = config.get("base_url")
        candidate_base = env_base or configured_base or "http://localhost:11434"
        self.base_url = self._resolve_base_url(candidate_base)
        
        # 🔧 雲端/本地自動切換配置
        self.cloud_base_url = "https://ollama.com/api"  # 雲端端點
        self.local_base_url = os.getenv("OLLAMA_FALLBACK_BASE") or "http://ollama_local:11434"  # 本地端點
        self.api_key = os.getenv("OLLAMA_API_KEY") or config.get("api_key")
        
        self.timeout = float(config.get("timeout", 180))
        self.max_retries = int(config.get("retries", 3))
        self.cache = {}
        # 全局重試保護：防止無限重試
        self.global_retry_limit = int(config.get("global_retry_limit", 10))  # 單次 generate 調用最多 10 次重試
        self.min_content_length = int(config.get("min_content_length", 5))  # 降低最小長度要求（原本是 10）
        self._call_start_time = None  # 記錄調用開始時間
        self.max_call_duration = float(config.get("max_call_duration", 600))  # 單次調用最長 10 分鐘
        # 默認 temperature (防止 LLM 過度保守而返回空內容)
        self.default_temperature = float(config.get("temperature", 0.7))

    def _resolve_base_url(self, candidate: str) -> str:
        """Resolve Ollama base URL with graceful fallback for local dev."""
        if not candidate:
            return "http://localhost:11434"
        fallback = os.getenv("OLLAMA_FALLBACK_BASE") or "http://localhost:11434"
        try:
            parsed = urlparse(candidate)
            hostname = parsed.hostname
            if not hostname:
                return candidate
            socket.gethostbyname(hostname)
            return candidate
        except Exception:
            if candidate != fallback:
                logger.warning("[OllamaProvider] base_url '%s' 無法解析，改用 '%s'", candidate, fallback)
            return fallback

    def _get_endpoint_for_model(self, model_name: str) -> tuple[str, bool]:
        """
        根據模型名稱自動選擇雲端或本地端點
        
        Args:
            model_name: 模型名稱 (例如: qwen3-vl:4b, qwen3-vl:235b-cloud)
            
        Returns:
            (endpoint_url, use_cloud): 端點URL 和 是否使用雲端推理
        """
        # 判斷是否為雲端模型 (名稱包含 'cloud' 或模型參數量 >= 100b)
        is_cloud_model = (
            '-cloud' in model_name.lower() or
            '235b' in model_name.lower() or
            '480b' in model_name.lower() or
            '120b' in model_name.lower()
        )
        
        if is_cloud_model:
            if not self.api_key:
                logger.warning(
                    "[OllamaProvider] 模型 '%s' 需要雲端推理，但未設置 OLLAMA_API_KEY，"
                    "將嘗試使用本地端點（可能會導致 GPU OOM）",
                    model_name
                )
                return self.local_base_url, False
            else:
                logger.info(
                    "[OllamaProvider] 模型 '%s' 使用雲端推理 → %s (GPU 零負載)",
                    model_name, self.cloud_base_url
                )
                return self.cloud_base_url, True
        else:
            logger.info(
                "[OllamaProvider] 模型 '%s' 使用本地推理 → %s",
                model_name, self.local_base_url
            )
            return self.local_base_url, False

    def _normalize_endpoint(self, endpoint_url: str) -> str:
        endpoint = (endpoint_url or "").rstrip("/")
        if endpoint.endswith("/api"):
            return endpoint[:-4]
        return endpoint


    async def generate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        image: Optional[str] = None,
        language: str = "zh-TW",
        use_cache: bool = True,
        cache_key: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        # 記錄調用開始時間（用於超時保護）
        self._call_start_time = time.time()
        
        model_name = model or self.default_model or "qwen3-vl:4b"
        key = cache_key or self._make_cache_key(prompt, model_name, image, language)
        if use_cache and key in self.cache:
            return LLMResponse(content=self.cache[key], provider=self.name, model=model_name, cache_hit=True)

        payload: Dict[str, Any] = {
            "model": model_name,
            "prompt": prompt,
            "options": {},
            "stream": False,
        }
        
        # 設置 options (包括默認 temperature)
        options = {}
        if extra:
            # 從 extra 參數取得設定
            for key in ("temperature", "top_p", "top_k"):
                if extra.get(key) is not None:
                    options[key] = extra[key]
            if extra.get("max_tokens") is not None:
                options["num_predict"] = extra["max_tokens"]
        
        # 如果沒有設置 temperature，使用默認值
        if "temperature" not in options:
            options["temperature"] = self.default_temperature
        
        if options:
            payload["options"] = options

        if image:
            payload["images"] = [image]

        # 🔧 根據模型名稱自動選擇雲端或本地端點
        endpoint_url, use_cloud = self._get_endpoint_for_model(model_name)
        normalized_endpoint = self._normalize_endpoint(endpoint_url)
        url = f"{normalized_endpoint}/api/generate"
        logger.info("[OllamaProvider] POST %s model=%s (雲端=%s)", url, model_name, use_cloud)
        logger.debug("[OllamaProvider] prompt length=%d image=%s", len(prompt), bool(image))


        base_delay = 3
        global_retry_count = 0  # 全局重試計數器
        
        for attempt in range(self.max_retries):
            # 超時保護：檢查總調用時間
            if self._call_start_time and (time.time() - self._call_start_time) > self.max_call_duration:
                logger.error(
                    "[OllamaProvider] 調用超時 (%.1f秒 > %.1f秒限制)，強制中斷",
                    time.time() - self._call_start_time,
                    self.max_call_duration
                )
                raise RuntimeError(f"LLM 調用超時 ({self.max_call_duration}秒)")
            
            # 全局重試保護：防止無限循環
            global_retry_count += 1
            if global_retry_count > self.global_retry_limit:
                logger.error(
                    "[OllamaProvider] 達到全局重試上限 (%d次)，強制中斷",
                    self.global_retry_limit
                )
                raise RuntimeError(f"LLM 重試次數超過限制 ({self.global_retry_limit}次)")
            
            logger.debug("[OllamaProvider] 重試 %d/%d (全局: %d/%d)", 
                        attempt + 1, self.max_retries, 
                        global_retry_count, self.global_retry_limit)
            try:
                # 🔧 只在雲端推理時添加 API 密鑰
                headers = {}
                if use_cloud and self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                    logger.debug("[OllamaProvider] 使用API密鑰進行雲端推理 (GPU零負載模式)")
                elif use_cloud and not self.api_key:
                    logger.warning("[OllamaProvider] 雲端模型但缺少API密鑰，請求可能失敗")
                
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    if response.status_code == 404:
                        logger.debug("[OllamaProvider] 404 from /api/generate, attempting /api/chat fallback")
                        chat_payload: Dict[str, Any] = {
                            "model": model_name,
                            "messages": [
                                {"role": "system", "content": f"請使用語言：{language} 回答，且保持客觀。"},
                                {"role": "user", "content": prompt},
                            ],
                        }
                        if image:
                            chat_payload["messages"][0]["content"] += " 圖片內容已另附。"
                            if self._looks_like_base64(image):
                                chat_payload["messages"][1]["content"] = [
                                    {"type": "text", "text": prompt},
                                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image}"}},
                                ]
                            else:
                                chat_payload["messages"][1]["content"] = [
                                    {"type": "text", "text": prompt},
                                    {"type": "image_url", "image_url": {"url": image}},
                                ]
                        else:
                            chat_payload["messages"][1]["content"] = prompt
                        chat_payload["stream"] = False
                        chat_url = f"{normalized_endpoint}/api/chat"
                        response = await client.post(chat_url, json=chat_payload, headers=headers)


                response.raise_for_status()
                data = response.json()
                content = self._extract_content(data)
                
                # 詳細記錄 LLM 返回結果（用於調試空內容問題）
                if not content or len(content.strip()) < self.min_content_length:
                    actual_length = len(content.strip()) if content else 0
                    logger.warning(
                        "[OllamaProvider] 內容過短 (長度=%d < 最小=%d) | 重試 %d/%d",
                        actual_length, self.min_content_length,
                        attempt + 1, self.max_retries
                    )
                    
                    # 記錄實際返回的原始數據（用於調試）
                    logger.debug("[OllamaProvider] 原始 response data keys: %s", list(data.keys()))
                    if "response" in data:
                        logger.debug("[OllamaProvider] response 欄位內容: %r", data["response"][:200] if data["response"] else "(empty)")
                    if "message" in data:
                        logger.debug("[OllamaProvider] message 欄位內容: %r", data["message"])
                    
                    # 記錄短內容預覽
                    if content:
                        logger.debug("[OllamaProvider] 短內容預覽: %r", content[:100])
                    
                    if attempt < self.max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning("[OllamaProvider] %d秒後重試... (使用 temperature=%.2f)", delay, self.default_temperature)
                        await asyncio.sleep(delay)
                        continue
                    else:
                        # 最後一次重試失敗，返回降級內容
                        logger.error("[OllamaProvider] 所有重試均失敗，返回降級內容")
                        logger.error("[OllamaProvider] 建議: 1) 檢查 Ollama 服務狀態 2) 增加 temperature 3) 簡化 prompt")
                        content = content or "⚠️ LLM 生成內容異常，請重試或檢查 Ollama 服務。"

                if use_cache:
                    self.cache[key] = content
                    if len(self.cache) > 128:
                        self.cache.pop(next(iter(self.cache)))

                return LLMResponse(content=content, provider=self.name, model=model_name, cache_hit=False)

            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as err:
                if attempt < self.max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning("[OllamaProvider] request error (%s). retrying in %ss", err, delay)
                    await asyncio.sleep(delay)
                    continue
                raise
            except httpx.HTTPStatusError as err:
                logger.error("[OllamaProvider] HTTP error %s: %s", err.response.status_code, err.response.text[:200])
                raise
            except Exception as err:
                logger.error("[OllamaProvider] unexpected error: %s", err, exc_info=True)
                if attempt < self.max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                raise

        raise RuntimeError("Ollama provider exhausted retries without success")

    def _make_cache_key(self, prompt: str, model: str, image: Optional[str], language: str) -> str:
        b64 = base64.b64encode(
            json.dumps(
                {
                    "prompt": prompt,
                    "model": model,
                    "image": image[:64] if image else None,
                    "language": language,
                },
                sort_keys=True,
            ).encode("utf-8")
        )
        return b64.decode("utf-8")

    def _extract_content(self, payload: Dict[str, Any]) -> str:
        if "response" in payload:
            return payload["response"]
        if "message" in payload and isinstance(payload["message"], dict):
            return payload["message"].get("content", "")
        if payload.get("choices"):
            return payload["choices"][0]["message"]["content"]
        logger.error("[OllamaProvider] unsupported payload structure: %s", payload)
        return ""

    def _looks_like_base64(self, value: str) -> bool:
        try:
            base64.b64decode(value, validate=True)
            return True
        except Exception:
            return False
