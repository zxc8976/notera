"""
結構化 OCR 處理模組
====================

提供以下能力：
1. 透過 PaddleOCR-VL (PP-Structure) 嘗試辨識版面結構（標題、段落、公式、表格等）
2. 針對數學/程式公式區塊做額外標記與整理
3. 回傳適合餵給 LLM / 筆記生成器的結構化結果

若環境尚未安裝 PP-Structure，則自動回退為傳統 OCR 文字抽取。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .ocr_utils import ocr_manager

logger = logging.getLogger(__name__)


@dataclass
class StructuredBlock:
    """單一區塊資訊"""

    block_type: str
    text: str
    bbox: Optional[List[List[int]]] = None
    confidence: float = 1.0
    meta: Dict[str, Any] = field(default_factory=dict)

    def is_formula(self) -> bool:
        return self.block_type in {"formula", "equation", "latex"} or looks_like_formula(
            self.text
        )

    def is_heading(self) -> bool:
        return self.block_type in {"title", "heading", "header"}

    def is_table(self) -> bool:
        return self.block_type in {"table"}

    def compact_text(self) -> str:
        return " ".join(self.text.split())


@dataclass
class StructuredOcrResult:
    """結構化 OCR 結果"""

    blocks: List[StructuredBlock] = field(default_factory=list)
    formulas: List[StructuredBlock] = field(default_factory=list)
    raw_text: str = ""
    used_layout: bool = False
    errors: List[str] = field(default_factory=list)

    def to_prompt_sections(self, max_chars: int = 2400) -> str:
        """
        生成給 LLM 的結構化提示文字。
        依序列出標題、段落、公式、表格摘要，避免超過指定字數。
        """
        parts: List[str] = []

        if self.blocks:
            headings = [b for b in self.blocks if b.is_heading()]
            paragraphs = [
                b for b in self.blocks if not b.is_heading() and not b.is_formula()
            ]
            tables = [b for b in self.blocks if b.is_table()]

            if headings:
                parts.append("### 標題與章節")
                for block in headings[:6]:
                    parts.append(f"- {block.compact_text()}")

            if paragraphs:
                parts.append("### 主要段落")
                for block in paragraphs[:8]:
                    snippet = block.text.strip().replace("\n", " ")
                    snippet = snippet[:180] + ("…" if len(snippet) > 180 else "")
                    parts.append(f"- {snippet}")

            if self.formulas:
                parts.append("### 公式與推導")
                for block in self.formulas[:8]:
                    clean = block.text.strip().replace("\n", " ")
                    clean = clean[:160] + ("…" if len(clean) > 160 else "")
                    parts.append(f"- {clean}")

            if tables:
                parts.append("### 表格摘要")
                for block in tables[:4]:
                    snippet = block.text.strip().replace("\n", " ")
                    snippet = snippet[:160] + ("…" if len(snippet) > 160 else "")
                    parts.append(f"- {snippet}")

        text = "\n".join(parts)
        if len(text) > max_chars:
            logger.debug(
                "[StructuredOcrResult] prompt 超過上限，已裁切: %d chars", len(text)
            )
            text = text[: max_chars - 3] + "..."
        return text

    def to_dict(self) -> Dict[str, Any]:
        """方便記錄/除錯"""
        return {
            "used_layout": self.used_layout,
            "raw_text_length": len(self.raw_text or ""),
            "blocks": [
                {
                    "type": b.block_type,
                    "text": b.compact_text(),
                    "confidence": b.confidence,
                }
                for b in self.blocks[:30]
            ],
            "formulas": [b.compact_text() for b in self.formulas[:20]],
            "errors": self.errors,
        }


def looks_like_formula(text: str) -> bool:
    """粗略判斷字串是否為公式或程式碼區塊"""
    if not text:
        return False

    formula_tokens = [
        "=",
        "\\frac",
        "\\sum",
        "\\int",
        "∑",
        "∫",
        "≠",
        "≈",
        "π",
        "sin",
        "cos",
        "tan",
        "λ",
        "σ",
        "∀",
        "∃",
        "⇒",
        "→",
        "∝",
    ]
    code_tokens = [";", "def ", "class ", "if (", "{", "}", "for (", "while", "return"]
    text_lower = text.lower()

    if any(token in text for token in formula_tokens):
        return True
    if any(token in text_lower for token in code_tokens):
        return True
    # 連續出現多於 3 個非中文/日文的符號亦視為公式
    symbol_count = sum(1 for ch in text if not ch.isalnum() and ch not in " ()[]{}")
    return symbol_count >= max(3, len(text) // 4)


class StructuredOCRProcessor:
    """
    提供結構化 OCR 結果。
    - 先嘗試使用 PP-Structure 取得版面結構
    - 再透過 OCRManager 抽取完整文字，做為回退或補齊
    """

    def __init__(self, config: Dict[str, Any], device: str = "gpu"):
        self.config = config
        self.device = device
        ocr_cfg = (self.config or {}).get("ocr", {})
        layout_cfg = ocr_cfg.get("layout") or {}
        self._layout_enabled = bool(layout_cfg.get("enabled", True))
        if not self._layout_enabled:
            logger.info("[StructuredOCR] 已停用 PaddleOCR-VL 版面偵測 (layout.enabled=False)")

    def analyze(self, image_path: str) -> StructuredOcrResult:
        result = StructuredOcrResult()

        # 1. 先嘗試結構化輸出
        layout_blocks: List[StructuredBlock] = []
        if self._layout_enabled:
            try:
                structure_output = ocr_manager.analyze_layout(image_path, self.config, self.device)
                for item in structure_output or []:
                    block_type = item.get("type") or "text"
                    bbox = item.get("bbox") or item.get("box")
                    confidence = 1.0
                    text_segment = ""
                    meta: Dict[str, Any] = {}

                    if "res" in item:
                        text_segment, confidence = self._parse_res_field(item["res"])
                        meta["line_count"] = (
                            len(item["res"]) if isinstance(item["res"], list) else 1
                        )
                    elif "text" in item:
                        text_segment = str(item["text"])
                    else:
                        text_segment = ""

                    layout_blocks.append(
                        StructuredBlock(
                            block_type=block_type,
                            text=text_segment,
                            bbox=bbox,
                            confidence=confidence,
                            meta=meta,
                        )
                    )

                    if layout_blocks:
                        result.used_layout = True
                        result.blocks.extend(layout_blocks)
            except Exception as exc:
                logger.warning("[StructuredOCR] 版面分析失敗: %s", exc)
                result.errors.append(f"layout_error: {exc}")

        # 2. 確保取得完整 OCR 文字
        try:
            structured = ocr_manager.extract_with_meta(image_path, self.config, self.device)
            if isinstance(structured, dict):
                result.raw_text = structured.get("text", "") or ""
                if not layout_blocks and structured.get("lines"):
                    for payload in structured["lines"]:
                        if not isinstance(payload, dict):
                            continue
                        block = StructuredBlock(
                            block_type="text",
                            text=str(payload.get("text") or "").strip(),
                            confidence=float(payload.get("confidence", 1.0)),
                            bbox=payload.get("bbox"),
                            meta={"language": payload.get("language")},
                        )
                        if block.text:
                            result.blocks.append(block)
            else:
                result.raw_text = str(structured or "")
        except Exception as exc:
            logger.error("[StructuredOCR] OCR 抽取失敗: %s", exc)
            result.errors.append(f"plain_ocr_error: {exc}")

        # 3. 若沒有結構化結果，從平面文字拆成段落
        if not result.blocks and result.raw_text:
            for para in split_paragraphs(result.raw_text):
                result.blocks.append(
                    StructuredBlock(
                        block_type="paragraph",
                        text=para,
                        confidence=0.9,
                        bbox=None,
                    )
                )

        # 4. 整理公式區塊
        if result.blocks:
            result.formulas = [
                block for block in result.blocks if block.is_formula()
            ]

        # 5. 若版面結果沒有抓到公式，再從原文補抓
        if not result.formulas and result.raw_text:
            for formula_text in detect_formula_lines(result.raw_text.splitlines()):
                result.formulas.append(
                    StructuredBlock(
                        block_type="formula",
                        text=formula_text,
                        confidence=0.8,
                        bbox=None,
                    )
                )

        return result

    @staticmethod
    def _parse_res_field(res_field: Any) -> (str, float):
        """
        從 PP-Structure 的 res 欄位解析文字與置信度。
        res 可能是 list[dict] 或 str。
        """
        if isinstance(res_field, list):
            texts: List[str] = []
            confidences: List[float] = []
            for item in res_field:
                if isinstance(item, dict):
                    if "text" in item:
                        texts.append(str(item["text"]))
                    if "confidence" in item:
                        try:
                            confidences.append(float(item["confidence"]))
                        except (TypeError, ValueError):
                            pass
            text_segment = "\n".join(texts)
            confidence = (
                sum(confidences) / len(confidences) if confidences else 1.0
            )
            return text_segment, confidence

        if isinstance(res_field, str):
            return res_field, 1.0

        return "", 1.0


def split_paragraphs(raw_text: str) -> List[str]:
    """將 OCR 文字粗略切成段落"""
    paragraphs: List[str] = []
    buffer: List[str] = []
    for line in (raw_text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            if buffer:
                paragraphs.append(" ".join(buffer))
                buffer = []
            continue
        buffer.append(stripped)

    if buffer:
        paragraphs.append(" ".join(buffer))
    return paragraphs


def detect_formula_lines(lines: Iterable[str]) -> List[str]:
    """沿著字串逐行找出疑似公式的內容"""
    formulas: List[str] = []
    for line in lines:
        candidate = line.strip()
        if not candidate:
            continue
        if looks_like_formula(candidate):
            formulas.append(candidate)
    return formulas


# 工廠函式，方便其他模組呼叫
def get_structured_ocr_processor(config: Dict[str, Any], device: str = "gpu"):
    return StructuredOCRProcessor(config=config, device=device)
