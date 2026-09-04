"""
統一的OCR管理模組
避免在多個地方重複初始化OCR引擎
"""
import logging
from typing import Any, Dict, List, Optional

from modules.services.paddleocr_vl import PaddleOCRVLEngine

logger = logging.getLogger(__name__)

class OCRManager:
    """統一的OCR管理器 - 單例模式"""
    
    _instance = None
    _engine_cache: Dict[str, PaddleOCRVLEngine] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def _cache_key(self, config: dict, device: str) -> str:
        ocr_cfg = (config or {}).get("ocr", {})
        lang = ocr_cfg.get("lang") or ocr_cfg.get("primary_lang") or "japan"
        use_gpu = ocr_cfg.get("use_gpu", True)
        device_id = ocr_cfg.get("device_id", 0)
        batch_size = ocr_cfg.get("batch_size", 8)
        layout_enabled = (ocr_cfg.get("layout") or {}).get("enabled", True)
        return f"{device}_{lang}_{use_gpu}_{device_id}_{batch_size}_{layout_enabled}"

    def get_engine(self, config: dict, device: str = "gpu") -> PaddleOCRVLEngine:
        cache_key = self._cache_key(config, device)
        if cache_key in self._engine_cache:
            logger.debug("[OCRManager] 使用快取 PaddleOCR-VL 引擎: %s", cache_key)
            return self._engine_cache[cache_key]

        logger.info("[OCRManager] 初始化 PaddleOCR-VL 引擎 (key=%s)", cache_key)
        engine = PaddleOCRVLEngine(config=config, device=device)
        self._engine_cache[cache_key] = engine
        return engine

    def get_ocr(self, config: dict, device: str = "gpu") -> Optional[PaddleOCRVLEngine]:
        """
        獲得OCR實例 - 支援快取以避免重複初始化
        
        Args:
            config: OCR配置
            device: 設備類型 (gpu/cpu)
            
        Returns:
            OCR實例或None
        """
        try:
            return self.get_engine(config=config, device=device)
        except Exception as e:
            logger.error(f"[OCRManager] PaddleOCR-VL 初始化失敗: {e}")
            return None
    
    def extract_text(self, image_path: str, config: dict, device: str = "gpu") -> str:
        """
        從圖片提取文字 - 統一接口
        
        Args:
            image_path: 圖片路徑
            config: OCR配置
            device: 設備類型
            
        Returns:
            提取的文字
        """
        try:
            engine = self.get_engine(config, device)
            if not engine:
                logger.warning(f"[OCRManager] OCR不可用，跳過文字提取: {image_path}")
                return ""

            structured = engine.extract_text(image_path)
            extracted_text = structured.get("text", "") if isinstance(structured, dict) else ""
            if not extracted_text:
                logger.debug(f"[OCRManager] OCR未找到文字: {image_path}")
                return ""

            logger.info(f"[OCRManager] OCR提取成功: {len(extracted_text)}字符")
            return extracted_text
            
        except Exception as e:
            logger.error(f"[OCRManager] OCR文字提取失敗: {e}")
            return ""
    
    def extract_with_meta(self, image_path: str, config: dict, device: str = "gpu") -> Dict[str, Any]:
        """擷取包含座標與置信度的 OCR 結果"""
        engine = self.get_engine(config, device)
        return engine.extract_text(image_path)

    def analyze_layout(self, image_path: str, config: dict, device: str = "gpu") -> List[Dict[str, Any]]:
        """呼叫版面分析"""
        engine = self.get_engine(config, device)
        return engine.analyze_layout(image_path)

    def clear_cache(self):
        """清除OCR快取"""
        for engine in self._engine_cache.values():
            try:
                engine.clear()
            except Exception:
                continue
        self._engine_cache.clear()
        logger.info("[OCRManager] OCR快取已清除")

# 全域OCR管理器實例
ocr_manager = OCRManager()
