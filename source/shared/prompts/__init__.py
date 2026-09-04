"""Shared prompt manifest utilities for Cornell/oteLedge note workflows."""
from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from typing import Any, Dict


PROMPT_ID = "cornell-note-v1"
PROMPT_VERSION = "2025-10-24"


_RAW_MANIFEST: Dict[str, Any] = {
    "id": PROMPT_ID,
    "version": PROMPT_VERSION,
    "description": (
        "Cornell/oteLedge hybrid note template ensuring lecture header metadata, "
        "Cue/Notes/Extend sections, and conditional Formula/Code blocks."
    ),
    "sections": [
        {
            "key": "header",
            "title": "🗂 講義名稱 / 章節標題",
            "required": True,
            "fields": [
                {"key": "title", "label": "講義名稱 / 章節標題", "type": "text", "required": True},
                {"key": "date", "label": "日期", "type": "date", "required": True, "format": "YYYY/MM/DD"},
                {"key": "subject", "label": "科目", "type": "text", "required": False, "editable": True},
            ],
        },
        {
            "key": "cue",
            "title": "🧭 一、章節概要（Cornell：Cue）",
            "required": True,
            "format": "ordered-list",
            "hint": "日文原文／主要內容或重點提示，搭配 VLM 判斷",
        },
        {
            "key": "notes",
            "title": "📖 二、中文解釋與理解（Cornell：Notes）",
            "required": True,
            "format": "unordered-list",
            "hint": "逐點說明、解釋與關鍵詞整理",
        },
        {
            "key": "extend",
            "title": "💡 三、補充知識（oteLedge：Extend）",
            "required": True,
            "format": "unordered-list",
            "hint": "背景知識、延伸概念、例外情況、考試陷阱",
        },
        {
            "key": "formula",
            "title": "🔢 四、數學公式",
            "required": False,
            "format": "latex-block",
            "hint": "若有數學推導時顯示，否則整段省略",
        },
        {
            "key": "code",
            "title": "💻 五、程式碼與技術重點",
            "required": False,
            "format": "code-block",
            "hint": "包含語言標示、語法高亮與複製按鈕",
        },
    ],
    "templates": {
        "verification_prompt": (
            "你是多模態校對專家。任務：根據 PaddleOCR-VL 文字輸出與原始圖片，"
            "確認文字內容是否準確，並補齊遺漏的關鍵詞或數據。\n\n"
            "## 輸入材料\n"
            "- OCR 文字：```\n{ocr_text}\n```\n"
            "- 圖片說明：{image_hint}\n"
            "- 其他上下文：{context}\n\n"
            "## 任務要求\n"
            "1. 檢查 OCR 是否缺字、錯字或版面被打亂，必要時列出修正。\n"
            "2. 標記出圖片中重要但未出現在 OCR 的資訊（例如圖表數據、公式、程式碼關鍵字）。\n"
            "3. 產出最多 5 條重點，使用「日文｜中文」的格式。\n"
            "4. 回報整體可信度 0-1，低於 0.6 時須說明原因。\n\n"
            "## 輸出 JSON 結構（請使用純 JSON，不要額外文字）\n"
            "{{\n"
            '  "verified_text": ["..."],\n'
            '  "missing_items": ["..."],\n'
            '  "corrections": ["..."],\n'
            '  "confidence": 0.0\n'
            "}}\n"
        ),
        "final_prompt": (
            "你是多模態講義筆記助理，需整合圖片理解、OCR 校對與缺漏資訊，生成適用 Cornell/oteLedge 模板的內容。"
            "請僅以 JSON 格式回覆，接續由後端轉換為 Markdown。\n\n"
            "## 來源資料\n"
            "- 圖片摘要（可含圖像線索等）：{image_findings}\n"
            "- OCR 校對後的重點：{verified_text}\n"
            "- OCR 缺失或需要補強的項目：{missing_items}\n"
            "- 既有筆記或上下文：{context}\n"
            "- 預設科目：{subject}\n"
            "- 預設日期：{date}\n"
            "- 預設標題：{title}\n\n"
            "## JSON 輸出要求\n"
            "```json\n"
            "{{\n"
            '  "title": "最終講義標題",\n'
            '  "date": "YYYY/MM/DD",\n'
            '  "subject": "科目可調整",\n'
            '  "cue": ["以日文開頭｜中文補充", "..."],\n'
            '  "notes": ["中文重點 1", "中文重點 2"],\n'
            '  "extend": ["補充知識 1", "..."],\n'
            '  "formulas": ["LaTeX 公式"],\n'
            '  "code_blocks": [{{"language": "python", "title": "用途", "code": "print(42)"}}]\n'
            "}}\n"
            "```\n"
            "- `cue` 列表需採 Cornel Cue 格式，日文原文與中文解釋以 `｜` 分隔。\n"
            "- `notes`、`extend` 為中文條列，可根據缺漏資訊補齊重點。\n"
            "- `formulas` 若無內容，回傳空陣列。\n"
            "- `code_blocks` 為陣列，每項含 `language`、`title`（可為空字串）、`code`。無程式內容時回傳空陣列。\n"
            "- 所有文字請使用繁體中文說明，無資料時使用「資訊不足，待補」。"
        ),
    },
}


def _compute_hash(data: Dict[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_prompt_manifest() -> Dict[str, Any]:
    """Return a copy of the Cornell prompt manifest with computed hash."""
    manifest = json.loads(json.dumps(_RAW_MANIFEST, ensure_ascii=False))
    manifest["hash"] = _compute_hash(
        {
            "sections": manifest["sections"],
            "templates": manifest["templates"],
            "version": manifest["version"],
        }
    )
    return manifest


def get_prompt_hash() -> str:
    """Return deterministic hash of the manifest sections/templates."""
    manifest = get_prompt_manifest()
    return manifest["hash"]


@dataclass(frozen=True)
class PromptManifest:
    id: str
    version: str
    hash: str
    description: str
    sections: Any
    templates: Dict[str, str]


def load_manifest() -> PromptManifest:
    """Typed helper returning a dataclass representation."""
    manifest = get_prompt_manifest()
    return PromptManifest(
        id=manifest["id"],
        version=manifest["version"],
        hash=manifest["hash"],
        description=manifest["description"],
        sections=manifest["sections"],
        templates=manifest["templates"],
    )


__all__ = [
    "PROMPT_ID",
    "PROMPT_VERSION",
    "PromptManifest",
    "get_prompt_manifest",
    "get_prompt_hash",
    "load_manifest",
]
