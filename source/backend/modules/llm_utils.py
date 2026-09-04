import logging
import json
import threading
import copy
from typing import Any, Dict, Optional, Tuple

from modules.services.config_manager import load_config
from modules.services.llm_provider import LLMProvider, LLMResponse, create_provider

logger = logging.getLogger(__name__)

_PROVIDER_CACHE: Dict[str, Tuple[LLMProvider, str]] = {}
_PROVIDER_LOCK = threading.RLock()

def get_language_system_prompt(
    language_code: str = "zh-TW",
    content_type: str = "bilingual",
    include_japanese: bool = True,
) -> str:
    """Return a concise system prompt for language policy."""
    lang = (language_code or "").lower()
    language_names = {
        "zh-tw": "繁體中文",
        "zh-cn": "簡體中文",
        "en": "English",
        "ja": "日本語",
        "ko": "한국어",
        "vi": "Tiếng Việt",
        "my": "မြန်မာ",
        "mn": "Монгол",
    }
    target_label = language_names.get(lang, language_code or "target language")
    if lang.startswith("ja") and not include_japanese:
        return "Output must be Japanese only. Do not include translations or bilingual separators."
    if content_type == "bilingual" or include_japanese:
        return (
            "Output must be bilingual with Japanese and the target language on each line. "
            f"Target language: {target_label}. Use the format 'Japanese｜{target_label}'."
        )
    return f"Output must be in {target_label} only. Do not include Japanese translations."


def get_grounded_analysis_prompt(language_code="zh-TW"):

    """
    返回強制引用 OCR 的分析提示詞，防止幻覺生成
    """
    return """你是一位專業的程式設計教育專家。你只能根據提供的 OCR 內容產生筆記，嚴禁添加 OCR 以外的內容。

規則：
1. 每條筆記必須包含：JP 原句(來自 OCR) → 中文解釋 → 技術補充
2. 嚴禁添加 OCR 中沒有的句子、例句或程式碼
3. 若 OCR 內容不足，回傳 "資料不足，請上傳清晰講義"
4. 對程式碼：只允許出現 OCR 中出現的符號/方法名
5. 關鍵詞白名單：String, StringBuilder, equals, ==, System.out.print, 記憶體, 參照, 內容

🚨 極其重要：你必須且只能輸出有效的 JSON 格式，絕對不能包含任何其他文字、說明、Markdown 格式、標題或任何非 JSON 內容。

輸出格式（嚴格 JSON，必須完全遵循）：
{
  "notes": [
    {
      "original": "OCR 中的日文原句",
      "explanation": "中文解釋",
      "supplements": ["技術補充1", "技術補充2"],
      "groundingValid": true
    }
  ],
  "terms": [
    {"jp": "日文術語", "zh": "中文解釋", "note": "備註"}
  ],
  "code": {
    "lang": "java",
    "code": "只允許 OCR 出現過的程式碼",
    "expected": ["預期輸出1", "預期輸出2"]
  },
  "qa": [
    {
      "q": "問題",
      "options": ["選項1", "選項2", "選項3", "選項4"],
      "answer": 0,
      "grounding": ["OCR 子字串1", "OCR 子字串2"]
    }
  ],
  "summary": ["重點1", "重點2", "重點3"]
}

⚠️ 最後提醒：你的回應必須是純 JSON 格式，不能有任何前綴、後綴、說明文字或 Markdown 格式。如果違反此要求，系統將無法解析你的回應。"""

def get_image_note_prompt(ocr_text, language_code="zh-TW", include_japanese=True):
    """
    DEPRECATED: 此函數已廢棄，請使用 llm_prompts_optimized.get_optimized_image_note_prompt
    
    此函數僅作為回退選項保留，不建議在新代碼中使用。
    
    原始功能：生成高品質圖片筆記提示詞 - 參考 ChatGPT-5 範例品質
    """
    
    language_names = {
        "zh-TW": "繁體中文",
        "zh-CN": "簡體中文", 
        "ko": "한국어",
        "en": "English",
        "ja": "日本語"
    }
    
    target_lang = language_names.get(language_code, "繁體中文")
    
    if include_japanese:
        prompt = f"""你是一位資深的日文程式設計教育專家。請根據以下OCR識別的講義內容,生成一份高品質、結構化的學習筆記。

【OCR識別內容】
{ocr_text}

【輸出要求】

請參考以下格式生成筆記(使用{target_lang}):

## 📌 日文重點摘錄

請列出講義中的核心日文內容(保持原文,每行一個要點):
• [日文原文句子1]
• [日文原文句子2]
• [日文原文句子3]
• [日文原文句子4]

---

## � {target_lang}詳解與補充

### 1. [主要概念標題]

• [概念說明1]
• [概念說明2]

**例如:**
- [具體例子1]
- [具體例子2]

### 2. [次要概念標題]

• [詳細說明]
• [補充資訊]

### 3. [重要操作/方法]

使用方式:

```javascript
// 實際的程式碼範例
[完整可執行的程式碼]
```

**注意:** [重要提醒]

### 4. 常見錯誤點

**[錯誤情況1]:**

```javascript
[示範錯誤的程式碼]
```

---

## 💻 範例程式碼

```javascript
// [範例標題]
[完整的程式碼範例,包含註解]

// [另一個範例]
[更多程式碼]
```

**執行結果:**
```
[預期輸出]
```

---

## � 更好的補充內容 (進一步建議)

### 1. [實用建議1]

• [具體建議內容]
• [原因說明]

### 2. [常用屬性與方法]

• `[方法名]`: [功能說明]
• `[屬性名]`: [用途說明]

**範例:**

```javascript
[實際使用範例]
```

### 3. 考試/面試常考區分

• [考點1]: [說明]
• [考點2]: [說明]

【重要原則】:
1. 所有內容必須基於OCR識別的實際內容
2. 日文原文必須完整保留且準確
3. 程式碼必須是實際可執行的JavaScript/Java程式碼,不是日文文字
4. 每個概念都要有清楚的說明和實際範例
5. 補充內容要實用且有學習價值
6. 使用項目符號(•)和編號讓結構清晰
7. 程式碼區塊只放程式碼,不放日文目錄或說明文字
"""
    else:
        prompt = f"""你是一位專業的程式設計教育專家。請根據以下講義內容生成高品質學習筆記。

【講義內容】
{ocr_text}

請生成結構化的學習筆記(使用{target_lang}),包含:

## 📖 核心概念

[清晰的概念說明]

## 🔍 重點分析

1. **[要點1]**: [詳細解釋]
2. **[要點2]**: [詳細解釋]

## 💻 程式碼範例

```
[完整程式碼]
```

**說明**: [程式碼解釋]

## 🎯 學習建議

[實用的學習建議]
"""
    
        return prompt


def _provider_signature(config: Dict[str, Any], provider_name: str) -> str:
    llm_cfg = config.get("llm", {})
    provider_cfg = llm_cfg.get(provider_name, {})
    return json.dumps({"name": provider_name, "cfg": provider_cfg}, sort_keys=True)


def _resolve_provider_name(config: Dict[str, Any], override: Optional[str] = None) -> str:
    if override:
        return override.lower()
    return (config.get("llm", {}).get("provider") or "ollama").lower()


def _ensure_provider(
    provider_override: Optional[str] = None, force_reload: bool = False, config: Optional[Dict[str, Any]] = None
) -> LLMProvider:
    config = config or load_config(force_reload=force_reload)
    provider_name = _resolve_provider_name(config, provider_override)
    signature = _provider_signature(config, provider_name)

    with _PROVIDER_LOCK:
        cached = _PROVIDER_CACHE.get(provider_name)
        if force_reload or not cached or cached[1] != signature:
            cfg_copy = copy.deepcopy(config)
            cfg_copy.setdefault("llm", {})["provider"] = provider_name
            provider = create_provider(cfg_copy)
            _PROVIDER_CACHE[provider_name] = (provider, signature)
        return _PROVIDER_CACHE[provider_name][0]


def reload_llm_providers() -> None:
    with _PROVIDER_LOCK:
        _PROVIDER_CACHE.clear()


def active_provider_name() -> str:
    config = load_config()
    return _resolve_provider_name(config)


def list_provider_metadata() -> Dict[str, Any]:
    config = load_config()
    llm_cfg = config.get("llm", {})
    active = _resolve_provider_name(config)
    providers = []
    for name, data in llm_cfg.items():
        if not isinstance(data, dict):
            continue
        if name != "ollama" and "base_url" not in data and "models" not in data and "model" not in data:
            continue
        entry = {
            "name": name,
            "title": data.get("title") or name.upper(),
            "base_url": data.get("base_url"),
            "model": data.get("model") or data.get("default_model"),
            "models": data.get("models") or [],
            "supports_images": data.get("supports_images", True),
        }
        providers.append(entry)
    return {"active": active, "providers": providers}

def get_language_system_prompt(language_code, content_type="general", include_japanese=False):
    """
    根據語言代碼和內容類型返回對應的系統提示詞
    
    Args:
        language_code: 目標語言代碼
        content_type: 內容類型 ("general", "technical", "educational", "bilingual")
        include_japanese: 是否包含日文學習內容
    """
    
    # 基礎語言提示詞
    base_prompts = {
        "zh-TW": "請使用繁體中文(台灣)回答。使用台灣慣用的技術術語。",
        "zh-CN": "请使用简体中文回答。使用中国大陆常用的技术术语。",
        "ko": "한국어로 답변해 주세요. 한국에서 일반적으로 사용하는 기술 용어와 표현을 사용해 주세요.",
        "en": "Please respond in English using standard technical terminology.",
        "ja": "日本語で回答してください。技術用語は適切な日本語表現を使用してください。",
        "vi": "Vui lòng trả lời bằng tiếng Việt, sử dụng thuật ngữ kỹ thuật phổ biến tại Việt Nam.",
        "my": "ကျေးဇူးပြု၍ မြန်မာဘာသာဖြင့် ဖြေကြားပါ။ နည်းပညာဆိုင်ရာ အသုံးအနှုန်းများကို အသုံးပြုပါ။"
    }
    
    # 教育內容特殊提示詞
    educational_prompts = {
        "zh-TW": """
你是一位專業的日文程式設計教育專家。請創建詳細的學習筆記，包含：
1. 清晰的概念解釋
2. 實用的程式碼範例
3. 重點詞彙標註
4. 學習建議和練習方法
使用繁體中文(台灣)，並適當保留重要的日文技術術語。
        """,
        "zh-CN": """
你是一位专业的日文程序设计教育专家。请创建详细的学习笔记，包含：
1. 清晰的概念解释
2. 实用的代码示例
3. 重点词汇标注
4. 学习建议和练习方法
使用简体中文，并适当保留重要的日文技术术语。
        """,
        "ko": """
당신은 전문적인 일본어 프로그래밍 교육 전문가입니다. 다음을 포함한 상세한 학습 노트를 작성해 주세요:
1. 명확한 개념 설명
2. 실용적인 코드 예제
3. 핵심 어휘 표시
4. 학습 제안 및 연습 방법
한국어를 사용하되, 중요한 일본어 기술 용어는 적절히 보존해 주세요.
        """,
        "en": """
You are a professional Japanese programming education expert. Please create detailed study notes including:
1. Clear concept explanations
2. Practical code examples
3. Key vocabulary annotations
4. Learning suggestions and practice methods
Use English while appropriately preserving important Japanese technical terms.
        """,
        "ja": """
あなたは専門的なプログラミング教育の専門家です。以下を含む詳細な学習ノートを作成してください：
1. 明確な概念説明
2. 実用的なコード例
3. 重要語彙の注釈
4. 学習提案と練習方法
日本語を使用し、技術用語は適切な表現を使ってください。
        """
    }
    
    # 雙語內容提示詞
    bilingual_prompts = {
        "zh-TW": """
請創建雙語學習筆記（日文+繁體中文），包含：
1. 🇯🇵 **日文原文內容**：保持原始日文表達
2. 🇹🇼 **繁體中文解釋**：詳細的中文說明
3. 📚 **詞彙對照表**：重要術語的日中對照
4. 💡 **學習重點**：標註學習要點和注意事項
5. 🔧 **實踐應用**：提供實際應用建議

格式要求：
- 使用清晰的標題結構
- 重要詞彙用 **粗體** 標示
- 日文內容用 `代碼格式` 標示
- 提供發音提示（平假名/片假名）
        """,
        "ko": """
일본어+한국어 이중 언어 학습 노트를 작성해 주세요:
1. 🇯🇵 **일본어 원문 내용**: 원래 일본어 표현 유지
2. 🇰🇷 **한국어 설명**: 상세한 한국어 설명
3. 📚 **어휘 대조표**: 중요 용어의 일한 대조
4. 💡 **학습 포인트**: 학습 요점과 주의사항 표시
5. 🔧 **실제 응용**: 실제 응용 제안 제공

형식 요구사항:
- 명확한 제목 구조 사용
- 중요 어휘는 **굵은 글씨**로 표시
- 일본어 내용은 `코드 형식`으로 표시
- 발음 힌트 제공 (히라가나/가타카나)
        """,
        "en": """
Please create bilingual study notes (Japanese + English) including:
1. 🇯🇵 **Japanese Original Content**: Maintain original Japanese expressions
2. 🇺🇸 **English Explanations**: Detailed English explanations
3. 📚 **Vocabulary Comparison**: Japanese-English comparison of key terms
4. 💡 **Learning Points**: Highlight key learning points and notes
5. 🔧 **Practical Applications**: Provide practical application suggestions

Format requirements:
- Use clear heading structure
- Mark important vocabulary with **bold**
- Mark Japanese content with `code format`
- Provide pronunciation hints (hiragana/katakana)
        """
    }
    
    # 根據內容類型選擇提示詞
    if content_type == "bilingual" or include_japanese:
        prompt = bilingual_prompts.get(language_code, bilingual_prompts.get("zh-TW", ""))
    elif content_type == "educational":
        prompt = educational_prompts.get(language_code, educational_prompts.get("zh-TW", ""))
    else:
        prompt = base_prompts.get(language_code, base_prompts["zh-TW"])
    
    return prompt.strip()

def _build_extra_params(config: Dict[str, Any], extra: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    llm_cfg = config.get("llm", {})
    defaults: Dict[str, Any] = {}
    for key in ("temperature", "top_p", "top_k", "max_tokens"):
        value = llm_cfg.get(key)
        if value is not None:
            defaults[key] = value
    if extra:
        defaults.update({k: v for k, v in extra.items() if v is not None})
    return defaults


async def call_llm(
    prompt: str,
    model: Optional[str] = None,
    *,
    image: Optional[str] = None,
    use_cache: bool = True,
    language: str = "zh-TW",
    provider: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
    force_reload_provider: bool = False,
) -> str:
    """Entry point for all LLM calls across providers."""
    logger = logging.getLogger(__name__)
    config = load_config()
    provider_instance = _ensure_provider(provider_override=provider, force_reload=force_reload_provider, config=config)
    extras = _build_extra_params(config, extra)

    logger.info(
        "[call_llm] provider=%s model=%s language=%s image=%s",
        provider_instance.name,
        model or provider_instance.default_model,
        language,
        bool(image),
    )
    response = await provider_instance.generate(
        prompt,
        model=model,
        image=image,
        language=language,
        use_cache=use_cache,
        extra=extras,
    )
    logger.debug("[call_llm] response length=%s cache_hit=%s", len(response.content), response.cache_hit)
    return response.content


async def call_ollama_llm(
    prompt,
    model="qwen3-vl:4b",
    image=None,
    use_cache=True,
    language="zh-TW",
    extra: Optional[Dict[str, Any]] = None,
):
    """Backward-compatible wrapper forcing Ollama provider."""
    return await call_llm(
        prompt,
        model=model,
        image=image,
        use_cache=use_cache,
        language=language,
        provider="ollama",
        extra=extra,
    )

