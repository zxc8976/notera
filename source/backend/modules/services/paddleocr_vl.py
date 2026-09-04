"""PaddleOCR-VL integration helpers."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned == "auto":
            return default
        return cleaned in {"1", "true", "yes", "on"}
    return bool(value)


def _int(value: Any, default: int) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _ensure_device_env(device_id: int) -> None:
    if device_id < 0:
        return
    current = os.environ.get("CUDA_VISIBLE_DEVICES")
    desired = str(device_id)
    if current == desired:
        return
    os.environ["CUDA_VISIBLE_DEVICES"] = desired
    logger.debug("[PaddleOCR-VL] CUDA_VISIBLE_DEVICES set to %s", desired)


@dataclass
class OCRLine:
    text: str
    confidence: float
    bbox: Optional[List[List[float]]]
    language: str


REPO_ROOT = Path(__file__).resolve().parents[4]


def _resolve_path(path: Optional[str]) -> Optional[Path]:
    if not path:
        return None
    p = Path(path)
    if not p.is_absolute():
        p = (REPO_ROOT / p).resolve()
    return p


class PaddleOCRVLEngine:
    """Wrapper around PaddleOCR + PP-Structure tuned for VL workflow."""

    def __init__(self, config: Dict[str, Any], device: str = "gpu") -> None:
        self.config = config or {}
        self.device = device

        ocr_config = self.config.get("ocr", {})
        self.primary_lang = ocr_config.get("primary_lang") or ocr_config.get("lang") or "japan"
        self.languages = ocr_config.get("languages") or [self.primary_lang]
        self.use_gpu = _bool(ocr_config.get("use_gpu"), device == "gpu")
        self.device_id = _int(ocr_config.get("device_id", 0), 0)
        self.rec_batch_size = _int(ocr_config.get("batch_size", 8), 8)
        self.enable_angle_cls = _bool(ocr_config.get("enable_angle_cls"), True)
        self.min_confidence = float(ocr_config.get("min_confidence", 0.35))
        try:
            import paddle  # type: ignore

            if self.use_gpu and not paddle.device.is_compiled_with_cuda():
                logger.warning(
                    "[PaddleOCR-VL] GPU requested but PaddlePaddle is CPU-only. Falling back to CPU."
                )
                self.use_gpu = False
        except Exception as paddle_exc:  # pragma: no cover
            if self.use_gpu:
                logger.warning(
                    "[PaddleOCR-VL] Unable to verify CUDA support (%s). Falling back to CPU.",
                    paddle_exc,
                )
                self.use_gpu = False

        layout_cfg = ocr_config.get("layout", {}) if isinstance(ocr_config.get("layout"), dict) else {}
        self.enable_layout = _bool(layout_cfg.get("enabled"), True)
        self.layout_detect_tables = _bool(layout_cfg.get("detect_tables"), True)
        self.layout_score_threshold = float(layout_cfg.get("score_threshold", 0.3))
        self.model_root = _resolve_path(ocr_config.get("model_root"))
        self.det_model_dir = _resolve_path(ocr_config.get("det_model_dir"))
        self.rec_model_dir = _resolve_path(ocr_config.get("rec_model_dir"))
        self.cls_model_dir = _resolve_path(ocr_config.get("cls_model_dir"))
        self.layout_model_dir = _resolve_path(layout_cfg.get("model_dir"))
        self.layout_structure_version = layout_cfg.get("structure_version", "PP-DocLayoutV2")

        try:
            if self.use_gpu:
                _ensure_device_env(self.device_id)
            else:
                # Force Paddle/PaddleX CPU execution path when OCR GPU is disabled.
                os.environ["CUDA_VISIBLE_DEVICES"] = ""

            try:  # pragma: no cover
                from paddleocr import PaddleOCR, PPStructure  # type: ignore
            except ImportError:  # pragma: no cover - PaddleOCR>=3.3 reorganised modules
                from paddleocr import PaddleOCR  # type: ignore
                try:
                    from paddleocr import PPStructureV3 as PPStructure  # type: ignore
                except ImportError:
                    from paddleocr._pipelines import PPStructureV3 as PPStructure  # type: ignore
            try:
                from paddle.base import libpaddle  # type: ignore

                if not hasattr(libpaddle.AnalysisConfig, "set_optimization_level"):
                    def _set_optimization_level(self, level):  # type: ignore
                        if hasattr(self, "tensorrt_optimization_level"):
                            try:
                                self.tensorrt_optimization_level = level
                            except Exception:
                                pass
                        return self
                    libpaddle.AnalysisConfig.set_optimization_level = _set_optimization_level  # type: ignore
            except Exception:  # pragma: no cover
                pass

            common_kwargs: Dict[str, Any] = {
                "device": "gpu" if self.use_gpu else "cpu",
            }
            if not self.use_gpu:
                if "enable_mkldnn" in ocr_config:
                    common_kwargs["enable_mkldnn"] = bool(ocr_config.get("enable_mkldnn"))
                if "cpu_threads" in ocr_config:
                    common_kwargs["cpu_threads"] = _int(ocr_config.get("cpu_threads", 4), 4)

            ocr_kwargs: Dict[str, Any] = {
                "lang": self.primary_lang,
                "text_recognition_batch_size": self.rec_batch_size,
                "enable_hpi": False,
                "use_doc_orientation_classify": _bool(
                    ocr_config.get("use_doc_orientation_classify"), False
                ),
                "use_doc_unwarping": _bool(
                    ocr_config.get("use_doc_unwarping"), False
                ),
                "use_textline_orientation": _bool(
                    ocr_config.get("use_textline_orientation"), self.enable_angle_cls
                ),
                **common_kwargs,
            }
            if self.det_model_dir and self.det_model_dir.exists():
                ocr_kwargs["text_detection_model_dir"] = str(self.det_model_dir)
            if self.rec_model_dir and self.rec_model_dir.exists():
                ocr_kwargs["text_recognition_model_dir"] = str(self.rec_model_dir)
            if self.cls_model_dir and self.cls_model_dir.exists():
                ocr_kwargs["textline_orientation_model_dir"] = str(self.cls_model_dir)

            logger.info(
                "[PaddleOCR-VL] Initialising engine (lang=%s, gpu=%s, batch=%s)",
                self.primary_lang,
                self.use_gpu,
                self.rec_batch_size,
            )

            self._ocr = PaddleOCR(**ocr_kwargs)

            if self.enable_layout:
                logger.info("[PaddleOCR-VL] Layout analysis enabled")
                structure_version = self.layout_structure_version or layout_cfg.get("ocr_version") or "PP-OCRv5"
                structure_version = {
                    "PP-DocLayoutV2": "PP-OCRv5",
                    "PP-DocLayoutV3": "PP-OCRv5",
                }.get(structure_version, structure_version)
                layout_kwargs: Dict[str, Any] = {
                    "lang": self.primary_lang,
                    "use_table_recognition": self.layout_detect_tables,
                    "text_recognition_batch_size": self.rec_batch_size,
                    "ocr_version": structure_version,
                    **common_kwargs,
                }
                layout_model_dir: Optional[str] = None
                if self.layout_model_dir and self.layout_model_dir.exists():
                    has_pdmodel = any(self.layout_model_dir.glob("*.pdmodel"))
                    if has_pdmodel:
                        layout_model_dir = str(self.layout_model_dir)
                        layout_kwargs["layout_detection_model_dir"] = layout_model_dir
                    else:
                        logger.warning(
                            "[PaddleOCR-VL] layout model dir %s lacks *.pdmodel, falling back to built-in weights",
                            self.layout_model_dir,
                        )
                try:
                    self._layout = PPStructure(**layout_kwargs)
                except AssertionError as assert_exc:
                    if layout_model_dir and "model dir" in str(assert_exc).lower():
                        logger.warning(
                            "[PaddleOCR-VL] Layout model mismatch for %s, retrying with built-in weights",
                            layout_model_dir,
                        )
                        layout_kwargs.pop("layout_detection_model_dir", None)
                        self._layout = PPStructure(**layout_kwargs)
                    else:
                        raise
            else:
                self._layout = None

        except Exception as exc:  # pragma: no cover - requires paddle runtime
            logger.exception("[PaddleOCR-VL] Failed to initialise engine: %s", exc)
            raise

    # ------------------------------------------------------------------
    # PaddleOCR compatibility helpers
    # ------------------------------------------------------------------
    def ocr(self, image_path: str, cls: bool = True) -> List[Any]:  # pragma: no cover
        """Compatibility proxy for legacy call sites."""
        return self._ocr.ocr(image_path, cls=cls)

    def extract_text(self, image_path: str) -> Dict[str, Any]:
        """Run OCR and return consolidated output and metadata."""
        raw_result = self._ocr.ocr(image_path)
        lines: List[OCRLine] = []

        if not raw_result:
            return {"text": "", "lines": []}

        primary = raw_result[0] if isinstance(raw_result, list) else raw_result
        texts = list(primary.get("rec_texts", [])) if isinstance(primary, dict) else []
        scores = list(primary.get("rec_scores", [])) if isinstance(primary, dict) else []
        boxes = primary.get("rec_polys") or primary.get("rec_boxes") if isinstance(primary, dict) else None

        for idx, text in enumerate(texts):
            text = (text or "").strip()
            if not text:
                continue
            confidence = float(scores[idx]) if idx < len(scores) else 1.0
            if confidence < self.min_confidence:
                continue

            bbox = None
            if boxes is not None and idx < len(boxes):
                bbox_entry = boxes[idx]
                try:
                    bbox = bbox_entry.tolist()
                except AttributeError:
                    bbox = bbox_entry

            lines.append(
                OCRLine(
                    text=text,
                    confidence=confidence,
                    bbox=bbox,
                    language=self.primary_lang,
                )
            )

        joined_text = "\n".join(line.text for line in lines)
        return {
            "text": joined_text,
            "lines": [line.__dict__ for line in lines],
        }

    def analyze_layout(self, image_path: str) -> List[Dict[str, Any]]:
        """Execute PP-Structure for layout detection if available."""
        if not self.enable_layout or not self._layout:
            return []

        try:
            # PPStructureV3 需要使用 __call__ 方法或者 predict 方法
            if hasattr(self._layout, '__call__'):
                layout_items = self._layout(image_path)
            elif hasattr(self._layout, 'predict'):
                layout_items = self._layout.predict(image_path)
            else:
                # 嘗試直接調用
                layout_items = self._layout(image_path)
        except Exception as exc:  # pragma: no cover - depends on runtime
            logger.warning("[PaddleOCR-VL] Layout analysis failed: %s", exc)
            return []

        filtered: List[Dict[str, Any]] = []
        for item in layout_items or []:
            if not isinstance(item, dict):
                continue
            res = item.get("res")
            score = 1.0
            if isinstance(res, dict):
                score = float(res.get("confidence", 1.0))
            if score < self.layout_score_threshold:
                continue
            filtered.append(item)
        return filtered

    def clear(self) -> None:
        """Release cached resources."""
        try:
            if hasattr(self._ocr, "predictor"):
                delattr(self._ocr, "predictor")
        except Exception:
            pass
        if self._layout:
            try:
                if hasattr(self._layout, "predictor"):
                    delattr(self._layout, "predictor")
            except Exception:
                pass


def get_paddleocr_vl_status(config: Dict[str, Any]) -> Dict[str, Any]:
    """Return diagnostic information for PaddleOCR-VL configuration."""
    try:
        ocr_cfg = config.get("ocr", {}) if isinstance(config, dict) else {}
        layout_cfg = ocr_cfg.get("layout", {}) if isinstance(ocr_cfg.get("layout"), dict) else {}
        model_root = _resolve_path(ocr_cfg.get("model_root"))
        layout_dir = _resolve_path(layout_cfg.get("model_dir"))
        exists = lambda path, name: bool(path and path.exists() and any(path.glob(name)))
        try:
            import paddleocr as _paddleocr  # type: ignore
            version = getattr(_paddleocr, "__version__", None)
        except Exception:
            version = None

        status = {
            "ok": True,
            "engine": ocr_cfg.get("engine"),
            "use_gpu": bool(ocr_cfg.get("use_gpu")),
            "device": "gpu" if bool(ocr_cfg.get("use_gpu")) else "cpu",
            "device_id": ocr_cfg.get("device_id"),
            "batch_size": ocr_cfg.get("batch_size"),
            "languages": ocr_cfg.get("languages"),
            "version": version,
            "model_root": str(model_root) if model_root else None,
            "layout_model_dir": str(layout_dir) if layout_dir else None,
            "layout_structure_version": layout_cfg.get("structure_version") or layout_cfg.get("ocr_version"),
            "layout_enabled": _bool(layout_cfg.get("enabled"), True),
            "layout_files": {
                "pdmodel": exists(layout_dir, "*.pdmodel"),
                "pdiparams": exists(layout_dir, "*.pdiparams"),
            },
            "checked_at": datetime.utcnow().isoformat(),
        }
        if layout_dir and not layout_dir.exists():
            status["ok"] = False
            status["error"] = "layout_model_dir_missing"
        if model_root and not model_root.exists():
            status["ok"] = False
            status["error"] = "model_root_missing"
        return status
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
