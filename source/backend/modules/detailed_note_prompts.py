"""
Detailed lecture-note prompt helpers derived from the transcript prompt specification
shared in ``BiliNote_prompts.md`` (2025-10-15).

This module centralises the Markdown-focused templates so other components can
assemble consistent prompts for transcript-based teaching notes. The
implementation intentionally avoids depending on any third-party component names.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence


LanguageProfile = Dict[str, str]

_LANGUAGE_PROFILES: Dict[str, LanguageProfile] = {
    "zh-TW": {"mother_tongue": "繁體中文", "glossary_label": "繁體中文"},
    "zh-CN": {"mother_tongue": "簡體中文", "glossary_label": "简体中文"},
    "ja": {"mother_tongue": "日本語", "glossary_label": "日本語"},
    "en": {"mother_tongue": "English", "glossary_label": "English"},
    "ko": {"mother_tongue": "한국어", "glossary_label": "한국어"},
    "vi": {"mother_tongue": "Tiếng Việt", "glossary_label": "Tiếng Việt"},
    "my": {"mother_tongue": "မြန်မာ", "glossary_label": "မြန်မာ"},
    "mn": {"mother_tongue": "Монгол", "glossary_label": "Монгол"},
}


def _resolve_language_profile(language: str) -> LanguageProfile:
    default = {"mother_tongue": "繁體中文", "glossary_label": "繁體中文"}
    return _LANGUAGE_PROFILES.get(language, default)


_BASE_PROMPT = """
你是一個「結構化筆記生成器」。請根據提供的影片轉錄（transcript）段落，產出符合中日雙語教學需求的 Markdown 筆記。筆記必須依照**三層階層結構**建構完整學習動線，並嚴格遵守以下規範：

【語言與內容】
- 全文以{mother_tongue_label}為主敘述，但保留原始日文句子並逐段解釋。
- 禁止臆測或補字；無來源的內容不得創造。
- 去除寒暄、廣告、重複語句，只保留教學相關資訊。

【三層階層結構】**（強制格式）**
必須嚴格遵循以下三層結構,從轉錄內容中提取實際的章節標題:

```markdown
# 第1章 [實際章標題]
## 1.1 [實際節標題]
### 1.1.1 [實際子節標題]
[段落內容: 包含日文原文引用 > 與{mother_tongue_label}解說]

### 1.1.2 [實際子節標題]
[段落內容]

## 1.2 [實際節標題]
### 1.2.1 [實際子節標題]
[段落內容]

# 第2章 [實際章標題]
## 2.1 [實際節標題]
...
```

**層級說明:**
- **一級標題 (`#`)**: 主題章節 (格式: `# 第X章 [章標題]`)
- **二級標題 (`##`)**: 章下的節 (格式: `## X.Y [節標題]`)
- **三級標題 (`###`)**: 節下的子節 (格式: `### X.Y.Z [子節標題]`)
- 標題必須從轉錄內容提取實際的主題名稱,禁止使用通用占位符如「基礎概念」「介紹」
- 章節編號必須連續且正確 (1.1, 1.2, 2.1, 2.2...)

【內容組織】
在每個子節內,依需求組織以下區塊 (沒有材料的區塊省略):
- **要點詳解**: 使用 `-` 條列要點,每列一個概念
- **例子**: 實際範例或程式碼,使用正確 Markdown 語法 (含語言標註)
- **反例**: 常見錯誤或易混淆點
- **公式**: 使用 LaTeX 語法
- **術語**: 重要專有名詞 (在章節末集中為術語表)

【章節末尾區塊】(可選,放在章節最後):
```markdown
## X.Y 術語表
| 日文 | {glossary_label} | 備註 |
|------|------|------|
| ... | ... | ... |

## X.Y 問答/考點
**Q:** [問題]
**A:** [答案]
```

【寫作要求】
- 日文原文以引用（`>`）呈現，{mother_tongue_label}解說另起段落，避免混排。
- 條列要點用 `-` 或編號列表，每列專注一個概念或步驟。
- 程式碼使用三個反引號包裹並標註語言，如 \`\`\`java。
- 程式碼區塊必須保留換行與縮排，且每個 \`\`\` 開頭都要有對應的結尾 \`\`\`（禁止把後續內容吞進代碼框）。
- 術語表以三欄表格呈現：日文｜{glossary_label}｜備註。
- 表格必須是完整且可解析的 Markdown 表格（含表頭分隔線 `|---|`），避免輸出殘缺的 `|---|` 片段；不確定時寧可改成條列。
- 問答區以 **Q:**/**A:** 呈現，聚焦常考或檢核觀念。
- 內容應邏輯連貫、語氣專業，可直接匯出為最終教材或 PDF。
- **禁止輸出舊模板標題**: 如 `# 📚 講義筆記`、`## 🎯 課程主題`、`## 核心日文術語詳解` 等
- 標題必須符合 Markdown：`#`/`##`/`###` 後面一定要有空格，且標題後空一行再開始正文。
- 公式請用 LaTeX（`$...$` / `$$...$$`）表示，**禁止**把公式放進反引號（`...`）或程式碼區塊（```...```）內。
- 忽略 OCR 噪音（頁碼、行號、邊角連號，例如 `274 275 276`），不要輸出這類純數字行。
- MDP/RL 程式碼若需要狀態定義，必須用 `enum` 或 `int`（或等價離散型別），禁止用 `double/float` 表示離散狀態。
- MDP/RL 兩狀態示例優先使用 `enum State {{{{ SOFF, SON }}}}`，且禁止在 ```lang 行尾追加註解文字。
- Java 範例必須包在 ```java 區塊內，禁止以純文字或單行夾帶方式輸出。
- MDP/RL 狀態不可僅用陣列索引表示，必須使用 `enum` 或明確的 `int` 常數。
- 期望報酬（Expected Reward）計算請分步呈現：Step 1: `P * R`，Step 2: `P * (R + gamma * V)`。
- 清理噪音：嚴禁輸出 `((((`、`java // java` 等殘留標籤或符號。

【輸入原始資料】
---
{segment_text}
---

請確保輸出為乾淨、層次分明的 Markdown，嚴格遵循三層階層結構。禁止輸出 JSON、HTML 或任何非 Markdown 格式。
"""

_LINK_SNIPPET = (
    "⏱️ **時間參照建議**：若可辨識時間點，可於相關段落或條列後方補上 `*Content-[mm:ss]`，方便學習者回到影片原段。"
)

_SCREENSHOT_SNIPPET = (
    "🖼️ **截圖提示**：若段落強調視覺示範，可在敘述結尾加入 `*Screenshot-[mm:ss]` 作為圖片占位符。"
)

_AI_SUM_SNIPPET = (
    "🧠 **補充摘要**：若教材需要，在結尾追加 80-150 字的{mother_tongue_label}總結，強調整體學習目標與 2-3 項行動建議。"
)

_STEP_A_PROMPT = """
你是雙語教學助理。輸入為影片轉錄段落（原語為日語）。請針對每個段落輸出三個清晰區塊，格式為 Markdown，並以 `---` 分隔段落輸出。對每個段落請產生：

1) 原文摘錄（日本語）：從段落中選取最能代表核心的 1–3 句原文（保留原句，不要改寫）。
2) 要点（日本語）：用日語以 3–6 條要點列出本段核心概念（每條 1–2 行）。
3) {mother_tongue_label}說明：逐條對「要点」做詳盡的教學性說明，包含必要的範例或程式碼（若有），並保留 LaTeX 公式。

時間標記：在段落標題或開頭加上 `*Content-[mm:ss]`。

輸入段落：
---
{segment_text}
---
"""

_STEP_B_PROMPT = """
你是專業的教學講師。輸入由數個日文要點組成。請為每條要點產出：

1. {mother_tongue_label}詳解：針對原要點進行深入說明，適當舉例。
2. 技術補充：列出必要的延伸資訊、程式碼或注意事項。
3. 延伸練習：提供 1–2 組實作或思考題，格式使用有序列表。

輸入要點：
---
{key_points}
---
"""

_SINGLE_PASS_PROMPT = """
你是雙語教學助理。輸入為影片轉錄段落（原語為日語）。請針對每個段落輸出三個清晰區塊，格式為 Markdown，並以 `---` 分隔段落輸出。對每個段落請產生：

1) 原文摘錄（日本語）：從段落中選取最能代表核心的 1–3 句原文（保留原句，不要改寫）。
2) 要点（日本語）：用日語以 3–6 條要點列出本段核心概念（每條 1–2 行）。
3) {mother_tongue_label}說明：逐條對「要点」做詳盡的教學性說明，包含必要的範例或程式碼（若有），並在需要保留 LaTeX 公式時以原始 LaTeX 顯示。

時間標記：在段落標題或開頭加上 `*Content-[mm:ss]`。

輸入段落：
---
{segment_text}
---
"""


def _normalise_tags(tags: Optional[Sequence[str]]) -> Optional[str]:
    if not tags:
        return None
    if isinstance(tags, str):
        raw_iterable = [part.strip() for part in tags.split(',')]
    else:
        raw_iterable = tags
    cleaned = [tag.strip() for tag in raw_iterable if tag and tag.strip()]
    return ", ".join(cleaned) if cleaned else None


def build_detailed_prompt(
    segment_text: str,
    *,
    target_language: str = "zh-TW",
    video_title: Optional[str] = None,
    tags: Optional[Sequence[str]] = None,
    include_link: bool = True,
    include_screenshot: bool = False,
    include_ai_summary: bool = True,
) -> str:
    """Assemble the detailed teaching-note prompt."""

    profile = _resolve_language_profile(target_language)

    lines: List[str] = []
    if video_title:
        lines.append(f"影片標題：{video_title.strip()}")
    tag_line = _normalise_tags(tags)
    if tag_line:
        lines.append(f"主題標籤：{tag_line}")

    inserted = _BASE_PROMPT.format(
        segment_text=segment_text.strip(),
        mother_tongue_label=profile["mother_tongue"],
        glossary_label=profile["glossary_label"],
    )
    lines.append(inserted.strip())

    extras: List[str] = []
    if include_link:
        extras.append(_LINK_SNIPPET)
    if include_screenshot:
        extras.append(_SCREENSHOT_SNIPPET)
    if include_ai_summary:
        extras.append(_AI_SUM_SNIPPET.format(mother_tongue_label=profile["mother_tongue"]))

    if extras:
        lines.append("\n\n".join(extras))

    return "\n\n".join(lines).strip()


def build_step_a_prompt(segment_text: str, *, target_language: str = "zh-TW") -> str:
    """Return the Step A (extract) prompt for the two-step pipeline."""

    profile = _resolve_language_profile(target_language)
    return _STEP_A_PROMPT.format(
        segment_text=segment_text.strip(),
        mother_tongue_label=profile["mother_tongue"],
    )


def build_step_b_prompt(key_points: str, *, target_language: str = "zh-TW") -> str:
    """Return the Step B (explain) prompt for the two-step pipeline."""

    profile = _resolve_language_profile(target_language)
    return _STEP_B_PROMPT.format(
        key_points=key_points.strip(),
        mother_tongue_label=profile["mother_tongue"],
    )


def build_single_pass_prompt(segment_text: str, *, target_language: str = "zh-TW") -> str:
    """Return the single-pass prompt variant."""

    profile = _resolve_language_profile(target_language)
    return _SINGLE_PASS_PROMPT.format(
        segment_text=segment_text.strip(),
        mother_tongue_label=profile["mother_tongue"],
    )


def build_detailed_messages(
    segment_text: str,
    *,
    target_language: str = "zh-TW",
    system_prompt: Optional[str] = None,
    video_title: Optional[str] = None,
    tags: Optional[Sequence[str]] = None,
    include_link: bool = True,
    include_screenshot: bool = False,
    include_ai_summary: bool = True,
) -> List[dict]:
    """Return OpenAI-style messages for the detailed prompt."""

    user_prompt = build_detailed_prompt(
        segment_text,
        target_language=target_language,
        video_title=video_title,
        tags=tags,
        include_link=include_link,
        include_screenshot=include_screenshot,
        include_ai_summary=include_ai_summary,
    )

    messages: List[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt.strip()})
    messages.append({"role": "user", "content": user_prompt})
    return messages


__all__ = [
    "build_detailed_prompt",
    "build_detailed_messages",
    "build_single_pass_prompt",
    "build_step_a_prompt",
    "build_step_b_prompt",
]
