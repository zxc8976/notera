"""
共享的筆記生成模組
統一處理筆記格式化和生成邏輯
"""
import os
import base64
import logging
import shutil
import traceback
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, cast

from PIL import Image

from modules.llm_utils import call_llm
from modules.note_formatter import format_vlm_output
from modules.services.gpu_utils import prepare_llm_inference
from modules.services.runtime_paths import (
    DATA_ROOT,
    FRONTEND_PUBLIC_IMAGES_DIR,
    NOTES_ROOT as NOTES_ROOT_PATH,
    OUTPUT_ROOT as OUTPUT_ROOT_PATH,
    ensure_runtime_dirs,
)
from modules.prompt_registry import resolve_prompt_bundle
from utils import markdown_cleaner

logger = logging.getLogger(__name__)

ensure_runtime_dirs()
OUTPUT_ROOT = str(OUTPUT_ROOT_PATH)
OUTPUT_IMAGES_ROOT = os.path.join(OUTPUT_ROOT, "images")
OUTPUT_TMP_ROOT = os.path.join(OUTPUT_ROOT, "tmp")
NOTES_ROOT = str(NOTES_ROOT_PATH)

LANGUAGE_STRINGS: Dict[str, Dict[str, Any]] = {
    "ja": {
        "note_title_alt": "",
        "labels": {
            "generated_at": "生成日時",
            "target_language": "表示言語",
            "scene_count": "処理したシーン数",
            "include_japanese_true": "- 日本語原文を含みます",
            "include_japanese_false": "- 日本語原文は含まれていません",
        },
        "fallbacks": {
            "jp": "> 現在表示できる日本語原文がありません。",
            "summary": "> 現在表示できる要約がありません。",
            "supplement": "> 追加の補足説明は生成されませんでした。",
            "formula": "> 数式は検出されませんでした。",
            "code": "> コードスニペットは検出されませんでした。",
            "example": "> 例題は生成されませんでした。",
            "quiz": "> 小テストの問題は生成されませんでした。",
            "glossary": "> 用語解説は生成されませんでした。",
        },
        "chapter": {
            "title": "チャプター",
            "image_label": "スライドキャプチャ",
            "detail_heading": "## 📖 内容解説（日本語）",
            "jp_heading": "## 📝 日本語原文",
            "supplement_heading": "## 💡 補足情報",
            "glossary_hint": "下部の用語集を参照してください。",
        },
    },
    "zh-TW": {
        "note_title_alt": "Auto-Generated Note",
        "labels": {
            "generated_at": "生成時間",
            "target_language": "顯示語系",
            "scene_count": "處理的場景數",
            "include_japanese_true": "- ✅ 包含日文原文",
            "include_japanese_false": "- ⚠️ 未包含日文原文",
        },
        "fallbacks": {
            "jp": "> 目前沒有可顯示的日文原文。",
            "summary": "> 尚未產生對應語系的要約內容。",
            "supplement": "> 尚未產生補充說明。",
            "formula": "> 尚未檢出可展示的數學公式。",
            "code": "> 尚未檢出可展示的程式碼片段。",
            "example": "> 尚未產生例題示範。",
            "quiz": "> 尚未產生小測驗題目。",
            "glossary": "> 尚未整理可顯示的術語解釋。",
        },
            "chapter": {
                "title": "章節",
                "image_label": "課程截圖",
                "detail_heading": "## ③ 母語解析（中文）",
                "jp_heading": "## ② 日文重點大綱（原講義語言）",
                "supplement_heading": "## ⑥ 補充說明 / 延伸理解",
                "glossary_hint": "請參考下方術語表了解相關概念。",
            }
    },
    "zh-CN": {
        "note_title_alt": "Auto-Generated Note",
        "labels": {
            "generated_at": "生成时间",
            "target_language": "显示语言",
            "scene_count": "处理场景数",
            "include_japanese_true": "- ✅ 包含日文原文",
            "include_japanese_false": "- ⚠️ 未包含日文原文",
        },
        "fallbacks": {
            "jp": "> 当前没有可显示的日文原文。",
            "summary": "> 尚未生成对应语言的要约内容。",
            "supplement": "> 尚未生成补充说明。",
            "formula": "> 未检测到可展示的数学公式。",
            "code": "> 未检测到可展示的代码片段。",
            "example": "> 尚未生成例题示范。",
            "quiz": "> 尚未生成小测验题目。",
            "glossary": "> 尚未整理可显示的术语解释。",
        },
        "chapter": {
            "title": "章节",
            "image_label": "课程截图",
            "detail_heading": "## ③ 母语解析（中文）",
            "jp_heading": "## ② 日文重点大纲（原讲义语言）",
            "supplement_heading": "## ⑥ 补充说明 / 延伸理解",
            "glossary_hint": "请参考下方术语表了解相关概念。",
        }
    },
    "en": {
        "note_title_alt": "Auto-Generated Note",
        "labels": {
            "generated_at": "Generated at",
            "target_language": "Target locale",
            "scene_count": "Scenes processed",
            "include_japanese_true": "- ✅ Japanese reference included",
            "include_japanese_false": "- ⚠️ Japanese reference not available",
        },
        "fallbacks": {
            "jp": "> No Japanese source text was detected for this session.",
            "summary": "> No localized summary is available yet.",
            "supplement": "> No supplemental insights were generated.",
            "formula": "> No math formulas were detected.",
            "code": "> No runnable code snippets were detected.",
            "example": "> No worked examples were generated.",
            "quiz": "> No quiz questions were generated.",
            "glossary": "> No glossary terms were captured.",
        },
        "chapter": {
            "title": "Chapter",
            "image_label": "Slide Screenshot",
            "detail_heading": "## 📖 Key Explanations",
            "jp_heading": "## 📝 Japanese Reference",
            "supplement_heading": "## 💡 Supplemental Insights",
            "glossary_hint": "Please refer to the glossary below for related concepts.",
        },
    },
    "ko": {
        "note_title_alt": "Auto-Generated Note",
        "labels": {
            "generated_at": "생성 시간",
            "target_language": "표시 언어",
            "scene_count": "처리한 장면 수",
            "include_japanese_true": "- ✅ 일본어 원문 포함",
            "include_japanese_false": "- ⚠️ 일본어 원문 미포함",
        },
        "fallbacks": {
            "jp": "> 표시할 일본어 원문이 없습니다.",
            "summary": "> 요약 내용이 아직 생성되지 않았습니다.",
            "supplement": "> 보충 설명이 생성되지 않았습니다.",
            "formula": "> 수식이 감지되지 않았습니다.",
            "code": "> 코드 스니펫이 감지되지 않았습니다.",
            "example": "> 예제가 생성되지 않았습니다.",
            "quiz": "> 퀴즈가 생성되지 않았습니다.",
            "glossary": "> 용어 해설이 없습니다.",
        },
        "chapter": {
            "title": "챕터",
            "image_label": "슬라이드 캡처",
            "detail_heading": "## 📖 핵심 설명",
            "jp_heading": "## 📝 일본어 원문",
            "supplement_heading": "## 💡 보충 설명",
            "glossary_hint": "아래 용어집을 참고하세요.",
        },
    },
    "vi": {
        "note_title_alt": "Auto-Generated Note",
        "labels": {
            "generated_at": "Thời gian tạo",
            "target_language": "Ngôn ngữ hiển thị",
            "scene_count": "Số cảnh đã xử lý",
            "include_japanese_true": "- ✅ Có kèm tiếng Nhật gốc",
            "include_japanese_false": "- ⚠️ Không có tiếng Nhật gốc",
        },
        "fallbacks": {
            "jp": "> Không có nội dung tiếng Nhật để hiển thị.",
            "summary": "> Chưa có phần tóm tắt theo ngôn ngữ này.",
            "supplement": "> Chưa tạo phần bổ sung.",
            "formula": "> Không phát hiện công thức toán.",
            "code": "> Không phát hiện đoạn mã.",
            "example": "> Chưa tạo ví dụ.",
            "quiz": "> Chưa tạo câu hỏi.",
            "glossary": "> Chưa có bảng thuật ngữ.",
        },
        "chapter": {
            "title": "Chương",
            "image_label": "Ảnh slide",
            "detail_heading": "## 📖 Giải thích trọng tâm",
            "jp_heading": "## 📝 Nhật ngữ gốc",
            "supplement_heading": "## 💡 Bổ sung",
            "glossary_hint": "Vui lòng xem bảng thuật ngữ bên dưới.",
        },
    },
    "my": {
        "note_title_alt": "Auto-Generated Note",
        "labels": {
            "generated_at": "ဖန်တီးချိန်",
            "target_language": "ပြသမည့်ဘာသာ",
            "scene_count": "ကိုင်တွယ်ခဲ့သော မြင်ကွင်း အရေအတွက်",
            "include_japanese_true": "- ✅ ဂျပန်မူရင်းပါဝင်",
            "include_japanese_false": "- ⚠️ ဂျပန်မူရင်းမပါဝင်",
        },
        "fallbacks": {
            "jp": "> ပြသရန် ဂျပန်မူရင်းမရှိပါ။",
            "summary": "> ယခုအချိန်တွင် အနှစ်ချုပ် မရှိသေးပါ။",
            "supplement": "> ထပ်ဆင့်ရှင်းလင်းချက် မရှိသေးပါ။",
            "formula": "> သင်္ချာဖော်မြူလာ မတွေ့ပါ။",
            "code": "> ကုဒ်နမူနာ မတွေ့ပါ။",
            "example": "> ဥပမာ မထုတ်လုပ်နိုင်ပါ။",
            "quiz": "> မေးခွန်း မထုတ်လုပ်နိုင်ပါ။",
            "glossary": "> စကားလုံးစာရင်း မရှိပါ။",
        },
        "chapter": {
            "title": "အခန်း",
            "image_label": "စလိုက်ပုံ",
            "detail_heading": "## 📖 အကြောင်းအရာ ရှင်းလင်းချက်",
            "jp_heading": "## 📝 ဂျပန်မူရင်း",
            "supplement_heading": "## 💡 ထပ်ဆင့်အချက်အလက်",
            "glossary_hint": "အောက်ပါ စကားလုံးစာရင်းကို ကြည့်ပါ။",
        },
    },
    "mn": {
        "note_title_alt": "Auto-Generated Note",
        "labels": {
            "generated_at": "Үүсгэсэн цаг",
            "target_language": "Дэлгэцлэх хэл",
            "scene_count": "Боловсруулсан хэсгийн тоо",
            "include_japanese_true": "- ✅ Япон эх текст орсон",
            "include_japanese_false": "- ⚠️ Япон эх текст ороогүй",
        },
        "fallbacks": {
            "jp": "> Япон эх текст олдсонгүй.",
            "summary": "> Одоогоор товч дүгнэлт байхгүй.",
            "supplement": "> Нэмэлт тайлбар үүсгээгүй.",
            "formula": "> Томъёо илрээгүй.",
            "code": "> Кодын жишээ олдсонгүй.",
            "example": "> Жишээ үүсгээгүй.",
            "quiz": "> Асуулт үүсгээгүй.",
            "glossary": "> Нэр томьёоны хэсэг байхгүй.",
        },
        "chapter": {
            "title": "Бүлэг",
            "image_label": "Слайдын зураг",
            "detail_heading": "## 📖 Гол тайлбар",
            "jp_heading": "## 📝 Япон эх текст",
            "supplement_heading": "## 💡 Нэмэлт тайлбар",
            "glossary_hint": "Доорх нэр томьёоны хэсгийг үзнэ үү.",
        },
    },
}

SECTION_ALIASES: Dict[str, Dict[str, str]] = {
    "jp_reference": {
        "zh-TW": "Japanese Reference",
        "zh-CN": "Japanese Reference",
        "en": "Japanese Reference",
        "ko": "일본어 원문",
        "vi": "Nhật ngữ gốc",
        "my": "ဂျပန်မူရင်း",
        "mn": "Япон эх текст",
    },
    "multilingual_summary": {
        "zh-TW": "Analysis & Summary",
        "zh-CN": "Analysis & Summary",
        "en": "Analysis & Summary",
        "ko": "분석 & 요약",
        "vi": "Phân tích & Tóm tắt",
        "my": "ခွဲခြမ်းချက် & အနှစ်ချုပ်",
        "mn": "Шинжилгээ ба Товч дүгнэлт",
    },
    "supplement": {
        "zh-TW": "Supplemental Insights",
        "zh-CN": "Supplemental Insights",
        "en": "Supplemental Insights",
        "ko": "보충 설명",
        "vi": "Bổ sung",
        "my": "ထပ်ဆင့်ရှင်းလင်းချက်",
        "mn": "Нэмэлт тайлбар",
    },
    "formula": {
        "zh-TW": "Math Formula",
        "zh-CN": "Math Formula",
        "en": "Math Formula",
        "ko": "수식",
        "vi": "Công thức",
        "my": "သင်္ချာဖော်မြူလာ",
        "mn": "Томъёо",
    },
    "code": {
        "zh-TW": "Code Snippet",
        "zh-CN": "Code Snippet",
        "en": "Code Snippet",
        "ko": "코드",
        "vi": "Mã nguồn",
        "my": "ကုဒ်",
        "mn": "Код",
    },
    "example": {
        "zh-TW": "Worked Example",
        "zh-CN": "Worked Example",
        "en": "Worked Example",
        "ko": "예제",
        "vi": "Ví dụ",
        "my": "ဥပမာ",
        "mn": "Жишээ",
    },
    "quiz": {
        "zh-TW": "Quick Quiz",
        "zh-CN": "Quick Quiz",
        "en": "Quick Quiz",
        "ko": "퀴즈",
        "vi": "Câu hỏi nhanh",
        "my": "မေးခွန်းတို",
        "mn": "Шалгалт",
    },
    "glossary": {
        "zh-TW": "Glossary",
        "zh-CN": "Glossary",
        "en": "Glossary",
        "ko": "용어집",
        "vi": "Thuật ngữ",
        "my": "စကားလုံးစာရင်း",
        "mn": "Нэр томьёо",
    },
}

COMMON_VOCAB_TERMS = {
    "network", "ネットワーク", "網路", "網絡",
    "service", "サービス", "服務",
    "server", "サーバ", "サーバー", "伺服器",
    "サーバ運用", "サーバー運用", "服務運用",
    "stable", "安定的", "安定", "穩定", "安定性",
    "operation", "オペレーション", "運用", "運行", "操作", "運営", "運用する",
    "point", "ポイント", "重點",
}

SECTION_BASE_TITLES: Dict[str, str] = {
    "jp_reference": "日本語原文（抽出）",
    "multilingual_summary": "解析＋要約（多言語）",
    "supplement": "補足説明（AI補完）",
    "formula": "数式（Math Formula）",
    "code": "コード（Code Snippet）",
    "example": "例題（Example）",
    "quiz": "小テスト（Quiz）",
    "glossary": "用語解説（Glossary）",
}

def convert_web_path_to_fs(web_path: str, base_dir: str = OUTPUT_ROOT) -> str:
    """
    將Web路徑轉換為文件系統路徑
    
    Args:
        web_path: Web路徑,例如 '/images/視頻名/scene_000.jpg'
        base_dir: 基礎目錄,默認為 'output'
    
    Returns:
        str: 文件系統路徑,例如 'output/images/視頻名/scene_000.jpg'
    
    Examples:
        >>> convert_web_path_to_fs('/images/video/scene_001.jpg')
        'output/images/video/scene_001.jpg'
        
        >>> convert_web_path_to_fs('/images/test%20video/scene_001.jpg')
        'output/images/test video/scene_001.jpg'
    """
    if not web_path or not web_path.startswith('/images/'):
        return web_path
    
    # URL解碼並移除開頭的 '/',然後加上基礎目錄前綴
    decoded_path = unquote(web_path[1:])  # 移除開頭的 '/'
    return os.path.join(base_dir, decoded_path)

class NoteGenerator:
    """筆記生成器 - 統一處理筆記生成邏輯"""
    
    def __init__(self, llm_config):
        self.llm_config = llm_config
        self._config_cache = None
        self.last_detailed_prompt = None
        self.last_note_metadata: Dict[str, Any] = {}
        self._prompt_bundle = None
        self._prompt_profile: Optional[str] = None

    def _load_runtime_config(self):
        """Lazy-load YAML configuration so prompt selection can be dynamic."""

        if self._config_cache is not None:
            return self._config_cache

        config_path = str(Path(__file__).resolve().parents[1] / "app" / "config.yaml")
        try:
            import yaml  # Local import to avoid hard dependency at module load

            with open(config_path, 'r', encoding='utf-8') as fh:
                self._config_cache = yaml.safe_load(fh) or {}
        except Exception as exc:  # pragma: no cover - configuration fallback
            logger.warning(
                "[NoteGenerator] 無法載入 config.yaml，使用預設設定: %s", exc
            )
            self._config_cache = {}
        return self._config_cache

    def set_runtime_config(self, runtime_config: Dict[str, Any]) -> None:
        """Inject runtime config from request-scoped pipeline."""
        self._config_cache = dict(runtime_config or {})
        self._prompt_bundle = None
        self._prompt_profile = None

    def _ensure_prompt_bundle(self):
        """Resolve prompt bundle based on configuration (cached)."""

        if self._prompt_bundle is not None:
            return self._prompt_bundle

        config = self._load_runtime_config() or {}
        bundle, profile = resolve_prompt_bundle(config)
        self._prompt_bundle = bundle
        self._prompt_profile = profile
        logger.info("[NoteGenerator] Prompt profile resolved to '%s'", profile)
        return self._prompt_bundle

    @staticmethod
    def _determine_locale_key(language: Optional[str]) -> str:
        lang = (language or "").lower()
        if lang.startswith("ja"):
            return "ja"
        if lang.startswith("zh-cn") or lang.startswith("zh-hans"):
            return "zh-CN"
        if lang.startswith("zh"):
            return "zh-TW"
        if lang.startswith("ko"):
            return "ko"
        if lang.startswith("vi"):
            return "vi"
        if lang.startswith("my"):
            return "my"
        if lang.startswith("mn"):
            return "mn"
        return "en"

    @staticmethod
    def _infer_language_mode(language: Optional[str], include_japanese: bool) -> str:
        lang = (language or "").lower()
        if lang.startswith("ja") and not include_japanese:
            return "ja-only"
        return "bilingual" if include_japanese else "target-only"

    def _get_language_strings(self, language: Optional[str]) -> Dict[str, Dict[str, str]]:
        key = self._determine_locale_key(language)
        return LANGUAGE_STRINGS.get(key, LANGUAGE_STRINGS["en"])

    def _build_section_heading(self, section_key: str, language: Optional[str]) -> str:
        base = SECTION_BASE_TITLES.get(section_key, section_key)
        locale_key = self._determine_locale_key(language)
        if locale_key == "ja":
            return f"## {base}"
        alias_map = SECTION_ALIASES.get(section_key, {})
        alt = alias_map.get(locale_key) or alias_map.get("en", "")
        if alt:
            return f"## {base} / {alt}"
        return f"## {base}"

    @staticmethod
    def _contains_japanese(text: str) -> bool:
        if not text:
            return False
        return bool(re.search(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]", text))

    def _build_blueprint_markdown(
        self,
        scene_notes: List[str],
        scene_summaries: List[Dict[str, Any]],
        language: Optional[str],
        include_japanese: bool,
    ) -> Tuple[str, Dict[str, bool]]:
        lang_key = self._determine_locale_key(language)
        strings = self._get_language_strings(language)
        note_title_alt = strings.get("note_title_alt", "")

        header = "# 自動生成ノート"
        if lang_key != "ja" and note_title_alt:
            header += f" / {note_title_alt}"
        header += "\n\n"

        generated_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        labels = strings.get("labels", {})
        overview_lines = [
            f"- {labels.get('generated_at', 'Generated at')}: {generated_at_utc}",
            f"- {labels.get('target_language', 'Target locale')}: {language or 'unknown'}",
            f"- {labels.get('scene_count', 'Scenes processed')}: {len(scene_summaries or [])}",
        ]
        include_label = labels.get(
            "include_japanese_true" if include_japanese else "include_japanese_false",
            "",
        )
        if include_label:
            overview_lines.append(include_label)
        if self._prompt_profile:
            overview_lines.append(f"- Prompt profile: {self._prompt_profile}")
        overview_section = "\n".join(overview_lines) + "\n\n"

        combined_notes = "\n".join(scene_notes or []).strip()
        if not combined_notes:
            combined_notes = strings["fallbacks"].get("summary", "").strip()

        # 日本語原文抽出
        jp_lines: List[str] = []
        if scene_summaries:
            for scene in scene_summaries:
                for key in ("jp_text", "ocr_text", "raw_text"):
                    raw = scene.get(key)
                    if not raw:
                        continue
                    text = str(raw)
                    for line in text.splitlines():
                        stripped = line.strip()
                        if stripped and self._contains_japanese(stripped):
                            jp_lines.append(stripped)
                if len(jp_lines) >= 20:
                    break
        jp_lines = jp_lines[:20]
        jp_has_content = bool(jp_lines)
        jp_section_body = ""
        if jp_has_content:
            jp_section_body = "\n".join(f"- {line}" for line in jp_lines) + "\n"
        else:
            jp_section_body = strings["fallbacks"].get("jp", "").strip()

        # 補足說明
        supplement_candidates: List[str] = []
        for scene in scene_summaries or []:
            for key in (
                "supplement",
                "supplements",
                "insights",
                "ai_completion",
                "analysis",
            ):
                value = scene.get(key)
                if isinstance(value, str):
                    val = value.strip()
                    if val:
                        supplement_candidates.append(val)
                elif isinstance(value, list):
                    for item in value:
                        text_val = str(item or "").strip()
                        if text_val:
                            supplement_candidates.append(text_val)
        supplement_text = ""
        supplement_has_content = bool(supplement_candidates)
        if supplement_has_content:
            supplement_text = "\n\n".join(supplement_candidates[:3]).strip()
        else:
            supplement_text = strings["fallbacks"].get("supplement", "").strip()

        # 數學公式
        formulas: List[str] = []
        for scene in scene_summaries or []:
            for key in ("formulas", "formula_lines", "math_formulas"):
                value = scene.get(key)
                if isinstance(value, list):
                    formulas.extend(str(item).strip() for item in value if item)
                elif isinstance(value, str):
                    formulas.append(value.strip())
        if not formulas:
            # 解析 markdown 內容
            inline_formulas = re.findall(r"\$\$(.+?)\$\$", combined_notes, flags=re.S)
            inline_formulas += re.findall(r"\$(.+?)\$", combined_notes)
            formulas.extend(frag.strip() for frag in inline_formulas if frag.strip())
        formulas = [frag for frag in formulas if frag]
        formula_has_content = bool(formulas)
        if formula_has_content:
            formula_text = "\n".join(f"- {frag}" for frag in formulas[:10])
        else:
            formula_text = strings["fallbacks"].get("formula", "").strip()

        # 程式碼
        code_blocks = re.findall(r"```(?:[\w+-]+)?\n.+?\n```", combined_notes, flags=re.S)
        code_has_content = bool(code_blocks)
        code_text = code_blocks[0].strip() if code_has_content else strings["fallbacks"].get("code", "").strip()

        # 例題 / 小測驗 / 用語解釋
        def extract_section(markdown: str, headings: List[str]) -> Optional[str]:
            if not markdown:
                return None
            for heading in headings:
                pattern = rf"##\s*{re.escape(heading)}[^\n]*\n(.*?)(?=\n##\s|$\Z)"
                match = re.search(pattern, markdown, flags=re.S | re.IGNORECASE)
                if match:
                    content = match.group(1).strip()
                    if content:
                        return content
            return None

        example_text = extract_section(
            combined_notes,
            ["例題", "例题", "Example", "Worked Example"],
        )
        example_has_content = bool(example_text)
        if not example_text:
            example_text = strings["fallbacks"].get("example", "").strip()

        quiz_text = extract_section(
            combined_notes,
            ["小テスト", "小測驗", "小测验", "Quick Quiz", "Quiz", "Self-Check"],
        )
        quiz_has_content = bool(quiz_text)
        if not quiz_text:
            quiz_text = strings["fallbacks"].get("quiz", "").strip()

        glossary_text = extract_section(
            combined_notes,
            ["用語解説", "用語解說", "用语解说", "Glossary"],
        )
        glossary_has_content = bool(glossary_text)
        if not glossary_text:
            glossary_text = strings["fallbacks"].get("glossary", "").strip()

        section_presence = {
            "note_overview": True,
            "jp_reference": jp_has_content and include_japanese,
            "multilingual_summary": bool(combined_notes),
            "supplement": supplement_has_content,
            "formula": formula_has_content,
            "code": code_has_content,
            "example": example_has_content,
            "quiz": quiz_has_content,
            "glossary": glossary_has_content,
        }

        parts: List[str] = [
            header,
            overview_section,
        ]

        if include_japanese:
            parts.append(f"{self._build_section_heading('jp_reference', language)}\n\n{jp_section_body.strip()}\n")

        parts.append(
            f"{self._build_section_heading('multilingual_summary', language)}\n\n{combined_notes.strip()}\n"
        )
        parts.append(
            f"{self._build_section_heading('supplement', language)}\n\n{supplement_text.strip()}\n"
        )
        parts.append(
            f"{self._build_section_heading('formula', language)}\n\n{formula_text.strip()}\n"
        )
        parts.append(
            f"{self._build_section_heading('code', language)}\n\n{code_text.strip()}\n"
        )
        parts.append(
            f"{self._build_section_heading('example', language)}\n\n{example_text.strip()}\n"
        )
        parts.append(
            f"{self._build_section_heading('quiz', language)}\n\n{quiz_text.strip()}\n"
        )
        parts.append(
            f"{self._build_section_heading('glossary', language)}\n\n{glossary_text.strip()}\n"
        )

        markdown = "\n".join(parts).strip() + "\n"
        return markdown, section_presence

    @staticmethod
    def _format_timecode(seconds):
        """Return mm:ss string for a float timestamp."""

        if seconds is None:
            return "??:??"
        try:
            total = int(round(float(seconds)))
        except (TypeError, ValueError):  # pragma: no cover - defensive guard
            return "??:??"
        if total < 0:
            total = 0
        minutes, secs = divmod(total, 60)
        return f"{minutes:02d}:{secs:02d}"

    @staticmethod
    def _split_text_for_segments(text: str, *, max_chunk: int = 220) -> List[str]:
        """Split raw transcript text into manageable pieces for prompting."""

        if not text:
            return []

        # Prefer existing line breaks first
        parts = [ln.strip() for ln in text.replace('\r', '\n').split('\n') if ln.strip()]
        if parts:
            return parts

        stripped = text.strip()
        if not stripped:
            return []

        if len(stripped) <= max_chunk:
            return [stripped]

        chunks = []
        start = 0
        length = len(stripped)
        while start < length:
            end = min(start + max_chunk, length)
            chunks.append(stripped[start:end].strip())
            start = end
        return [chunk for chunk in chunks if chunk]

    @staticmethod
    def _strip_markdown_to_plain(text: str) -> str:
        """Reduce markdown-heavy content to plain sentences for prompting."""

        if not text:
            return ""

        import re

        # Remove fenced code blocks entirely; they pollute the transcript view
        cleaned = re.sub(r"```[\s\S]*?```", " ", text)
        # Unwrap inline code markers
        cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)

        plain_lines = []
        for raw_line in cleaned.splitlines():
            line = re.sub(r"^\s*(?:[#>\-\*\+\u2022]+|\d+\.)\s*", "", raw_line)
            line = re.sub(r"\s+", " ", line).strip()
            if line:
                plain_lines.append(line)
        return "\n".join(plain_lines)
    
    @staticmethod
    def _strip_enclosing_code_fences(text: str) -> str:
        """Remove single enclosing triple-backtick fences from a Markdown block."""
        if not text:
            return ""
        stripped = text.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            # Remove leading fence with optional language hint
            lines = stripped.splitlines()
            if len(lines) >= 2:
                first = lines[0]
                last = lines[-1]
                if first.startswith("```") and last.strip() == "```":
                    body = "\n".join(lines[1:-1])
                    return body.strip()
        return stripped

    def _extract_scene_text(self, scene: dict) -> Tuple[str, Optional[str]]:
        """Pick the best available textual evidence for transcript prompts."""

        raw_asr = (scene.get('asr_text') or '').strip()
        if raw_asr:
            return raw_asr, 'asr'

        raw_ocr = (scene.get('ocr_text') or '').strip()
        if raw_ocr:
            return self._strip_markdown_to_plain(raw_ocr), 'ocr'

        raw_summary = (scene.get('summary') or '').strip()
        if raw_summary:
            return self._strip_markdown_to_plain(raw_summary), 'summary'

        return "", None

    def _build_transcript_segment_text(self, scene_summaries, *, max_segments: int = 200) -> str:
        """Convert scene summaries into the {segment_text} payload."""

        if not scene_summaries:
            return ""

        lines = []
        for scene in scene_summaries:
            timecode = self._format_timecode(scene.get('start'))
            raw_text, source = self._extract_scene_text(scene or {})
            if not raw_text:
                continue

            if source and source != 'asr':
                logger.debug(
                    "[NoteGenerator] transcript fallback using %s for scene %s",
                    source,
                    scene.get('index'),
                )

            for fragment in NoteGenerator._split_text_for_segments(raw_text):
                if not fragment:
                    continue
                lines.append(f"{timecode} - {fragment}")
                if len(lines) >= max_segments:
                    return "\n".join(lines)

        return "\n".join(lines)

    async def _generate_detailed_transcript_notes(self, scene_summaries, language: str, config: dict) -> str:
        """Run the detailed transcript-based prompt when enabled."""

        from modules import detailed_note_prompts

        max_segments_raw = config.get('max_segments', 200) or 200
        try:
            max_segments = max(1, int(max_segments_raw))
        except (TypeError, ValueError):
            max_segments = 200
        segment_text = self._build_transcript_segment_text(
            scene_summaries, max_segments=max_segments
        )

        if not segment_text.strip():
            logger.info("[NoteGenerator] 詳細講義無可用 transcript，跳過生成")
            return ""

        prompt = detailed_note_prompts.build_detailed_prompt(
            segment_text,
            target_language=language,
            video_title=config.get('video_title'),
            tags=config.get('tags'),
            include_link=config.get('include_time_markers', True),
            include_screenshot=config.get('include_screenshot_placeholders', False),
            include_ai_summary=config.get('include_ai_summary', True),
        )

        self.last_detailed_prompt = prompt

        model = config.get('model') or self.llm_config.get('final_model', 'qwen3-vl:4b')
        prepare_llm_inference("note-generator:transcript-notes")
        response = await call_llm(
            prompt=prompt,
            model=model,
            language=language,
            use_cache=False,
        )

        if response and response.strip():
            cleaned = self._strip_enclosing_code_fences(response)
            return cleaned
        return ""
    
    def format_image_note(
        self,
        content,
        image_filename,
        base_name,
        language="zh-TW",
        include_japanese=True,
        ocr_text="",
        structured_summary="",
        structured_ocr=None,
        visual_focus="",
    ):
        """
        格式化圖片筆記 - 簡化版:確保圖片顯示且內容完整
        
        Args:
            content: 筆記內容
            image_filename: 圖片檔名
            base_name: 基本名稱
            language: 語言代碼
            include_japanese: 是否包含日文學習內容
            ocr_text: 原始OCR文字
            structured_summary: 結構化OCR的重點摘要
            structured_ocr: 結構化OCR的詳細字典
            visual_focus: VLM 補充的視覺重點
        
        Returns:
            str: 格式化後的筆記
        """
        logger.info(f"[NoteGenerator] 格式化圖片筆記: {image_filename} (語言: {language}, 包含日文: {include_japanese})")
        if self.last_note_metadata.get("note_style") == "transcript":
            logger.info("[NoteGenerator] Transcript 模式啟用，略過圖片筆記格式化")
            return content
        
        try:
            # ===== 1. 內容品質檢查 =====
            content_length = len(content.strip()) if content else 0
            
            if not content or content_length < 200:
                logger.error(f"[NoteGenerator] ❌ 筆記內容過短或為空: {content_length} 字")
                return self._generate_error_note(image_filename, "內容生成失敗", 
                    "LLM 未返回有效內容,請檢查 Ollama 服務狀態")

            structured_info = structured_ocr or {}
            structured_formula_count = len(structured_info.get('formulas') or [])
            structured_used_layout = bool(structured_info.get('used_layout'))
            summary_lower = (structured_summary or "").lower()
            source_has_formula = structured_formula_count > 0 or any(
                keyword in summary_lower for keyword in ["公式", "equation", "式", "math", "derivation", "積分", "integral", "微分"]
            )
            source_has_flow = False
            if structured_summary:
                if any(token in structured_summary for token in ["→", "↦", "箭頭", "流程", "手順"]):
                    source_has_flow = True
            for block in structured_info.get('blocks') or []:
                text = (block.get('text') or "")
                lowered = text.lower()
                if any(
                    token in text
                    for token in ["→", "↦", "流程", "手順"]
                ) or any(token in lowered for token in ["arrow", "flow", "step", "transition"]):
                    source_has_flow = True
                    break

            logger.info(
                f"[NoteGenerator] 結構化來源資訊: formulas={structured_formula_count}, used_layout={structured_used_layout}, flow={source_has_flow}"
            )
            
            # 檢查是否為錯誤降級內容
            if "🚨 系統提示" in content:
                logger.warning(f"[NoteGenerator] ⚠️ 內容包含系統錯誤提示,這是降級的 OCR 結果")
            
            # ===== 2. 結構完整性檢查 =====
            quality_issues = []
            
            # 放寬檢查條件 - 匹配多種可能的標題格式(包含多語言)
            has_japanese_section = (
                "📌 日文重點摘錄" in content or 
                "📌 日文重點" in content or
                "🇯🇵" in content or
                "日文原文" in content or
                "日文重點" in content or
                "日本語の要点" in content or  # 日語
                "Japanese Highlights" in content or  # 英語
                "일본어 요점" in content  # 韓語
            )
            has_chinese_section = (
                ("📘" in content and "詳解" in content) or
                ("📘" in content and "說明" in content) or
                "繁體中文詳解" in content or
                "繁體中文說明" in content or
                "中文解釋" in content or
                "日本語説明" in content or  # 日語說明
                "English Explanation" in content or  # 英語說明
                "한국어 설명" in content or  # 韓語說明
                "Core Concept" in content  # 英文詳解區塊
            )
            has_code_section = "💻" in content or "```" in content
            has_supplement_section = "🔧" in content or "補充" in content
            
            if include_japanese and not has_japanese_section:
                quality_issues.append("缺少日文重點摘錄區塊")
                logger.warning(f"[NoteGenerator] ⚠️ 內容缺少日文重點摘錄")
            
            if not has_chinese_section:
                quality_issues.append("缺少中文詳解區塊")
                logger.warning(f"[NoteGenerator] ⚠️ 內容缺少中文詳解")
            
            # 程式碼不是必須的(可能是純理論內容)
            if not has_code_section:
                logger.info(f"[NoteGenerator] ℹ️ 內容未包含程式碼範例(可能為純理論講義)")

            if source_has_formula and not self._has_formula_section(content):
                quality_issues.append("來源包含公式或程式步驟,需補充公式推導或程式說明")
                logger.warning("[NoteGenerator] ⚠️ 來源顯示公式/程式,但筆記缺少對應說明")

            if source_has_flow and not self._has_flow_description(content):
                quality_issues.append("來源有流程/箭頭提示,需補充步驟或狀態解釋")
                logger.warning("[NoteGenerator] ⚠️ 來源顯示流程箭頭,但筆記缺少流程描述")
            
            # ===== 3. 內容長度檢查 =====
            if content_length < 800:
                quality_issues.append(f"內容過短({content_length}字),可能分析不完整")
                logger.warning(f"[NoteGenerator] ⚠️ 筆記內容偏短: {content_length} 字")
            else:
                logger.info(f"[NoteGenerator] ✅ 筆記內容長度合理: {content_length} 字")

            if visual_focus and visual_focus.strip():
                if not self._has_visual_section(content):
                    header = self._get_visual_header(language)
                    content = content.rstrip() + f"\n\n{header}\n{visual_focus.strip()}\n"
                    quality_issues.append("已自動補上圖像補充說明")
                    logger.info("[NoteGenerator] 🔁 已注入視覺補充段落")
                else:
                    logger.info("[NoteGenerator] 視覺補充段落已存在，不需追加")
            
            # ===== 4. 如果有品質問題,添加警告區塊 =====
            if quality_issues:
                warning_block = "\n\n---\n## ⚠️ 內容品質提示\n\n"
                warning_block += "本筆記可能存在以下問題:\n\n"
                for issue in quality_issues:
                    warning_block += f"- ⚠️ {issue}\n"
                warning_block += "\n**建議:** 檢查 LLM 服務狀態或重新處理此圖片\n\n---\n\n"
                content = warning_block + content
            
            # 確保圖片檔名正確
            display_filename = image_filename
            
            # 處理 HEIC -> JPG 轉換後的檔名
            if image_filename.lower().endswith('.heic'):
                # HEIC 轉換後會變成 xxx_converted.jpg
                display_filename = image_filename.rsplit('.', 1)[0] + '_converted.jpg'
            
            # 根據語言設置圖片區塊
            if include_japanese:
                image_section_titles = {
                    "zh-TW": "## 📸 講義圖片\n",
                    "zh-CN": "## 📸 讲义图片\n",
                    "ja": "## 📸 講義画像\n",
                    "en": "## 📸 Lecture Image\n",
                    "ko": "## 📸 강의 이미지\n"
                }
            else:
                image_section_titles = {
                    "zh-TW": "## 📸 講義圖片\n",
                    "zh-CN": "## 📸 讲义图片\n",
                    "ja": "## 📸 講義画像\n",
                    "en": "## 📸 Lecture Image\n",
                    "ko": "## 📸 강의 이미지\n"
                }
            
            image_section_title = image_section_titles.get(language, image_section_titles["zh-TW"])
            
            # 構建圖片Markdown（圖片必須在單元最上方）
            # 使用完整路徑: /images/{base_name}/{display_filename}
            image_markdown = f"\n![講義圖片](/images/{base_name}/{display_filename})\n\n"
            
            # 組合: 圖片 + 內容（不再在圖片後插入分隔線）
            final_note = image_section_title + image_markdown + content
            
            logger.info(f"[NoteGenerator] ✅ 筆記格式化完成,總長度: {len(final_note)} 字")
            return final_note
                


        except Exception as e:
            logger.error(f"[NoteGenerator] ❌ 格式化圖片筆記失敗: {e}")
            logger.error(traceback.format_exc())
            return content
    
    def _enhance_image_note_content(self, content, language, include_japanese):
        """增強圖片筆記內容 - 極致空白清理"""
        try:
            import re
            enhanced_content = content or ""

            # 第一階段：激進式空白區塊清理
            lines = enhanced_content.split('\n')
            cleaned = []
            i = 0
            
            while i < len(lines):
                line = lines[i]
                stripped = line.strip()
                
                # 跳過單獨的 emoji 或標記
                if stripped in {"📖", "�", "🎯", "�", "�", "🇯🇵", "內容概覽", "課程內容", "日文原文", "繁中解釋"}:
                    i += 1
                    continue
                
                # 檢測標題
                if stripped.startswith('##'):
                    # 向前查看，判斷是否有實質內容
                    j = i + 1
                    has_real_content = False
                    
                    while j < len(lines) and j < i + 20:  # 最多向前看20行
                        next_line = lines[j].strip()
                        
                        # 遇到下一個標題，停止
                        if next_line.startswith('#'):
                            break
                        
                        # 檢查是否為實質內容（非空、非emoji、非單一詞）
                        if (next_line and 
                            len(next_line) > 10 and  # 至少10字
                            not next_line in {"內容概覽", "課程內容", "日文原文", "繁中解釋", "---"} and
                            next_line not in {"📖", "📝", "🎯", "📄", "🌏"}):
                            has_real_content = True
                            break
                        
                        j += 1
                    
                    # 只保留有實質內容的標題
                    if has_real_content:
                        cleaned.append(line)
                    else:
                        # 跳過整個空白區塊
                        i = j
                        continue
                else:
                    # 非標題行，保留
                    if stripped:  # 只保留非空行
                        cleaned.append(line)
                
                i += 1
            
            enhanced_content = '\n'.join(cleaned)

            # 第二階段：智能解包程式碼區塊（區分真實程式碼與誤包的文本）
            import re

            def unwrap_if_text(m):
                lang = m.group(1) or ""
                body = m.group(2)
                
                # 計算內容特徵
                cjk = len(re.findall(r"[\u3040-\u30ff\u3400-\u9fff]", body))
                sym = len(re.findall(r"[{}();=\[\]<>/\\.:]", body))
                keywords = len(re.findall(r"\b(class|public|static|void|String|int|return|if|for|while)\b", body))
                total = max(len(body), 1)
                
                markdowny = re.search(r"(^|\n)\s*(#{1,6}\s+|[-*]\s+|\d+\.\s+|\|.+\|)", body)
                blockquote = re.search(r"(^|\n)\s*>", body)
                
                # 判斷是否為真實程式碼
                is_code = (
                    keywords >= 2 or  # 有多個程式關鍵字
                    (sym / total > 0.15 and lang.lower() in ['java', 'javascript', 'python', 'c', 'cpp']) or  # 符號密度高且標記為程式語言
                    re.search(r"(System\.out\.print|public\s+class|private\s+\w+|void\s+\w+\s*\()", body)  # 典型程式碼模式
                )

                # 強制解包：內容像敘述但被包在 code fence（尤其 LLM 誤包）
                if not is_code and lang:
                    return body

                # 若為純文本/目錄/日文原文/Markdown 結構，則解包
                if not is_code and (
                    (cjk / total > 0.25 and sym / total < 0.05) or
                    (markdowny and sym / total < 0.12 and keywords == 0) or
                    (blockquote and sym / total < 0.12 and keywords == 0) or
                    'jp-original-text' in body or
                    re.search(r"(^|\n)\s*(目次|目錄|章|節|項目一覧|原文|內容|學習重點|重點|摘要)\s*[:：]?", body)
                ):
                    return body
                
                return m.group(0)

            fence_pattern = re.compile(r"```(python|java|javascript|text|markdown|cpp|c)?\s*([\s\S]*?)```", re.IGNORECASE)
            enhanced_content = fence_pattern.sub(unwrap_if_text, enhanced_content)

            # 第三階段：強制清理日文原文區塊的程式碼包裹並轉為引用格式
            block_pattern = re.compile(r"(##\s*[^\n]*?日文原文[^\n]*?\n)```[^\n]*\n([\s\S]*?)\n```", re.IGNORECASE)
            def _force_unwrap_to_blockquote(m):
                header = m.group(1)
                body = m.group(2)
                # 移除所有 HTML 標籤
                body = re.sub(r"</?span[^>]*>", "", body)
                body = re.sub(r"</?mark[^>]*>", "", body)
                body = re.sub(r"</?div[^>]*>", "", body)
                # 轉換為 blockquote 格式
                lines = [line.strip() for line in body.splitlines() if line.strip()]
                blockquote = '\n'.join(f"> {line}" for line in lines)
                return header + blockquote
            enhanced_content = block_pattern.sub(_force_unwrap_to_blockquote, enhanced_content)

            # 第四階段：全域清理 HTML 標籤（保護程式碼區塊）
            parts = re.split(r"(```[\s\S]*?```)", enhanced_content)
            cleaned_parts = []
            for i, part in enumerate(parts):
                if part.startswith('```'):
                    # 程式碼區塊保持原樣
                    cleaned_parts.append(part)
                else:
                    # 非程式碼區塊：移除 HTML 標籤
                    part = re.sub(r"</?span[^>]*>", "", part)
                    part = re.sub(r"</?mark[^>]*>", "", part)
                    part = re.sub(r"</?div[^>]*>", "", part)
                    part = re.sub(r"</?p[^>]*>", "", part)
                    part = re.sub(r"</?(strong|em|b|i)[^>]*>", "", part)
                    cleaned_parts.append(part)
            enhanced_content = ''.join(cleaned_parts)
            
            # 第五階段：移除連續空行和無內容標題
            lines = enhanced_content.split('\n')
            
            # 5.1 移除多餘空行
            temp_lines = []
            empty_count = 0
            for line in lines:
                if not line.strip():
                    empty_count += 1
                    if empty_count <= 1:
                        temp_lines.append(line)
                else:
                    empty_count = 0
                    temp_lines.append(line)
            
            # 5.2 移除無內容標題
            final_lines = []
            i = 0
            while i < len(temp_lines):
                line = temp_lines[i]
                
                if line.strip().startswith('##'):
                    # 檢查後續是否有內容
                    j = i + 1
                    has_content = False
                    
                    while j < len(temp_lines):
                        next = temp_lines[j].strip()
                        if next.startswith('#'):  # 下一個標題
                            break
                        if next and next != '---':  # 有實質內容
                            has_content = True
                            break
                        j += 1
                    
                    if has_content or line.strip().startswith('# '):  # 保留 H1
                        final_lines.append(line)
                    else:
                        logger.debug(f"[NoteGenerator] 移除空標題: {line.strip()}")
                else:
                    final_lines.append(line)
                i += 1
            
            enhanced_content = '\n'.join(final_lines)
            
            # 如果包含日文學習內容，添加學習提示
            if include_japanese:
                # 添加時間戳
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                timestamp_labels = {
                    "zh-TW": f"📅 **分析時間**: {timestamp}",
                    "zh-CN": f"📅 **分析时间**: {timestamp}",
                    "ja": f"📅 **分析時刻**: {timestamp}",
                    "ko": f"📅 **분석 시간**: {timestamp}",
                    "en": f"📅 **Analysis Time**: {timestamp}"
                }
                
                timestamp_label = timestamp_labels.get(language, timestamp_labels["zh-TW"])
                enhanced_content = f"{timestamp_label}\n\n{enhanced_content}"
                
            # 停用：移除影像學習指南，改用藍圖格式  
            # learning_footer = self._get_image_learning_footer(language)
            # enhanced_content += f"\n\n---\n\n{learning_footer}"
            
            return enhanced_content
            
        except Exception as e:
            logger.error(f"[NoteGenerator] 內容增強失敗: {e}")
            return content
    
    def _get_image_learning_footer(self, language):
        """獲取圖片學習頁腳"""
        footers = {
            "zh-TW": """
## 🎓 學習指南

### 📖 複習建議
- **重點回顧**: 定期回顧重要概念和術語
- **實作練習**: 嘗試重現圖片中的程式碼範例
- **筆記整理**: 建立個人的學習筆記系統

### 🇯🇵 日文學習進階
- **術語記憶**: 建立日文技術術語卡片
- **發音練習**: 練習重要術語的正確發音
- **文檔閱讀**: 嘗試閱讀相關的日文技術文檔

### 🔗 延伸學習
- 探索相關的程式設計概念
- 參與日文程式設計社群討論
- 實作更複雜的專案範例

---
*💡 提示: 這份筆記是基於圖片內容的AI分析生成，建議結合實際課程內容進行學習。*
            """,
            "zh-CN": """
## 🎓 学习指南

### 📖 复习建议
- **重点回顾**: 定期回顾重要概念与术语
- **实践练习**: 尝试复现图片中的代码示例
- **笔记整理**: 建立个人的学习笔记系统

### 🇯🇵 日语学习进阶
- **术语记忆**: 建立日语技术术语卡片
- **发音练习**: 练习重要术语的正确发音
- **文档阅读**: 尝试阅读相关的日语技术文档

### 🔗 延伸学习
- 探索相关的编程概念
- 参与日语编程社群讨论
- 实作更复杂的项目示例

---
*💡 提示: 本笔记基于图片内容的 AI 分析生成，建议结合实际课程内容学习。*
            """,
            "ja": """
## 🎓 学習ガイド

### 📖 復習の提案
- **重要ポイントの復習**: 重要な概念や用語を定期的に復習
- **実践練習**: 画像のコード例を再現してみる
- **ノート整理**: 個人の学習ノートシステムを構築

### 🇯🇵 日本語学習の強化
- **用語記憶**: 日本語の技術用語カードを作成
- **発音練習**: 重要用語の正しい発音を練習
- **ドキュメント読解**: 関連する日本語の技術文書を読む

### 🔗 発展学習
- 関連するプログラミング概念を探求
- 日本語のプログラミングコミュニティに参加
- より複雑なプロジェクト例を実装

---
*💡 ヒント: このノートは画像内容の AI 解析に基づいて生成されています。実際の講義内容と合わせて学習することを推奨します。*
            """,
            "ko": """
## 🎓 학습 가이드

### 📖 복습 제안
- **핵심 복습**: 중요한 개념과 용어를 정기적으로 복습
- **실습 연습**: 이미지의 코드 예제 재현 시도
- **노트 정리**: 개인 학습 노트 시스템 구축

### 🇯🇵 일본어 학습 심화
- **용어 암기**: 일본어 기술 용어 카드 만들기
- **발음 연습**: 중요 용어의 정확한 발음 연습
- **문서 읽기**: 관련 일본어 기술 문서 읽기 시도

### 🔗 확장 학습
- 관련 프로그래밍 개념 탐색
- 일본어 프로그래밍 커뮤니티 토론 참여
- 더 복잡한 프로젝트 예제 구현

---
*💡 팁: 이 노트는 이미지 내용의 AI 분석을 기반으로 생성되었으므로, 실제 강의 내용과 함께 학습하는 것을 권장합니다.*
            """,
            "en": """
## 🎓 Learning Guide

### 📖 Review Suggestions
- **Key Review**: Regularly review important concepts and terminology
- **Practice Exercises**: Try to reproduce code examples from the image
- **Note Organization**: Build a personal learning note system

### 🇯🇵 Advanced Japanese Learning
- **Terminology Memory**: Create Japanese technical term flashcards
- **Pronunciation Practice**: Practice correct pronunciation of important terms
- **Document Reading**: Try reading related Japanese technical documentation

### 🔗 Extended Learning
- Explore related programming concepts
- Participate in Japanese programming community discussions
- Implement more complex project examples

---
*💡 Tip: This note is generated based on AI analysis of image content. It's recommended to combine it with actual course content for learning.*
            """
        }
        return footers.get(language, footers["zh-TW"])
    
    def format_video_note(self, content, scene_summaries, base_name, language="zh-TW", include_japanese=True):
        """
        格式化影片筆記
        
        Args:
            content: 筆記內容
            scene_summaries: 場景摘要列表
            base_name: 基本名稱
            language: 語言代碼
            include_japanese: 是否包含日文學習內容
        
        Returns:
            str: 格式化後的筆記
        """
        logger.info(f"[NoteGenerator] 格式化影片筆記: {base_name}, 語言: {language}, 包含日文: {include_japanese}")
        
        try:
            # 先處理圖片路徑與佔位符
            processed_content = self._process_image_paths(content, scene_summaries, base_name, language)

            # 影片專屬內容增強（時間戳、學習頁腳等）
            processed_content = self._enhance_video_note_content(processed_content, language, include_japanese)

            # 如果沒有任何標題，補上預設標題
            if not processed_content.lstrip().startswith('#'):
                if include_japanese:
                    title_map = {
                        "zh-TW": f"# 🇯🇵🇹🇼 雙語影片筆記 - {base_name}\n\n",
                        "zh-CN": f"# 🇯🇵🇨🇳 双语影片笔记 - {base_name}\n\n",
                        "ja": f"# 🇯🇵🇯🇵 バイリンガル動画ノート - {base_name}\n\n",
                        "en": f"# 🇯🇵🇺🇸 Bilingual Video Notes - {base_name}\n\n",
                        "ko": f"# 🇯🇵🇰🇷 이중 언어 영상 노트 - {base_name}\n\n"
                    }
                else:
                    title_map = {
                        "zh-TW": f"# 📼 影片筆記 - {base_name}\n\n",
                        "zh-CN": f"# 📼 影片笔记 - {base_name}\n\n",
                        "ja": f"# 📼 動画ノート - {base_name}\n\n",
                        "en": f"# 📼 Video Notes - {base_name}\n\n",
                        "ko": f"# 📼 영상 노트 - {base_name}\n\n"
                    }
                header = title_map.get(language, title_map["zh-TW"])
                processed_content = header + processed_content

            return processed_content
            
        except Exception as e:
            logger.error(f"[NoteGenerator] 格式化影片筆記失敗: {e}")
            return content
    
    def _process_image_paths(self, content, scene_summaries, base_name, language="zh-TW"):
        """處理筆記中的圖片路徑"""
        import re
        
        try:
            # 收集所有圖片路徑
            all_image_paths = []
            output_image_dir = os.path.join(OUTPUT_ROOT, 'images', base_name)
            os.makedirs(output_image_dir, exist_ok=True)
            
            for group in scene_summaries:
                image_paths = group.get('image_paths', [])
                for img_path in image_paths:
                    if img_path and img_path.startswith('/images/'):
                        all_image_paths.append(img_path)
            
            if not all_image_paths:
                # 移除圖片佔位符
                processed_content = re.sub(r'!\[([^\]]*)\]\([^)]*\)', '<!-- 圖片不可用 -->', content)
                return processed_content
            
            # 基於路徑值去重，避免重複圖片
            dedup_paths = []
            seen_paths = set()
            for p in all_image_paths:
                key = p.strip().lower()
                if key not in seen_paths:
                    seen_paths.add(key)
                    dedup_paths.append(p)

            # 替換圖片佔位符
            processed_content = content
            used_images = set()
            
            # 替換 {{image_placeholder}}
            placeholder_count = processed_content.count('{{image_placeholder}}')
            for i in range(min(placeholder_count, len(dedup_paths))):
                processed_content = processed_content.replace(
                    '{{image_placeholder}}', 
                    f'![課程截圖]({dedup_paths[i]})', 
                    1
                )
                used_images.add(i)
            
            # 替換其他圖片佔位符
            placeholder_pattern = r'!\[([^\]]*)\]\(實際圖片路徑\)'
            matches = re.findall(placeholder_pattern, processed_content)
            
            for i, alt_text in enumerate(matches):
                if i < len(dedup_paths):
                    img_index = i % len(dedup_paths)
                    while img_index in used_images and len(used_images) < len(dedup_paths):
                        img_index = (img_index + 1) % len(dedup_paths)
                    
                    used_images.add(img_index)
                    old_pattern = f'![{alt_text}](實際圖片路徑)'
                    new_pattern = f'![{alt_text}]({dedup_paths[img_index]})'
                    processed_content = processed_content.replace(old_pattern, new_pattern, 1)
            
            # 如果沒有圖片標記，在開頭添加
            if not re.search(r'!\[.*?\]\(.*?\)', processed_content) and dedup_paths:
                if '## ' in processed_content:
                    first_h2_pos = processed_content.find('## ')
                    next_line_pos = processed_content.find('\n', first_h2_pos)
                    if next_line_pos != -1:
                        insert_pos = next_line_pos + 1
                        img_markdown = f"\n![課程截圖]({dedup_paths[0]})\n\n"
                        processed_content = processed_content[:insert_pos] + img_markdown + processed_content[insert_pos:]
                else:
                    img_markdown = f"![課程截圖]({dedup_paths[0]})\n\n"
                    processed_content = img_markdown + processed_content
            
            return processed_content
            
        except Exception as e:
            logger.error(f"[NoteGenerator] 處理圖片路徑失敗: {e}")
            return content

    def _enhance_video_note_content(self, content, language, include_japanese):
        """增強影片筆記內容：加入生成時間與影片學習指南（避免與通用增強重複）。"""
        try:
            enhanced = content

            # 生成時間（置於頂部且不干擾既有 H1）
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            ts_labels = {
                "zh-TW": f"🕒 生成時間：{timestamp}",
                "zh-CN": f"🕒 生成时间：{timestamp}",
                "ja": f"🕒 生成時刻：{timestamp}",
                "en": f"🕒 Generated: {timestamp}",
                "ko": f"🕒 생성 시간: {timestamp}"
            }
            ts_line = ts_labels.get(language, ts_labels["zh-TW"]) + "\n\n"

            # 僅在頂端沒有旗標或時間標時插入一次
            head = enhanced.lstrip()
            if not (head.startswith("🇯🇵") or head.startswith("🕒") or head.startswith("# ")):
                enhanced = ts_line + enhanced

            # 注意：學習建議/影片學習指南將在最終階段以動態內容統一插入
            # 這裡不再追加頁腳，以免與最終整合的區塊重複

            return enhanced
        except Exception as e:
            logger.error(f"[NoteGenerator] 影片內容增強失敗: {e}")
            return content

    def _get_video_learning_footer(self, language):
        """停用：完全移除影片學習指南。改用藍圖格式生成筆記"""
        return ""

    def _extract_japanese_key_points(self, ocr_text: str, max_points: int = 3) -> list:
        """從 OCR 文字中提取日文重點"""
        if not ocr_text:
            return []
        
        # 先過濾個人資訊
        from modules.summarize_video import _filter_personal_info
        filtered_ocr = _filter_personal_info(ocr_text)
        
        import re
        lines = filtered_ocr.split('\n')
        key_points = []
        
        # 過濾噪音行
        filtered_lines = []
        for line in lines:
            line = line.strip()
            if line and not self._is_noise_line(line):
                filtered_lines.append(line)
        
        # 尋找重要內容
        for line in filtered_lines[:10]:  # 只檢查前10行
            if any(keyword in line for keyword in ['重要', 'ポイント', '概念', '定義', '方法', '機能', 'はじめに', 'サーバ']):
                if len(key_points) < max_points:
                    key_points.append(line)
        
        # 如果沒有找到重要行，取前幾行
        if not key_points and filtered_lines:
            key_points = filtered_lines[:max_points]
        
        return key_points[:max_points]

    def _is_vlm_output_insufficient(self, content: str) -> bool:
        """檢測 VLM 回傳內容是否不足以填滿章節結構。"""
        if not content:
            return True
        plain = self._strip_markdown_to_plain(content)
        if not plain:
            return True
        if len(plain.strip()) < 80:
            return True
        failure_markers = (
            "內容生成中遇到問題",
            "請稍後再試",
            "生成中遇到問題",
            "暫時無法提供內容",
        )
        if any(marker in content for marker in failure_markers):
            return True
        lines = [ln.strip() for ln in plain.splitlines() if ln.strip()]
        if len(lines) < 3:
            return True
        return False

    def _prune_simple_vocab_sections(self, content: str) -> str:
        """刪除或過濾已存在的詞彙表中太簡單的詞。"""
        if not content:
            return content
        try:
            pattern = re.compile(r"(##\s+📚[^\n]*\n)([\s\S]+?)(?=\n##|\Z)")
            def _clean_section(match: re.Match) -> str:
                header = match.group(1)
                body = match.group(2)
                rows = body.splitlines()
                filtered: List[str] = []
                for row in rows:
                    row_stripped = row.strip()
                    if row_stripped.startswith("|") and row_stripped.endswith("|") and row.count("|") >= 4:
                        lower_row = row_stripped.lower()
                        if any(term.lower() in lower_row for term in COMMON_VOCAB_TERMS):
                            continue
                    filtered.append(row)
                # 如果剩下的資料行少於 1 (header + separator + data)，移除整段
                data_line_count = sum(
                    1 for line in filtered if line.strip().startswith("|") and line.count("|") >= 4
                ) - 1
                if data_line_count <= 0:
                    return ""
                return header + "\n".join(filtered)
            return pattern.sub(_clean_section, content)
        except Exception:
            return content

    async def _normalize_scene_summary(
        self,
        content: str,
        language: str,
        ocr_text: str,
    ) -> str:
        """標準化 ImageAnalyzer 產出的章節內容，確保符合 Blueprint 格式。"""
        cleaned = (content or "").strip()
        if not cleaned:
            return ""
        try:
            formatted = await format_vlm_output(cleaned, language, ocr_text=ocr_text)
            formatted = markdown_cleaner.clean_markdown(formatted)
            formatted = self._clean_garbled_code_blocks(formatted)
            return formatted.strip()
        except Exception as exc:
            logger.warning(
                "[NoteGenerator] 📄 無法正規化場景摘要，直接使用原始內容: %s",
                exc,
            )
            return cleaned

    def _should_reuse_structured_scene(self, scene_info: Dict[str, Any]) -> bool:
        """判斷場景摘要是否已包含完整章節結構，可直接複用。"""
        summary = (scene_info.get("summary") or "").strip()
        if len(summary) < 120:
            return False
        if "資訊不足" in summary or "請重新檢查" in summary:
            return False
        normalized = summary.strip()
        if normalized.startswith("# "):
            return True
        if any(token in normalized for token in ("## 🎯", "## 🇯🇵", "## 🇺🇸", "## 📖")):
            return True
        return False

    def _build_fallback_chapter_explanation(self, scene_info: Dict[str, Any], language: str) -> Tuple[str, str]:
        """使用場景摘要與 OCR 內容組裝備援的章節說明與補充。"""
        strings = self._get_language_strings(language)
        fallback_strings = strings.get("fallbacks", {})
        summary = scene_info.get("summary") or ""
        summary_plain = self._strip_markdown_to_plain(summary)
        segments = self._split_text_for_segments(summary_plain, max_chunk=140)

        def _clean_segment(seg: str) -> str:
            cleaned = re.sub(r"\s+", " ", seg or "").strip(" -•\u2022")
            return cleaned.strip()

        explanation_items: List[str] = []
        for seg in segments:
            cleaned = _clean_segment(seg)
            if cleaned:
                explanation_items.append(cleaned)
            if len(explanation_items) >= 4:
                break

        if not explanation_items:
            asr_plain = self._strip_markdown_to_plain(scene_info.get("asr_text") or "")
            for seg in self._split_text_for_segments(asr_plain, max_chunk=140):
                cleaned = _clean_segment(seg)
                if cleaned:
                    explanation_items.append(cleaned)
                if len(explanation_items) >= 4:
                    break

        if not explanation_items:
            explanation_items.append(
                fallback_strings.get("summary")
                or "Content is insufficient. Please review the original slides."
            )

        explanation_block = "\n".join(f"- {item}" for item in explanation_items)

        supplement_items: List[str] = []
        remaining_segments = segments[len(explanation_items):] if len(segments) > len(explanation_items) else []
        for seg in remaining_segments:
            cleaned = _clean_segment(seg)
            if cleaned:
                supplement_items.append(cleaned)
            if len(supplement_items) >= 3:
                break

        if not supplement_items and scene_info.get("asr_text"):
            asr_snippet = self._strip_markdown_to_plain(scene_info["asr_text"])[:120].strip()
            if asr_snippet:
                supplement_items.append(f"語音補充：{asr_snippet}")

        if not supplement_items:
            supplement_items.append(
                fallback_strings.get("supplement")
                or "Please review the slide manually to add missing key points."
            )

        supplement_block = "\n".join(f"- {item}" for item in supplement_items)
        return explanation_block, supplement_block
    
    def _dedupe_learning_sections(self, text: str, language: str) -> str:
        """移除重複的區塊，保留第一個。

        覆蓋的標題（大小寫/emoji/語言/『JP 』前綴變體皆視為同一）：
        - 日文原文 Top-5
        - 學習建議 / Learning Suggestions / Study Suggestions
        - 影片學習指南 / Video Learning Guide
        - 日文學習重點 / Japanese Focus
        """
        try:
            import re

            def canonical(h: str) -> str:
                base = re.sub(r"[📖🎬🇯🇵\s]+", " ", h).strip()  # 去 emoji/多空白
                base = re.sub(r"^JP\s+", "", base, flags=re.IGNORECASE)
                base = base.lower()
                # 映射同義
                synonyms = {
                    '學習建議': 'learn_tips',
                    'learning suggestions': 'learn_tips',
                    'study suggestions': 'learn_tips',
                    '影片學習指南': 'video_guide',
                    'video learning guide': 'video_guide',
                    '日文學習重點': 'jp_focus',
                    'japanese focus': 'jp_focus',
                    '日文原文 top-5': 'jp_top5',
                }
                # 取前 16 字做模糊匹配
                for k, v in synonyms.items():
                    if base.startswith(k):
                        return v
                return base

            lines = text.split('\n')
            keep = []
            seen_keys = set()
            i = 0
            while i < len(lines):
                line = lines[i]
                m = re.match(r"^##\s*(.*)$", line)
                if m:
                    key = canonical(m.group(1))
                    if key in {'jp_top5', 'learn_tips', 'video_guide', 'jp_focus'}:
                        if key in seen_keys:
                            # 跳過到下一個 H2 或文尾
                            i += 1
                            while i < len(lines) and not re.match(r"^##\s+", lines[i]):
                                i += 1
                            continue
                        seen_keys.add(key)
                keep.append(line)
                i += 1
            return '\n'.join(keep)
        except Exception:
            return text
    
    async def generate_final_summary(self, scene_summaries, language="zh-TW", include_japanese=True):
        """
        生成最終總結 - 使用與圖片處理相同的簡潔方式,嚴格過濾無關內容
        
        Args:
            scene_summaries: 場景摘要列表
            language: 輸出語言
            include_japanese: 是否包含日文學習內容
        
        Returns:
            str: 最終總結內容
        """
        logger.info(f"[NoteGenerator] 開始生成最終總結 - 語言: {language}, 包含日文: {include_japanese}")
        prompt_bundle = self._ensure_prompt_bundle()
        language_strings = self._get_language_strings(language)
        chapter_strings = language_strings.get("chapter", {})
        chapter_title_label = chapter_strings.get("title", "Chapter")
        image_label = chapter_strings.get("image_label", "Slide Screenshot")
        detail_heading_label = chapter_strings.get("detail_heading", "## 📖 Key Explanations")
        jp_heading_label = chapter_strings.get("jp_heading", "## 📝 Japanese Reference")
        supplement_heading_label = chapter_strings.get("supplement_heading", "## 💡 Supplemental Insights")
        glossary_hint_label = chapter_strings.get(
            "glossary_hint", "Please refer to the glossary below for related concepts."
        )
        self.last_note_metadata = {
            "note_style": "blueprint",
            "source": "vlm",
            "prompt_profile": self._prompt_profile,
        }
        self.last_note_metadata.update(
            {
                "language": language,
                "include_japanese": include_japanese,
                "language_mode": self._infer_language_mode(language, include_japanese),
            }
        )
        language_mode = self._infer_language_mode(language, include_japanese)
        runtime_config = self._load_runtime_config()
        output_cfg = runtime_config.get('output', {}) if isinstance(runtime_config, dict) else {}
        requested_note_style = str(output_cfg.get('note_style', 'blueprint') or 'blueprint').strip().lower()
        if requested_note_style in {'summary', 'meeting', 'minutes', 'meetingmode'}:
            requested_note_style = 'meeting'
        elif requested_note_style in {'detailed', 'lecture', 'blueprint', 'lecturemode'}:
            requested_note_style = 'blueprint'
        elif requested_note_style == 'bilinote':
            requested_note_style = 'transcript'
        self.last_note_metadata["note_style"] = requested_note_style
        use_optimized = (self._prompt_profile == 'optimized')
        image_prompt_factory = prompt_bundle.image_prompt
        logger.info(f"[NoteGenerator] 📦 接收到的 scene_summaries 類型: {type(scene_summaries)}")
        logger.info(f"[NoteGenerator] 📦 接收到的 scene_summaries 長度: {len(scene_summaries) if scene_summaries else 0}")
        if scene_summaries:
            logger.info(f"[NoteGenerator] 📦 第一個場景的鍵: {list(scene_summaries[0].keys()) if scene_summaries[0] else 'N/A'}")
        
        try:
            # 【新架構】VLM-First: 收集場景圖片+OCR,直接讓VLM分析圖片
            scene_data = []  # 收集 {image_path, ocr_text}
            logger.info(f"[NoteGenerator] 🎯 VLM-First模式: 開始處理場景,總數: {len(scene_summaries)}")
            
            for idx, scene in enumerate(scene_summaries):
                logger.info(f"[NoteGenerator] 🔍 檢查場景 {idx}")
                
                # 獲取圖片路徑和OCR文字
                image_path_web = scene.get('image_path_final', '').strip()  # 保存原始Web路徑
                ocr_text = scene.get('ocr_text', '').strip()
                
                # 🔧 轉換Web路徑為文件系統路徑
                # image_path_final 格式: '/images/視頻名/scene_000.jpg'
                # 轉換為: 'output/images/視頻名/scene_000.jpg'
                image_path = convert_web_path_to_fs(image_path_web)
                
                logger.info(f"[NoteGenerator] 場景 {idx} 原始數據: {scene.keys()}")
                logger.info(f"[NoteGenerator] 場景 {idx} 圖片路徑: '{image_path}'")
                logger.info(f"[NoteGenerator] 場景 {idx} 圖片: {image_path[-50:] if image_path else '(無)'}")
                logger.info(f"[NoteGenerator] 場景 {idx} OCR長度: {len(ocr_text)}")
                
                missing_image = False
                skip_reason = None

                if not image_path:
                    missing_image = True
                    skip_reason = "無圖片路徑"
                    logger.warning(f"[NoteGenerator] ⚠️ 場景 {idx} 無圖片路徑，保留章節")
                elif not os.path.exists(image_path):
                    missing_image = True
                    skip_reason = f"圖片不存在 {image_path}"
                    logger.warning(f"[NoteGenerator] ⚠️ 場景 {idx} 圖片不存在，保留章節")
                
                # 🔧 改進噪音過濾邏輯:
                # 因為課程都在 Google Classroom 中進行,不能過濾 google.com
                # 只過濾明確是系統畫面/無內容的場景
                noise_keywords = [
                    'file explorer', 'ファイルエクスプローラ',
                    'chrome://settings', 'chrome://extensions'
                ]
                
                # 極度寬鬆的過濾策略: 只過濾明確的系統畫面
                skip_scene = False
                if ocr_text:
                    ocr_lower = ocr_text.lower()
                    
                    # 只有在以下情況才跳過:
                    # 1. OCR極短(<10字符)且全是系統關鍵字
                    # 2. 明確是檔案總管畫面
                    if 'file explorer' in ocr_lower or 'ファイルエクスプローラ' in ocr_lower:
                        ocr_len = len(ocr_text.strip())
                        if ocr_len < 30:  # 只在內容極少時才過濾
                            logger.info(f"[NoteGenerator] ⚠️ 場景 {idx} 跳過檔案總管畫面 (OCR長度: {ocr_len})")
                            skip_scene = True
                    
                    # 檢查chrome設定頁面
                    if 'chrome://settings' in ocr_lower or 'chrome://extensions' in ocr_lower:
                        logger.info(f"[NoteGenerator] ⚠️ 場景 {idx} 跳過瀏覽器設定頁面")
                        skip_scene = True
                
                if skip_scene:
                    logger.info(f"[NoteGenerator] ⚠️ 場景 {idx} 標記為噪音場景，保留章節")
                
                # ✅ 不再檢查日文比例!讓VLM直接看圖片決定
                logger.info(f"[NoteGenerator] ✅ 場景 {idx} 接受 (VLM將分析圖片)")
                
                scene_data.append({
                    'index': idx,
                    'image_path': image_path,  # 文件系統路徑(用於讀取)
                    'image_path_web': image_path_web,  # Web路徑(用於Markdown顯示)
                    'ocr_text': ocr_text,
                    'missing_image': missing_image,
                    'skip_scene': skip_scene,
                    'skip_reason': skip_reason,
                    'summary': scene.get('summary', '')
                })
            
            # 如果沒有有效場景,返回空筆記
            if not scene_data:
                logger.warning(f"[NoteGenerator] 沒有找到有效的場景圖片")
                return "# 無相關講義內容\n\n此影片中未檢測到相關的程式設計講義內容。\n\n可能原因:\n- 影片主要是瀏覽器畫面或系統操作\n- 無法提取場景截圖\n- 影片內容與程式設計無關", []
            
            
            logger.info(f"[NoteGenerator] 📊 有效場景: {len(scene_data)} 個")

            def _average_hash(image_path: str) -> Optional[int]:
                if not image_path:
                    return None
                try:
                    with Image.open(image_path) as img:
                        resample_space = getattr(Image, "Resampling", None)
                        if resample_space:
                            resample_alg = getattr(
                                resample_space,
                                "LANCZOS",
                                getattr(resample_space, "NEAREST", 0),
                            )
                        else:
                            resample_alg = getattr(
                                Image,
                                "LANCZOS",
                                0,
                            )
                        img = img.convert("L").resize((8, 8), resample_alg)
                        pixels = list(cast(Iterable[int], img.getdata()))
                except Exception as exc:
                    logger.debug("[NoteGenerator] 無法計算影像 hash (%s): %s", image_path, exc)
                    return None
                avg = sum(pixels) / len(pixels)
                bits = 0
                for idx, value in enumerate(pixels):
                    if value >= avg:
                        bits |= (1 << idx)
                return bits

            def _hash_distance(a: Optional[int], b: Optional[int]) -> Optional[int]:
                if a is None or b is None:
                    return None
                return int(bin(a ^ b).count("1"))

            def _normalize_text_for_compare(text: Optional[str]) -> str:
                if not text:
                    return ""
                return re.sub(r"\s+", "", text)

            def _merge_ocr_text(base: str, addition: str) -> str:
                base_lines = [line.strip() for line in (base or "").splitlines() if line.strip()]
                add_lines = [line.strip() for line in (addition or "").splitlines() if line.strip()]
                merged: List[str] = []
                for line in base_lines + add_lines:
                    if line and line not in merged:
                        merged.append(line)
                return "\n".join(merged)

            def _dedupe_markdown_sections(markdown: str) -> str:
                """移除章節內重複的段落與清單項目，避免 VLM 產生重複內容。"""
                if not markdown:
                    return markdown
                try:
                    from modules.note_formatter import _clean_duplicate_content
                except Exception:
                    _clean_duplicate_content = None  # type: ignore

                text = markdown
                if _clean_duplicate_content:
                    try:
                        text = _clean_duplicate_content(text)
                    except Exception:
                        pass

                lines = text.splitlines()
                result_lines: List[str] = []
                seen_bullets: Set[str] = set()
                for line in lines:
                    stripped = line.strip()
                    if not stripped:
                        result_lines.append(line)
                        continue

                    bullet_key: Optional[str] = None
                    if stripped.startswith(("- ", "* ")):
                        bullet_key = stripped[2:].strip().lower()
                    else:
                        match = re.match(r"^\d+\.\s+(.*)", stripped)
                        if match:
                            bullet_key = match.group(1).strip().lower()

                    if bullet_key:
                        if bullet_key in seen_bullets:
                            continue
                        seen_bullets.add(bullet_key)

                    result_lines.append(line)

                cleaned: List[str] = []
                blank_count = 0
                for line in result_lines:
                    if line.strip():
                        blank_count = 0
                        cleaned.append(line)
                    else:
                        blank_count += 1
                        if blank_count <= 2:
                            cleaned.append(line)

                return "\n".join(cleaned).strip()

            merge_identical_scenes = False
            deduped_scene_data: List[Dict[str, Any]] = []
            for scene_info in scene_data:
                scene_info["_primary_ocr"] = scene_info.get("ocr_text") or ""
                image_hash = _average_hash(scene_info.get("image_path"))
                scene_info["image_hash"] = image_hash
                normalized_text = _normalize_text_for_compare(scene_info["_primary_ocr"])

                if deduped_scene_data:
                    prev_scene = deduped_scene_data[-1]
                    prev_hash = prev_scene.get("image_hash")
                    prev_primary_norm = _normalize_text_for_compare(prev_scene.get("_primary_ocr"))
                    distance = _hash_distance(image_hash, prev_hash)
                    same_text = normalized_text and normalized_text == prev_primary_norm
                    should_merge = False
                    if merge_identical_scenes and distance is not None and distance == 0 and same_text and len(normalized_text) >= 120:
                        should_merge = True
                    elif merge_identical_scenes and same_text and len(normalized_text) >= 260:
                        should_merge = True

                    if should_merge:
                        logger.info(
                            "[NoteGenerator] 🔁 場景 %s 與上一張投影片相似 (hash距離=%s)，合併處理",
                            scene_info["index"],
                            distance,
                        )
                        prev_scene["ocr_text"] = _merge_ocr_text(prev_scene.get("ocr_text") or "", scene_info.get("ocr_text") or "")
                        merged_indices = prev_scene.setdefault("merged_indices", [])
                        merged_indices.append(scene_info["index"])
                        prev_scene.setdefault("merged_images", []).append(scene_info.get("image_path"))
                        prev_scene.setdefault("merged_ocr_blocks", []).append(scene_info.get("ocr_text") or "")

                        prev_len = len(prev_primary_norm)
                        curr_len = len(normalized_text)
                        if curr_len >= prev_len:
                            logger.info(
                                "[NoteGenerator] 📸 場景 %s 內容更完整 (字元: %s > %s)，更新主圖像",
                                scene_info["index"],
                                curr_len,
                                prev_len,
                            )
                            prev_scene["_primary_ocr"] = scene_info.get("ocr_text") or prev_scene.get("_primary_ocr") or ""
                            prev_scene["image_path"] = scene_info.get("image_path")
                            prev_scene["image_path_web"] = scene_info.get("image_path_web", "")
                            prev_scene["index"] = scene_info["index"]
                            prev_scene["image_hash"] = image_hash
                        continue

                deduped_scene_data.append(scene_info)

            if len(deduped_scene_data) != len(scene_data):
                logger.info(
                    "[NoteGenerator] ✅ 投影片去重：原始 %s 張，合併後 %s 張",
                    len(scene_data),
                    len(deduped_scene_data),
                )

            if scene_summaries:
                try:
                    scene_summaries = [scene_summaries[info["index"]] for info in deduped_scene_data]
                except Exception as exc:
                    logger.debug("[NoteGenerator] 無法按去重結果重建 scene_summaries: %s", exc)

            if requested_note_style == "meeting":
                structured_summaries = self._group_related_scenes(scene_summaries)
                final_note = self._build_meeting_minutes_from_scenes(deduped_scene_data, language)
                self.last_note_metadata.update(
                    {
                        "note_style": "meeting",
                        "source": "meeting_minutes",
                        "sections": {"chapters": len(deduped_scene_data)},
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                logger.info(
                    "[NoteGenerator] ✅ 會議模式快速輸出: scenes=%s",
                    len(deduped_scene_data),
                )
                return final_note, structured_summaries

            # 🎯 VLM-First: 對每個場景使用VLM分析圖片+OCR，生成獨立章節
            all_chapter_notes = []
            for scene_info in deduped_scene_data:
                idx = scene_info['index']
                image_path = scene_info['image_path']  # 文件系統路徑
                image_path_web = scene_info.get('image_path_web', '')  # Web路徑(用於Markdown)
                ocr_text = scene_info['ocr_text']
                missing_image = scene_info.get('missing_image')
                skip_scene = scene_info.get('skip_scene')
                skip_reason = scene_info.get('skip_reason')
                
                logger.info(f"[NoteGenerator] 🖼️ 章節 {idx + 1}: 調用VLM分析圖片...")
                
                formatted_note = ""
                supplement_override: Optional[str] = None
                used_scene_summary = False

                raw_summary = (scene_info.get("summary") or "").strip()
                if missing_image:
                    reason = skip_reason or "圖片不存在"
                    formatted_note = f"**圖片缺失**：{reason}。請重新同步圖片資料夾後再生成。"
                    used_scene_summary = True
                elif skip_scene:
                    fallback_body, fallback_supplement = self._build_fallback_chapter_explanation(
                        scene_info, language
                    )
                    formatted_note = fallback_body
                    supplement_override = fallback_supplement
                    used_scene_summary = True
                if raw_summary:
                    formatted_note = await self._normalize_scene_summary(
                        raw_summary,
                        language,
                        ocr_text,
                    )
                    formatted_note = self._prune_simple_vocab_sections(formatted_note)
                    if formatted_note and not self._is_vlm_output_insufficient(formatted_note):
                        used_scene_summary = True
                        logger.info(
                            "[NoteGenerator] 🔁 章節 %s: 重用 ImageAnalyzer 摘要 (len=%s)",
                            idx + 1,
                            len(formatted_note),
                        )

                if not used_scene_summary:
                    if raw_summary and not formatted_note:
                        logger.info(
                            "[NoteGenerator] ℹ️ 章節 %s: 原摘要為空或格式不足，轉為重新生成",
                            idx + 1,
                        )
                    if use_optimized:
                        logger.info(f"[NoteGenerator] ✅ 章節 {idx + 1}: 使用優化版 Blueprint Prompt (語言: {language})")
                        vlm_prompt = image_prompt_factory(
                            ocr_text if ocr_text else "",
                            language_code=language,
                            context=scene_info.get('asr_text') or scene_info.get('context') or "",
                            has_ocr=bool(ocr_text.strip()) if isinstance(ocr_text, str) else False,
                            language_mode=language_mode,
                        )
                        logger.info(f"[NoteGenerator] 📊 Prompt 長度: {len(vlm_prompt)} 字元")
                    else:
                        logger.info(f"[NoteGenerator] 使用舊版 Prompt (語言: {language})")
                        vlm_prompt = image_prompt_factory(
                            ocr_text if ocr_text else "",
                            language_code=language,
                            context=scene_info.get('asr_text') or scene_info.get('context') or "",
                            has_ocr=bool(ocr_text.strip()) if isinstance(ocr_text, str) else False,
                            language_mode=language_mode,
                        )
                    
                    try:
                        if not image_path or not os.path.exists(image_path):
                            raise FileNotFoundError(image_path or "(missing image)")
                        with open(image_path, 'rb') as f:
                            image_data = f.read()
                        image_b64 = base64.b64encode(image_data).decode('utf-8')
                        prepare_llm_inference("note-generator:image-chapter")
                        scene_note = await call_llm(
                            prompt=vlm_prompt,
                            model=self.llm_config.get('final_model', 'qwen3-vl:4b'),
                            image=image_b64,
                            use_cache=False,
                            language=language,
                            extra={"temperature": 0.3, "max_tokens": 2048}
                        )
                        if scene_note and scene_note.strip():
                            logger.info(f"[NoteGenerator] ✅ 章節 {idx + 1} VLM重新生成 ({len(scene_note)} 字)")
                            formatted_note = await format_vlm_output(
                                scene_note.strip(),
                                language,
                                ocr_text=ocr_text,
                            )
                            formatted_note = markdown_cleaner.clean_markdown(formatted_note)
                            formatted_note = self._clean_garbled_code_blocks(formatted_note)
                            formatted_note = self._prune_simple_vocab_sections(formatted_note)
                        else:
                            logger.warning(f"[NoteGenerator] ⚠️ 章節 {idx + 1} VLM返回空內容")
                    except Exception as e:
                        logger.error(f"[NoteGenerator] ❌ 章節 {idx + 1} VLM調用失敗: {e}")
                        if ocr_text:
                            chapter_title = f"# {chapter_title_label} {idx + 1}\n\n![{image_label}]({image_path_web})\n\n"
                            chapter_content = chapter_title + f"```\n{ocr_text[:300]}\n```\n\n---\n\n"
                            all_chapter_notes.append(chapter_content)
                        continue

                if image_path_web.startswith('/app/'):
                    image_path_web = image_path_web.replace('/app/', '/images/')
                elif not image_path_web.startswith('/images/'):
                    image_path_web = f"/images/{image_path_web}"
                image_path_web = image_path_web.replace('//', '/')
                
                chapter_sections = [
                    f"# {chapter_title_label} {idx + 1}",
                    "",
                    f"![{image_label}]({image_path_web})" if image_path_web else f"*({image_label} unavailable)*",
                    ""
                ]

                formatted_note_clean = (formatted_note or "").strip()
                jp_key_points = self._extract_japanese_key_points(ocr_text)
                has_jp_section = "② 日文重點大綱" in formatted_note_clean
                if jp_key_points and not has_jp_section:
                    chapter_sections.append("## ② 日文重點大綱（原講義語言）")
                    chapter_sections.extend(f"- {point}" for point in jp_key_points if point)
                    chapter_sections.append("")

                has_detail_section = (
                    "③ 母語解析" in formatted_note_clean
                    or "重點說明（中文解釋" in formatted_note_clean
                    or "重點說明（中文解释" in formatted_note_clean
                    or "📖 重點說明" in formatted_note_clean
                )

                if not formatted_note_clean or self._is_vlm_output_insufficient(formatted_note_clean):
                    fallback_body, fallback_supplement = self._build_fallback_chapter_explanation(
                        scene_info, language
                    )
                    formatted_note_clean = fallback_body
                    supplement_override = fallback_supplement
                    has_detail_section = False

                if formatted_note_clean:
                    if not has_detail_section:
                        chapter_sections.append("## ③ 母語解析（中文）")
                    chapter_sections.append(formatted_note_clean)
                else:
                    chapter_sections.append("*(VLM 未產生可用內容)*")

                has_glossary_hint = "請參考下方術語表了解相關概念" in formatted_note_clean
                has_glossary_section = "關鍵術語" in formatted_note_clean or "術語" in formatted_note_clean
                if supplement_override:
                    chapter_sections.append("")
                    chapter_sections.append("## ⑥ 補充說明 / 延伸理解")
                    chapter_sections.append(supplement_override)
                elif has_glossary_section and not has_glossary_hint:
                    chapter_sections.append("## ⑥ 補充說明 / 延伸理解")
                    chapter_sections.append(glossary_hint_label)

                chapter_body = "\n".join(chapter_sections).strip()
                chapter_body = _dedupe_markdown_sections(chapter_body)
                if not chapter_body:
                    chapter_body = "*(VLM 未產生可用內容)*"
                chapter_content = chapter_body + "\n\n---\n\n"
                all_chapter_notes.append(chapter_content)
            
            # 如果所有VLM調用都失敗
            if not all_chapter_notes:
                logger.warning(f"[NoteGenerator] 所有VLM調用失敗,使用fallback")
                return "# 無法生成筆記\n\n無法分析場景圖片內容。", []
            
            # 合併所有章節
            logger.info("[NoteGenerator] 📚 章節輸出完成，共 %s 章", len(all_chapter_notes))
            final_note = "\n".join(all_chapter_notes)
            final_note = markdown_cleaner.clean_markdown(final_note)
            final_note = self._clean_garbled_code_blocks(final_note)
            section_presence = {"chapters": len(all_chapter_notes)}

            self.last_note_metadata.update(
                {
                    "target_locale": language,
                    "include_japanese": include_japanese,
                    "sections": section_presence,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            )

            logger.info(f"[NoteGenerator] 🎉 VLM-First模式完成,總長度: {len(final_note)} 字")

            # 插入日文原文重點（僅限 transcript 樣式）
            if include_japanese and scene_summaries and self.last_note_metadata.get("note_style") == "transcript":
                final_note = self._inject_ocr_verbatim_block(final_note, scene_summaries, language)
                logger.info(f"[NoteGenerator] ✅ 已插入日文原文重點")

            # 簡單的結構化數據(用於圖片路徑處理)
            structured_summaries = self._group_related_scenes(scene_summaries)

            # 檢查是否需要生成詳細講義版本
            runtime_config = self._load_runtime_config()
            output_cfg = runtime_config.get('output', {}) if isinstance(runtime_config, dict) else {}
            transcript_cfg = (
                output_cfg.get('transcript_notes')
                or output_cfg.get('bilinote')  # 兼容舊版設定鍵
                or {}
            )
            note_style = output_cfg.get('note_style', 'blueprint')
            if note_style == 'bilinote':  # 舊版別名
                note_style = 'transcript'
            use_transcript_notes = requested_note_style == 'transcript' or bool(transcript_cfg.get('enabled')) or note_style == 'transcript'

            if requested_note_style == 'meeting':
                use_transcript_notes = False

            if use_transcript_notes:
                try:
                    transcript_markdown = await self._generate_detailed_transcript_notes(
                        scene_summaries,
                        language,
                        transcript_cfg,
                    )
                    if transcript_markdown:
                        cleaned_transcript = transcript_markdown.strip()
                        cleaned_transcript = cleaned_transcript.replace("\r\n", "\n").strip()
                        if cleaned_transcript.startswith("```") and cleaned_transcript.endswith("```"):
                            cleaned_transcript = self._strip_enclosing_code_fences(cleaned_transcript)
                        if not cleaned_transcript.startswith("#"):
                            cleaned_transcript = f"# 教學講義\n\n{cleaned_transcript}"
                        final_note = cleaned_transcript.strip()
                        self.last_note_metadata = {
                            "note_style": "transcript",
                            "source": "transcript_notes",
                            "use_transcript": True,
                            "language": language,
                            "include_japanese": include_japanese,
                            "language_mode": self._infer_language_mode(language, include_japanese),
                        }
                        logger.info("[NoteGenerator] ✅ 已生成 transcript 詳細教學筆記")
                    else:
                        logger.warning("[NoteGenerator] ⚠️ transcript 詳細筆記輸出為空，保留原筆記格式")
                except Exception as transcript_error:  # pragma: no cover - runtime safeguard
                    logger.error(
                        "[NoteGenerator] ❌ transcript 詳細筆記生成失敗: %s",
                        transcript_error,
                        exc_info=True,
                    )

            return final_note, structured_summaries
            
        except Exception as e:
            logger.error(f"[NoteGenerator] 生成最終總結失敗: {e}")
            # Fallback: 生成基本筆記
            logger.warning(f"[NoteGenerator] 使用 fallback 生成基本筆記")
            try:
                structured_summaries = self._group_related_scenes(scene_summaries)
                basic_note = self._generate_basic_note_from_scenes(structured_summaries, language)
                return basic_note, structured_summaries
            except Exception as e2:
                logger.error(f"[NoteGenerator] Fallback 也失敗: {e2}")
                return "# 筆記生成失敗\n\n無法生成筆記內容。", []

    def _build_meeting_minutes_from_scenes(self, scene_data: List[Dict[str, Any]], language: str) -> str:
        """Build meeting-mode notes per scene with JP speech points and Chinese explanation."""
        import re

        is_zh = str(language).lower().startswith("zh")
        title = "# 會議重點整理" if is_zh else "# Meeting Highlights"

        def _clean_line(text: str) -> str:
            s = (text or "").strip()
            if not s:
                return ""
            s = re.sub(r"```[\s\S]*?```", " ", s)
            s = re.sub(r"```[^\n]*", " ", s)
            s = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1", s)
            s = re.sub(r"\s+", " ", s)
            s = s.strip("-• ")
            if s.startswith("```"):
                return ""
            return s

        def _split_candidates(text: str) -> List[str]:
            sanitized = re.sub(r"```[\s\S]*?```", " ", text or "")
            chunks: List[str] = []
            for line in sanitized.splitlines():
                cleaned = _clean_line(line)
                if not cleaned or len(cleaned) < 6:
                    continue
                chunks.append(cleaned)
            return chunks

        def _jp_points(scene: Dict[str, Any]) -> List[str]:
            asr_text = str(scene.get("asr_text") or scene.get("context") or "")
            ocr_text = str(scene.get("ocr_text") or "")
            candidates = _split_candidates(asr_text) or _split_candidates(ocr_text)
            if not candidates:
                return []
            return self._dedupe_similar_lines(list(dict.fromkeys(candidates)), threshold=0.84)[:3]

        def _zh_points(scene: Dict[str, Any]) -> List[str]:
            summary = str(scene.get("summary") or "")
            ocr_text = str(scene.get("ocr_text") or "")
            candidates = _split_candidates(summary) or _split_candidates(ocr_text)
            if not candidates:
                return []
            return self._dedupe_similar_lines(list(dict.fromkeys(candidates)), threshold=0.84)[:3]

        def _norm_image_path(path: str) -> str:
            p = (path or "").strip()
            if not p:
                return ""
            if p.startswith("/app/"):
                p = p.replace("/app/", "/images/")
            elif not p.startswith("/images/"):
                p = f"/images/{p}"
            return p.replace("//", "/")

        lines: List[str] = [title, ""]
        scene_count = 0
        for scene in scene_data:
            scene_count += 1
            image_path = _norm_image_path(str(scene.get("image_path_web") or ""))
            jp_points = _jp_points(scene)
            zh_points = _zh_points(scene)

            lines.append(f"## 場景 {scene_count}" if is_zh else f"## Scene {scene_count}")
            if image_path:
                lines.append(f"![會議截圖 {scene_count}]({image_path})" if is_zh else f"![Meeting Screenshot {scene_count}]({image_path})")
            lines.append("")

            lines.append("### 日文語音重點" if is_zh else "### Japanese Speech Key Points")
            if jp_points:
                lines.extend([f"- {item}" for item in jp_points])
            else:
                lines.append("- （本場景未擷取到足夠日文語音內容）" if is_zh else "- (No sufficient Japanese speech captured in this scene)")
            lines.append("")

            lines.append("### 中文重點整理" if is_zh else "### Chinese Summary")
            if zh_points:
                lines.extend([f"- {item}" for item in zh_points])
            else:
                lines.append("- （本場景資訊不足，請搭配截圖人工確認）" if is_zh else "- (Insufficient scene details; please verify with screenshot)")
            lines.append("")

        return "\n".join(lines).strip()
    
    def _clean_duplicate_content(self, text: str) -> str:
        """清理重複內容，特別是日文原文和中文解釋的重複"""
        try:
            import re
            
            # 移除重複的日文原文段落
            lines = text.split('\n')
            cleaned_lines = []
            seen_japanese = set()
            seen_chinese = set()
            
            i = 0
            while i < len(lines):
                line = lines[i]
                
                # 檢查是否為日文原文標題
                if re.match(r'^##\s*[📝🇯🇵]*\s*日文原文', line):
                    # 收集日文原文內容
                    japanese_content = []
                    i += 1
                    while i < len(lines) and not re.match(r'^##\s*', lines[i]):
                        japanese_content.append(lines[i])
                        i += 1
                    
                    # 檢查是否重複
                    content_key = ' '.join(japanese_content).strip()
                    if content_key and content_key not in seen_japanese:
                        seen_japanese.add(content_key)
                        cleaned_lines.append(line)
                        cleaned_lines.extend(japanese_content)
                    # 跳過重複內容
                    continue
                
                # 檢查是否為中文解釋標題
                elif re.match(r'^##\s*[🌏🇹🇼]*\s*繁中解釋', line):
                    # 收集中文解釋內容
                    chinese_content = []
                    i += 1
                    while i < len(lines) and not re.match(r'^##\s*', lines[i]):
                        chinese_content.append(lines[i])
                        i += 1
                    
                    # 檢查是否重複
                    content_key = ' '.join(chinese_content).strip()
                    if content_key and content_key not in seen_chinese:
                        seen_chinese.add(content_key)
                        cleaned_lines.append(line)
                        cleaned_lines.extend(chinese_content)
                    # 跳過重複內容
                    continue
                
                else:
                    cleaned_lines.append(line)
                    i += 1
            
            return '\n'.join(cleaned_lines)
            
        except Exception as e:
            logger.error(f"[NoteGenerator] 清理重複內容失敗: {e}")
            return text
    
    def _group_related_scenes(self, scene_summaries):
        """將相關場景分組"""
        # 簡化版本：每個場景作為一個組
        grouped_scenes = []
        for i, scene in enumerate(scene_summaries):
            group = {
                'group_index': i,
                'scenes': [scene],
                'combined_summary': scene.get('summary', ''),
                'image_paths': [scene.get('image_path_final', '')] if scene.get('image_path_final') else []
            }
            grouped_scenes.append(group)
        
        return grouped_scenes
    
    def _format_scenes_for_prompt(self, structured_summaries):
        """格式化場景數據用於提示詞"""
        import json
        return json.dumps(structured_summaries, ensure_ascii=False, indent=2)
    
    def _get_language_specific_prompt(self, structured_summaries, language="zh-TW"):
        """根據語言生成特定的提示詞 - 修正為簡潔筆記格式"""
        scenes_json = self._format_scenes_for_prompt(structured_summaries)
        
        if language == "en":
            return f"""You are a classroom note-taker for a Japanese programming course. Create CONCISE lecture notes from these scenes.

Scene Data:
{scenes_json}

**CRITICAL REQUIREMENTS:**
1. **Format**: Classroom notes, NOT a textbook chapter
2. **Length**: Each scene should be 200-500 words MAX (not thousands)
3. **Deduplication**: If multiple scenes show the same slide/concept, merge them into ONE entry
4. **Focus**: Only core concepts, key terms, and essential code examples
5. **Style**: Bullet points, short paragraphs, clear structure

**Output Format (use this structure):**

# [Course Topic from scenes]

## Scene N: [Brief scene description]

**Key Points:**
- [Point 1]
- [Point 2]
- [Point 3]

**Japanese Terms:** (if applicable)
> [Original Japanese text from slide]

**Code Example:** (if applicable)
```[language]
[Essential code only]
```

**AVOID:**
- Repetitive section headers like "Learning Objectives", "Deep Analysis"
- Excessive emojis (use sparingly: max 2-3 per scene)
- Lengthy explanations (keep under 500 words per scene)
- Duplicate content across scenes

Be concise, focus on actionable notes."""
        else:
            # 中文提示詞 - 修正為簡潔格式
            return f"""你是日文程式設計課程的課堂筆記員。請從這些場景截圖製作**簡潔的課堂筆記**。

場景資料：
{scenes_json}

**重要要求**：
1. **格式**：這是課堂筆記，不是完整的教科書章節
2. **長度**：每個場景 200-500 字以內（不是數千字）
3. **去重**：如果多個場景顯示相同投影片/概念，合併成一條記錄
4. **重點**：只記錄核心概念、關鍵術語和必要的程式碼範例
5. **風格**：多用列表、短段落、清晰結構

**輸出格式（使用此結構）：**

# [從場景推斷的課程主題]

## 場景 N：[場景簡述]

**重點**：
- [要點 1]
- [要點 2]  
- [要點 3]

**日文原文**：（如有）
> [投影片上的原文]

**程式碼範例**：（如有）
```[語言]
[只保留關鍵程式碼]
```

**禁止**：
- 重複的章節標題如「學習目標」、「深度解析」、「延伸建議」
- 過多 emoji（每場景最多 2-3 個）
- 冗長解釋（每場景 500 字以內）
- 跨場景重複內容

保持簡潔，專注於可操作的筆記。"""

    def _enhance_note_content(self, note_content, language, include_japanese):
        """增強筆記內容格式和結構 - 深度清理與優化"""
        try:
            text = note_content or ""

            # 第一階段：保護程式碼區塊，清理其他區域
            import re
            parts = re.split(r"(```[\s\S]*?```)", text)
            cleaned = []
            for seg in parts:
                if seg.startswith('```'):
                    # 程式碼區塊：只做基礎清理
                    code = seg
                    # 移除程式碼區塊內的 HTML 標籤（避免渲染問題）
                    code = re.sub(r"</?span[^>]*>", "", code)
                    code = re.sub(r"</?mark[^>]*>", "", code)
                    cleaned.append(code)
                    continue
                
                s = seg
                # 全面清理 HTML 標籤和屬性
                s = re.sub(r"</?span[^>]*>", "", s, flags=re.IGNORECASE)
                s = re.sub(r"</?mark[^>]*>", "", s, flags=re.IGNORECASE)
                s = re.sub(r"</?(div|p|br|font|strong|em|b|i|u)[^>]*>", "", s, flags=re.IGNORECASE)
                s = re.sub(r"</?h[1-6][^>]*>", "", s, flags=re.IGNORECASE)
                
                # 移除內聯樣式和屬性
                s = re.sub(r'\s*style="[^"]*"', '', s, flags=re.IGNORECASE)
                s = re.sub(r'\s*class="[^"]*"', '', s, flags=re.IGNORECASE)
                s = re.sub(r'\s*id="[^"]*"', '', s, flags=re.IGNORECASE)
                s = re.sub(r'\s*data-[^=]*="[^"]*"', '', s, flags=re.IGNORECASE)
                
                # 清理色碼殘留
                s = re.sub(r'"?color:\s*#[0-9a-fA-F]{3,8}"?', '', s)
                s = re.sub(r'#[0-9a-fA-F]{6}>', '', s)
                
                # 規整空白與換行
                s = s.replace("\r", "")
                s = re.sub(r"[ \t]+\n", "\n", s)
                s = re.sub(r"\n{3,}", "\n\n", s)
                s = re.sub(r"[ \t]{2,}", " ", s)
                
                cleaned.append(s)
            
            enhanced_content = ''.join(cleaned)
            
            # 第二階段：移除冗餘的標記文字與重複章節標題
            redundant_phrases = [
                r"以下是根據.*?的.*?筆記[:：]?\s*",
                r"根據.*?內容.*?整理[:：]?\s*",
                r"這是.*?的.*?分析[:：]?\s*",
                r"本節將.*?介紹[:：]?\s*"
            ]
            for pattern in redundant_phrases:
                enhanced_content = re.sub(pattern, "", enhanced_content, flags=re.IGNORECASE)

            # 移除任務/練習類 blockquote（避免誤渲染為 UI 卡片）
            task_line_re = re.compile(r"(任務|任务|課題|タスク|task)", re.IGNORECASE)
            filtered_task_lines = []
            skip_task_block = False
            for line in enhanced_content.split("\n"):
                stripped = line.strip()
                if skip_task_block:
                    if stripped.startswith(">"):
                        continue
                    if not stripped:
                        skip_task_block = False
                        continue
                    skip_task_block = False
                if stripped.startswith(">") and task_line_re.search(stripped):
                    skip_task_block = True
                    continue
                filtered_task_lines.append(line)
            enhanced_content = "\n".join(filtered_task_lines)
            
            # 移除重複的通用章節標題（LLM 過度擴寫的產物）
            # 僅保留新結構 ②–⑥，避免舊版標題被視為合法段落
            repetitive_headers = [
                r"^##?\s*🎯\s*[學学]習主[題题]\s*$",
                r"^##?\s*📚\s*內容概述\s*$",
                r"^##?\s*📖\s*[內内]容[詳详]解\s*$",
                r"^##?\s*💡\s*重點[說说]明\s*$",
                r"^##?\s*🔧\s*補充[資资][訊讯]\s*$",
                r"^##?\s*🎓\s*延伸[學学]習[建议]\s*$",
                r"^##?\s*核心日文術[語语][詳详]解\s*$",
                r"^##?\s*(?:📋\s*)?關鍵詞彙表\s*$",
                r"^##?\s*(?:🧩\s*)?Vocabulary\s*$",
                r"^##?\s*(?:📌\s*)?練習題\s*$",
                r"^##?\s*(?:❓\s*)?Quiz\s*$",
                r"^##?\s*(?:🧠\s*)?考點速覽\s*$",
                r"^##?\s*(?:📖\s*)?概念講解\s*$",
                r"^##?\s*(?:💻\s*)?範例程式\s*$",
                r"^##?\s*(?:❓\s*)?Q&A\s*$",
                r"^##?\s*(?:🔎\s*)?關鍵術語對照\s*$"
            ]
            lines_temp = enhanced_content.split('\n')
            filtered_lines = []
            for line in lines_temp:
                stripped = line.strip()
                is_repetitive = any(re.match(pat, stripped, re.IGNORECASE) for pat in repetitive_headers)
                if not is_repetitive:
                    filtered_lines.append(line)
                else:
                    logger.debug(f"[NoteGenerator] 移除重複標題: {stripped}")
            enhanced_content = '\n'.join(filtered_lines)
            
            # 第三階段：優化標題與段落結構
            lines = enhanced_content.split('\n')
            optimized = []
            prev_was_empty = False
            
            for line in lines:
                stripped = line.strip()
                
                # 跳過多餘空行
                if not stripped:
                    if not prev_was_empty:
                        optimized.append(line)
                        prev_was_empty = True
                    continue
                
                prev_was_empty = False
                
                # 優化標題格式（確保 # 後有空格）
                if stripped.startswith('#'):
                    if not re.match(r'^#+\s', stripped):
                        stripped = re.sub(r'^(#+)', r'\1 ', stripped)
                
                # 優化列表項（確保 - 後有空格）
                if stripped.startswith('-') and not stripped.startswith('- '):
                    stripped = '- ' + stripped[1:].lstrip()
                
                optimized.append(stripped if line.strip() else '')
            
            enhanced_content = '\n'.join(optimized)
            
            # 第四階段：添加語言標識（僅當不存在時）
            if include_japanese and not enhanced_content.lstrip().startswith('🇯🇵'):
                language_flags = {
                    "zh-TW": "🇯🇵🇹🇼",
                    "zh-CN": "🇯🇵🇨🇳", 
                    "ko": "🇯🇵🇰🇷",
                    "en": "🇯🇵🇺🇸"
                }
                flag = language_flags.get(language, "🇯🇵🇹🇼")
                enhanced_content = f"{flag} **雙語學習筆記**\n\n{enhanced_content}"
            
            return enhanced_content
            
        except Exception as e:
            logger.error(f"[NoteGenerator] 內容增強失敗: {e}")
            return note_content

    def _collect_top_jp_lines(self, scene_summaries, max_lines: int = 5):
        """從各場景收集 OCR 擷取的日文原文 Top-N（去重、保序）。"""
        jp_raw = []
        for sc in (scene_summaries or []):
            for ln in (sc.get('jp_top_lines') or []):
                ln = (ln or '').strip()
                if not ln:
                    continue
                jp_raw.append(ln)
        # 先做嚴格去重，再用相似度去重
        uniq = []
        seen = set()
        for ln in jp_raw:
            if ln in seen:
                continue
            seen.add(ln)
            uniq.append(ln)
        dedup = self._dedupe_similar_lines(uniq, threshold=0.85)
        return dedup[:max_lines]

    def _ensure_top_jp_section(self, note_text: str, scene_summaries, language: str) -> str:
        """若缺少『日文原文 Top-5』，基於 OCR 內容補齊一段；不移除既有內容。"""
        try:
            import re
            text = note_text or ""
            # 若已存在 Top 區塊則不動
            if re.search(r"^##\s*.*(日文原文|JP|Japanese).*(Top|Top\s*-?\s*\d+)", text, flags=re.IGNORECASE | re.MULTILINE):
                return text
            # 收集 Top JP 行
            top_lines = self._collect_top_jp_lines(scene_summaries, max_lines=5)
            if not top_lines:
                return text
            header = "## 🇯🇵 日文原文 Top-5" if language.startswith('zh') else "## Japanese Top-5"
            lines = "\n".join([f"- {ln}" for ln in top_lines])
            block = f"{header}\n\n{lines}\n\n"
            # 插到第一個 H2 前（或文首）
            pos = text.find("\n## ")
            if pos != -1:
                return text[:pos+1] + block + text[pos+1:]
            return block + text
        except Exception:
            return note_text

    def _inject_ocr_verbatim_block(self, note_text: str, scene_summaries, language: str) -> str:
        """在筆記前段插入『日文原文重點』，只顯示最重要的內容，避免冗長顯示。"""
        try:
            # 移除重複的日文原文區塊
            import re
            note_text = re.sub(r'^##\s*🇯🇵\s*日文原文.*?\n(?=##|\Z)', '', note_text, flags=re.MULTILINE | re.DOTALL)
            note_text = re.sub(r'^##\s*日本語原文.*?\n(?=##|\Z)', '', note_text, flags=re.MULTILINE | re.DOTALL)

            # 收集重點內容（只取最重要的 1-2 行）
            key_points = []
            for sc in (scene_summaries or []):
                ocr = (sc.get('ocr_text') or '').replace('\r','\n').split('\n')
                ocr = [ln.strip() for ln in ocr if ln.strip()]
                # 雜訊過濾
                ocr = [ln for ln in ocr if not self._is_noise_line(ln)]
                if not ocr:
                    continue
                
                # 只取最重要的 1-2 行，優先選擇包含關鍵詞的行
                important_lines = []
                for line in ocr[:5]:  # 只檢查前5行
                    if any(keyword in line for keyword in ['重要', 'ポイント', '概念', '定義', '方法', '機能']):
                        important_lines.append(line)
                        if len(important_lines) >= 2:
                            break
                
                # 如果沒有找到重要行，取前1行
                if not important_lines and ocr:
                    important_lines = [ocr[0]]
                
                if important_lines:
                    key_points.extend(important_lines)
                    if len(key_points) >= 3:  # 最多3個重點
                        break
            
            if not key_points:
                return note_text
            
            # 簡潔的格式
            header = "## 📝 日文原文重點\n\n"
            for i, point in enumerate(key_points[:3], 1):
                header += f"{i}. {point}\n"
            header += "\n"
            # 插在第一個 H2 區塊之前
            pos = note_text.find("\n## ")
            if pos != -1:
                return note_text[:pos] + "\n" + header + note_text[pos:]
            return header + note_text
        except Exception:
            return note_text

    def _clean_garbled_code_blocks(self, note_text: str) -> str:
        """掃描 Markdown 代碼區塊，移除長串括號亂碼。"""
        try:
            import re
            text = note_text or ""
            if "```" not in text:
                return text

            pattern = re.compile(r"```([^\n]*)\n([\s\S]*?)```")

            def _is_code_line(line: str) -> bool:
                stripped = line.strip()
                if not stripped:
                    return True
                lower = stripped.lower()
                # 明確的噪音關鍵字
                noise_keywords = [
                    "spanclass",
                    "&lt;",
                    "&gt;",
                    "&quot",
                    "| 學",
                    "學習主題",
                    "內容概述",
                    "關鍵概念",
                    "表格",
                    "reinforcement",
                    "狀態轉移",
                    "行動策略",
                    "學習重點",
                    "內容概述",
                    "摘要",
                    "問題描述",
                    "<math",
                    "<mrow",
                    "<msup",
                    "<mfrac",
                    "<msub",
                    "<mtable",
                    "mathjax",
                    "math-block",
                    "<img",
                    "src=",
                    "style=",
                    "###",
                    "##",
                ]
                if any(k in lower for k in noise_keywords):
                    return False
                if stripped.startswith(("#", "*", "-", "•", ">")):
                    return False
                # 明確的程式碼提示
                code_tokens = [
                    ";",
                    "{",
                    "}",
                    "(",
                    ")",
                    "class",
                    "public",
                    "private",
                    "static",
                    "void",
                    "int",
                    "double",
                    "String",
                    "return",
                    "//",
                    "/*",
                    "*/",
                    "new ",
                    "Math.",
                    "System.out",
                ]
                has_code_token = any(tok in stripped for tok in code_tokens)
                ends_like_code = stripped.endswith((";", "{", "}", "*/")) or "*/" in stripped or "//" in stripped

                # 字符統計
                ascii_count = sum(1 for ch in stripped if ord(ch) < 128)
                non_ascii = len(stripped) - ascii_count

                # 過長且非 ASCII 為主的行通常是敘述
                if len(stripped) > 120 and non_ascii > ascii_count:
                    return False
                # 非 ASCII 比例很高且沒有明顯程式碼標記時，判定為敘述
                if non_ascii > ascii_count * 0.7 and not has_code_token and not ends_like_code:
                    return False

                # 允許含程式碼關鍵字/符號或結尾有程式碼特徵的行
                if has_code_token or ends_like_code:
                    return True
                # 允許 ASCII 為主的短行
                return ascii_count >= non_ascii and any(ch in stripped for ch in ";{}()")

            def _cleanup(match):
                lang = match.group(1) or ""
                body = match.group(2)
                # strip lingering HTML/MathML tags inside code fences
                body = re.sub(r"<[^>\n]+>", "", body)
                cleaned_body, changed = self._trim_brace_noise(body)

                filtered_lines = [ln for ln in cleaned_body.splitlines() if _is_code_line(ln)]
                # 若混入大量非程式碼，且過濾後行數小於 2，則嘗試保留原始前幾行以免完全清空
                if len(filtered_lines) < 2:
                    filtered_lines = [
                        ln for ln in cleaned_body.splitlines() if len(ln.strip()) <= 160 and any(ch in ln for ch in ";{}()")
                    ][:8]
                if filtered_lines:
                    cleaned_body = "\n".join(filtered_lines)
                    changed = changed or True

                if not changed:
                    return match.group(0)
                lang_header = f"```{lang}\n"
                return f"{lang_header}{cleaned_body}\n```"

            return pattern.sub(_cleanup, text)
        except Exception as exc:  # pragma: no cover - 防禦性處理
            logger.warning(f"[NoteGenerator] 代碼亂碼清理失敗: {exc}")
            return note_text

    def _trim_brace_noise(self, code: str) -> Tuple[str, bool]:
        """從程式碼片段中刪除過長的括號噪音序列。"""
        try:
            lines = code.splitlines()
            cleaned: List[str] = []
            changed = False
            i = 0

            def is_noise(line: str) -> bool:
                stripped = line.strip()
                if not stripped:
                    return False
                return all(ch in "{}[]()" for ch in stripped)

            while i < len(lines):
                if is_noise(lines[i]):
                    start = i
                    while i < len(lines) and is_noise(lines[i]):
                        i += 1
                    run_len = i - start
                    if run_len >= 8:
                        indent_match = re.match(r"^\s*", lines[start])
                        indent = indent_match.group(0) if indent_match else ""
                        cleaned.append(f"{indent}// ⚠️ 自動清理：已移除 {run_len} 行僅含括號的異常輸出")
                        changed = True
                        continue
                    cleaned.extend(lines[start:i])
                    continue

                cleaned.append(lines[i])
                i += 1

            if not changed:
                return code.rstrip(), False
            return "\n".join(cleaned).rstrip(), True
        except Exception:
            return code, False

    def _is_noise_line(self, line: str) -> bool:
        """判斷 OCR 行是否為雜訊：網址、Meet 系統提示、僅時間戳等。"""
        import re
        s = (line or '').strip()
        if not s:
            return True
        # URL / 會議連結 / email
        if re.search(r"https?://|www\.|meet\.google\.com|bit\.ly|goo\.gl", s, flags=re.IGNORECASE):
            return True
        if re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", s):
            return True
        # 系統提示（中/英/日/簡）
        sys_phrases = [
            "錄影已開始", "錄影已停止", "正在錄影", "您正在展示", "你正在分享", "You are presenting", "Recording has started",
            "joined the meeting", "left the meeting", "ミーティング", "録画を開始", "録画を停止"
        ]
        for ph in sys_phrases:
            if ph.lower() in s.lower():
                return True
        # 純時間戳或括號時間
        if re.fullmatch(r"\[?\(?\d{1,2}:\d{2}(?::\d{2})?\)?\]?", s):
            return True
        if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}(\s+\d{1,2}:\d{2}(:\d{2})?\s*(AM|PM|am|pm)?)?", s):
            return True
        return False

    def _normalize_text_for_similarity(self, text: str) -> str:
        import re
        t = (text or '').strip()
        t = re.sub(r"\s+", "", t)
        t = re.sub(r"[\p{P}\p{S}]", "", t) if hasattr(re, 'UNICODE') else re.sub(r"[\W_]+", "", t, flags=re.UNICODE)
        return t.lower()

    def _dedupe_similar_lines(self, lines, threshold: float = 0.85):
        """用相似度去重，保留順序。避免 Top-5 出現近似重複句。"""
        try:
            from difflib import SequenceMatcher
            kept = []
            norms = []
            for ln in lines:
                n = self._normalize_text_for_similarity(ln)
                is_dup = False
                for kn in norms:
                    if SequenceMatcher(None, n, kn).ratio() >= threshold:
                        is_dup = True
                        break
                if not is_dup:
                    kept.append(ln)
                    norms.append(n)
            return kept
        except Exception:
            return list(dict.fromkeys(lines))

    def _highlight_keywords(self, note_text: str) -> str:
        """高亮 equals / == / StringBuilder / String（僅非程式碼區塊）。"""
        import re
        parts = re.split(r"(```[\s\S]*?```)", note_text or "")
        out = []
        for seg in parts:
            if seg.startswith('```'):
                out.append(seg)
                continue
            s = seg
            # 避免重複包裹已是反引號的
            def wrap(pattern, repl):
                return re.sub(pattern, repl, s, flags=re.IGNORECASE)
            s = wrap(r"\bStringBuilder\b", r"`StringBuilder`")
            s = wrap(r"\bString\b", r"`String`")
            s = wrap(r"(?<!`)==(?!=)`?", r"`==`")
            s = wrap(r"\bequals\s*\(\)", r"`equals()`")
            out.append(s)
        return ''.join(out)

    def _append_code_analysis(self, note_text: str, language: str, scene_summaries) -> str:
        """在程式碼區塊後追加執行結果分析與逐行說明 - 優化版"""
        import re
        text = note_text or ""
        blocks = list(re.finditer(r"```[\s\S]*?```", text))
        if not blocks:
            return text
        
        inserts = []
        zh = language.startswith('zh')
        
        # 優化標題與內容
        analysis_title = "\n#### 🧪 執行結果分析\n" if zh else "\n#### 🧪 Execution Analysis\n"
        guide_template = """
**預期輸出**：
```
{output}
```

**關鍵說明**：
- **第 1 行**：{explanation}
- **輸出結果**：{result_explanation}

""" if zh else """
**Expected Output**:
```
{output}
```

**Key Points**:
- **Line 1**: {explanation}
- **Result**: {result_explanation}

"""
        
        for m in reversed(blocks):  # 從後往前避免位移
            end = m.end()
            tail = text[end: end + 300]
            
            # 檢查是否已有分析
            if re.search(r"(執行結果|結果分析|逐行|Execution|Expected Output)", tail):
                continue
            
            # 提取程式碼內容以生成智能分析
            code_content = m.group(0)
            lang_match = re.match(r"```(\w+)", code_content)
            code_lang = lang_match.group(1) if lang_match else "unknown"
            code_body = re.search(r"```\w*\n([\s\S]*?)\n```", code_content)
            
            if code_body:
                body = code_body.group(1).strip()
                # 簡單智能分析
                output_guess = "// 輸出結果將顯示在這裡" if zh else "// Output will be shown here"
                explanation = "程式碼執行邏輯" if zh else "Code execution logic"
                result_exp = "根據程式邏輯推斷" if zh else "Inferred from code logic"
                
                # Java println 檢測
                if 'System.out.print' in body:
                    prints = re.findall(r'System\.out\.print(?:ln)?\s*\(\s*"([^"]*)"\s*\)', body)
                    if prints:
                        output_guess = '\n'.join(prints)
                        result_exp = "輸出字串內容" if zh else "String output"
                
                insert = analysis_title + guide_template.format(
                    output=output_guess,
                    explanation=explanation,
                    result_explanation=result_exp
                )
            else:
                insert = analysis_title + (
                    "程式碼邏輯分析將在此顯示\n" if zh else "Code analysis will be shown here\n"
                )
            
            inserts.append((end, insert))
        
        for pos, ins in inserts:
            text = text[:pos] + ins + text[pos:]
        
        return text

    # 已停用的舊版詞彙/測驗插入邏輯：避免影像筆記混入舊樣式
    def _inject_vocab_table(self, note_text: str, language: str, scene_summaries) -> str:  # pragma: no cover
        return note_text

    def _enhance_quiz(self, note_text: str, language: str, scene_summaries) -> str:  # pragma: no cover
        return note_text

    def _inject_toc(self, note_text: str) -> str:
        """在頂部插入章節目錄（依據 H2/H3）。"""
        import re
        text = note_text or ""
        # 找到第一個 H1 之後插入
        lines = text.split('\n')
        anchors = []
        for ln in lines:
            m = re.match(r"^(##+)\s+(.+)$", ln)
            if m:
                level = len(m.group(1))
                title = m.group(2).strip()
                # 生成簡單 anchor（GitHub 風格簡化版）
                anchor = re.sub(r"[^a-zA-Z0-9\u3040-\u30ff\u3400-\u9fff\s-]", "", title).strip().lower()
                anchor = anchor.replace(' ', '-')
                anchors.append((level, title, anchor))
        if not anchors:
            return text
        toc_lines = ["## 目錄", ""]
        for level, title, anchor in anchors[:30]:
            indent = "  " * (level - 2) if level >= 2 else ""
            toc_lines.append(f"{indent}- [{title}](#{anchor})")
        toc = "\n".join(toc_lines) + "\n\n"
        # 插入在第一個 H1 之後或文首
        if lines and lines[0].startswith('# '):
            return lines[0] + "\n\n" + toc + "\n".join(lines[1:])
        return toc + text

    def _filter_out_of_context_lines(self, note_text: str, scene_summaries) -> str:
        """放寬過濾：盡量保留內容，只刪明顯雜訊/模板短句。"""
        try:
            import re
            text = note_text or ""
            # 構建弱匹配詞袋
            bag = set()
            for sc in (scene_summaries or []):
                for src in ((sc.get('ocr_text') or ''), (sc.get('asr_text') or '')):
                    for tok in re.findall(r"[\u3040-\u30ff\u3400-\u9fffA-Za-z0-9_+./:-]{2,}", src):
                        bag.add(tok.lower())
            if not bag:
                return text
            paragraphs = text.split('\n\n')
            kept = []
            for para in paragraphs:
                pl = para.strip().lower()
                if not pl:
                    continue
                # 永遠保留：標題/程式碼/表格/清單
                if pl.startswith('#') or pl.startswith('```') or pl.startswith('|') or pl.startswith('- '):
                    kept.append(para)
                    continue
                # 段落較長則保留
                if len(para) >= 100:
                    kept.append(para)
                    continue
                # 與證據有重疊則保留
                toks = re.findall(r"[\u3040-\u30ff\u3400-\u9fffA-Za-z0-9_+./:-]{2,}", pl)
                if any(t in bag for t in toks):
                    kept.append(para)
                    continue
                # 短且無證據重疊：視為模板短句 → 丟棄
            return '\n\n'.join(kept)
        except Exception:
            return note_text

    def _build_dynamic_guides(self, scene_summaries, language: str) -> str:
        """已停用：根據藍圖格式，不再生成冗餘的學習建議和影片學習指南"""
        # 直接返回空值，避免舊式學習建議干擾藍圖格式
        return ""
    
    def _get_enhanced_prompt(self, structured_summaries, language, content_type):
        """根據最佳輸出結果藍圖生成結構化筆記提示詞"""
        # 安全構建：避免JSON中包含的字符引起 format 問題
        scenes_json = self._format_scenes_for_prompt(structured_summaries)
        # 若JSON包含特殊字符，先編碼以避免format崩潰 
        if scenes_json:
            import json
            try:
                # 檢查JSON正確性並清理'风险'字段名
                import re
                scenes_str = json.dumps(structured_summaries, ensure_ascii=False, indent=2)
                # 去除意外出現 { 的存在避免擾亂模板
                scenes_json_safe = str(scenes_str)
            except Exception:
                # 作為最後 resort，避免 format error，改用原始字符串
                scenes_json_safe = str(scenes_json) if scenes_json else ""
        else:
            scenes_json_safe = ""

        # 獲取語言特定的系統提示詞
        from modules.llm_utils import get_language_system_prompt
        system_prompt = get_language_system_prompt(
            language,
            content_type,
            include_japanese=(content_type == "bilingual")
        )

        # 使用安全字符串替換以避免 bro ken format issues
        extra = """
【STRICT REQUIREMENT：生成完全藍圖格式筆記】

【輸入資料】
{SCENES_PLACEHOLDER}

【輸出必以藍圖格式】

# [課程名稱 - 日期]

## 濃縮重點摘要
| 日文 | 中文 |
|------|------|  
| [實際要點1] | [對應說明1] |
| [實際要點2] | [對應說明2] |

## 目錄  
1. [日文標題A] - [中文標題A] ([時間戳]/頁碼)
2. [日文標題B] - [中文標題B] ([時間戳]/頁碼)

## 章節內容

### [章節日文標題] - [章節中文標題]

**學習要點**  
- [JP原文1] → [ZH解釋1] ◎考 ASR:[時間]
- [JP原文2] → [ZH解釋2] ★必背 OCR:[頁碼]
- [JP原文3] → [ZH解釋3] ⚠誤 講義:[頁碼]

**章節回顧**  
[3-5句重點]
[2-3個練習題，格式：Q: [JP問題]/[ZH翻譯] A: [答案]源:[來源]]

## 附錄

### 術語表
| 日文術語 | 中文對獲 | 說明 | 首次位置 |
|----------|----------|------|----------|  
| [術語1] | [對應1] | [解釋] | [位置] |

### 來源索引  
- ASR：[時間段] (具體內容摘要)
- OCR第[序列號頁][講義語義]

【強制剪切指導】:
1) STRICT – 不准生成任何沒有在輸入SCENES JSON內的內容
2) STRICT NO LEGACY – 嚴禁生成"學習建議"、"影片學習指南"、"學習重點"等無關模版內容
3) 嚴格藍圖格式保證（pip tables・雙標◎★⚠必須準確）
4) 來源必須有精確出處（ASR時間帶・OCR頁・講橫頁面編號）
5) 長度控制∶ 7 ≤ 每章要點 ≤ 10總擇點（總濃縮區）
"""

        # 將佔位符替換為實際的JSON資料（安全 avoid format problems）
        safe_extra = extra.replace("{SCENES_PLACEHOLDER}", scenes_json_safe)
        return f"{system_prompt}\n\n{safe_extra}".strip()
    
    def _get_simple_fallback_prompt(self, structured_summaries, language, include_japanese):
        """生成簡化的fallback提示詞"""
        try:
            # 提取關鍵信息
            scenes_text = ""
            for i, group in enumerate(structured_summaries):
                scenes_text += f"\n場景 {i+1}:\n"
                for scene in group.get('scenes', []):
                    if scene.get('summary'):
                        scenes_text += f"- {scene['summary']}\n"
                    if scene.get('ocr_text'):
                        scenes_text += f"- OCR: {scene['ocr_text'][:200]}...\n"
            
            if language.startswith('zh'):
                return f"""請根據以下場景資料生成學習筆記：

{scenes_text}

請生成包含以下內容的筆記：
1. 課程標題
2. 主要學習內容
3. 重要概念
4. 實用建議

使用繁體中文，格式要清晰易讀。"""
            else:
                return f"""Please generate study notes based on the following scene data:

{scenes_text}

Please include:
1. Course title
2. Main learning content  
3. Key concepts
4. Practical suggestions

Use clear and readable format."""
        except Exception as e:
            logger.error(f"[NoteGenerator] 生成簡化提示詞失敗: {e}")
            return "請生成學習筆記"
    
    def _generate_simple_note_from_scenes(self, structured_summaries, language, include_japanese):
        """基於場景摘要生成簡單筆記"""
        try:
            note_lines = []
            
            if language.startswith('zh'):
                note_lines.append("# 📚 學習筆記")
                note_lines.append("")
                note_lines.append("## 📋 課程內容摘要")
                note_lines.append("")
            else:
                note_lines.append("# 📚 Study Notes")
                note_lines.append("")
                note_lines.append("## 📋 Course Content Summary")
                note_lines.append("")
            
            for i, group in enumerate(structured_summaries):
                note_lines.append(f"### 場景 {i+1}")
                note_lines.append("")
                
                for scene in group.get('scenes', []):
                    if scene.get('summary'):
                        note_lines.append(f"- {scene['summary']}")
                    if scene.get('ocr_text') and scene['ocr_text'].strip():
                        ocr_preview = scene['ocr_text'][:100].replace('\n', ' ')
                        note_lines.append(f"- OCR內容: {ocr_preview}...")
                
                note_lines.append("")
            
            return '\n'.join(note_lines)
            
        except Exception as e:
            logger.error(f"[NoteGenerator] 生成簡單筆記失敗: {e}")
            return "# 📚 學習筆記\n\n內容生成中遇到問題，請稍後再試。"
    
    def _generate_basic_note_from_scenes(self, structured_summaries, language):
        """生成最基本的筆記"""
        try:
            basic_lines = ["# 📚 學習筆記", ""]
            
            if structured_summaries:
                basic_lines.append("## 📋 處理的場景")
                basic_lines.append("")
                for i, group in enumerate(structured_summaries):
                    basic_lines.append(f"### 場景 {i+1}")
                    for scene in group.get('scenes', []):
                        if scene.get('summary'):
                            basic_lines.append(f"- {scene['summary']}")
                    basic_lines.append("")
            else:
                basic_lines.append("## ⚠️ 無可用內容")
                basic_lines.append("")
                basic_lines.append("請檢查影片檔案或重新處理。")
            
            return '\n'.join(basic_lines)
            
        except Exception as e:
            logger.error(f"[NoteGenerator] 生成基本筆記失敗: {e}")
            return "# 📚 學習筆記\n\n## ⚠️ 生成錯誤\n\n請檢查影片檔案或重新處理。"

    def _get_learning_tips(self, language):
        """已停用：不再生成學習建議模板，改用藍圖格式"""
        return ""
    
    def _generate_fallback_summary(self, scene_summaries, language="zh-TW", include_japanese=False):
        """已停用：不再使用舊模板格式生成，強制藍圖結構化筆記"""
        return "# 請稍後再試\n當前使用藍圖格式架構生成"
    
    async def sync_image_to_frontend(self, src_path, display_filename):
        """同步圖片到前端目錄 - 確保路徑正確"""
        logger.info(f"[NoteGenerator] 同步圖片: {src_path} -> {display_filename}")
        
        try:
            dst_dir_path = FRONTEND_PUBLIC_IMAGES_DIR
            dst_dir = str(dst_dir_path)
            dst_path = os.path.join(dst_dir, display_filename)

            os.makedirs(dst_dir, exist_ok=True)

            if os.path.exists(src_path):
                shutil.copy2(src_path, dst_path)
                logger.info(f"[NoteGenerator] 圖片同步成功: {dst_path}")

                # 驗證複製後的檔案
                if os.path.exists(dst_path):
                    file_size = os.path.getsize(dst_path)
                    logger.info(f"[NoteGenerator] 複製驗證通過，檔案大小: {file_size} bytes")
                else:
                    logger.warning(f"[NoteGenerator] 複製後檔案不存在: {dst_path}")
            else:
                logger.warning(f"[NoteGenerator] 源圖片不存在: {src_path}")
                # 嘗試從其他可能的路徑尋找
                alternative_paths = [
                    os.path.join(OUTPUT_IMAGES_ROOT, display_filename),
                    os.path.join(str(DATA_ROOT / "images"), display_filename),
                    os.path.join(str(DATA_ROOT / "external" / "f" / "講義圖片"), display_filename),
                    os.path.join(str(DATA_ROOT / "external" / "f"), display_filename),
                    os.path.join(str(DATA_ROOT / "external" / "c" / "Users"), display_filename),
                ]

                for alt_path in alternative_paths:
                    if os.path.exists(alt_path):
                        logger.info(f"[NoteGenerator] 找到替代路徑: {alt_path}")
                        shutil.copy2(alt_path, dst_path)
                        break

        except Exception as e:
            logger.error(f"[NoteGenerator] 圖片同步失敗: {e}")
            logger.error(f"[NoteGenerator] 錯誤詳情: {traceback.format_exc()}")

    @staticmethod
    def _has_formula_section(content: str) -> bool:
        if not content:
            return False
        if "```" in content or "$" in content:
            return True
        keywords = ["公式", "方程", "推導", "推导", "解法", "derivation", "equation", "proof", "math", "程式碼", "程式", "code"]
        lower = content.lower()
        return any(keyword in content or keyword in lower for keyword in keywords)

    @staticmethod
    def _has_flow_description(content: str) -> bool:
        if not content:
            return False
        keywords = ["流程", "步驟", "順序", "箭頭", "→", "↦", "流程圖", "flow", "transition", "手順", "狀態轉移"]
        lower = content.lower()
        return any(keyword in content or keyword in lower for keyword in keywords)

    @staticmethod
    def _has_visual_section(content: str) -> bool:
        if not content:
            return False
        keywords = [
            "圖像補充重點",
            "圖像補充",
            "視覺重點",
            "視覺補充",
            "visual highlights",
            "visual focus",
            "画像補足",
        ]
        lower = content.lower()
        return any(keyword in content or keyword in lower for keyword in keywords)

    @staticmethod
    def _get_visual_header(language: str) -> str:
        mapping = {
            "zh-TW": "### 🔎 圖像補充重點",
            "zh-CN": "### 🔎 图像补充要点",
            "ja": "### 🔎 画像補足ポイント",
            "en": "### 🔎 Visual Highlights",
            "ko": "### 🔎 시각 보충 포인트",
            "vi": "### 🔎 Điểm nhấn hình ảnh",
            "my": "### 🔎 ရုပ်ပုံထပ်ဆင့်အချက်များ",
            "mn": "### 🔎 Дүрсний нэмэлт онцлох хэсэг",
        }
        return mapping.get(language, mapping["zh-TW"])

    def _generate_error_note(self, image_filename, error_title, error_message):
        """生成錯誤提示筆記"""
        return f"""# ❌ {error_title}

## 🚨 處理失敗

**圖片:** `{image_filename}`

**錯誤訊息:** {error_message}

---

## 🔍 可能原因

1. **Ollama 服務異常**
   - LLM 模型未載入
   - Ollama 容器未運行
   - 連線超時

2. **圖片處理失敗**
   - 圖片檔案損壞
   - OCR 無法識別文字
   - 格式不支援

3. **系統資源不足**
   - 記憶體不足
   - GPU 資源耗盡
   - 處理佇列過長

---

## 🛠️ 建議操作

1. **檢查 Ollama 狀態:**
   ```bash
   docker ps | grep ollama
   docker exec ollama_local ollama list
   ```

2. **檢查後端日誌:**
   ```bash
   docker logs notegen-backend-enhanced --tail 100
   ```

3. **重新處理:**
   - 等待幾分鐘後重試
   - 確認圖片檔案完整
   - 檢查系統資源使用情況

4. **聯絡管理員:**
   - 如果問題持續,請聯絡系統管理員
   - 提供上述日誌資訊

---
"""

# 工廠函數
def create_note_generator(llm_config):
    """創建筆記生成器實例"""
    return NoteGenerator(llm_config)
