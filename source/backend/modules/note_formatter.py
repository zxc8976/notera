"""
筆記格式化模組 - 強制轉換VLM輸出為正確格式
"""
import re
import json
import logging
from typing import Dict, Tuple, List, Set, Any

# 🎯 導入日文假名轉換工具
try:
    import pykakasi
    PYKAKASI_AVAILABLE = True
    kks = pykakasi.kakasi()
    logger = logging.getLogger(__name__)
    logger.info("[NoteFormatter] pykakasi 假名轉換工具已載入")
except ImportError:
    PYKAKASI_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("[NoteFormatter] pykakasi 未安裝,假名轉換功能將被停用")

logger = logging.getLogger(__name__)

try:
    from modules.llm_utils import call_llm
except ModuleNotFoundError:  # pragma: no cover - fallback for tests
    from source.backend.modules.llm_utils import call_llm  # type: ignore

LEGACY_SECTION_TITLES = {
    "topic": ["🎯 課程主題"],
    "legacy_highlights": ["🔥 重點內容（紅色標記）", "🔥 重點內容"],
    "summary_highlights": ["💡 學習重點總結", "學習重點總結"],
    "example": ["🔍 核心概念深度解析", "🔍 核心概念解析"],
    "counter": ["⚠️ 常見錯誤與注意事項", "⚠️ 常見錯誤"],
    "practice": ["🎓 延伸學習建議", "延伸學習建議"],
    "terms": ["核心日文術語詳解", "核心日文術語深度學習", "重要詞彙表"],
}


def _split_sections_by_heading(text: str) -> Dict[str, str]:
    sections = {}
    pattern = re.compile(r'^##\s+([^\n]+)\n', re.MULTILINE)
    matches = list(pattern.finditer(text))
    for idx, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        sections[title] = text[start:end].strip()
    return sections


def _extract_bullets(text: str) -> List[str]:
    bullets = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r'^[-*•●▪︎▶︎▹➤\d]', stripped):
            cleaned = re.sub(r'^[-*•●▪︎▶︎▹➤\d\.)]+\s*', '', stripped)
            cleaned = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned)
            cleaned = cleaned.strip()
            if cleaned and cleaned not in bullets:
                bullets.append(cleaned)
    return bullets


def _split_dual_line(text: str) -> Tuple[str, str]:
    text = text.strip()
    separators = ['｜', '|', '：', ':', ' - ', ' — ', ' -> ', '→']
    for sep in separators:
        if sep in text:
            parts = [p.strip() for p in text.split(sep) if p.strip()]
            if len(parts) >= 2:
                left = parts[0]
                right = ' ｜ '.join(parts[1:]).strip()
                return left, right
    # 嘗試括號
    match = re.match(r'^(.+?)\s*[\(（]\s*(.+?)\s*[\)）]$', text)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return text, text


def _format_dual_bullets(items: List[Tuple[str, str]]) -> str:
    lines = []
    seen = set()
    for left, right in items:
        left = left or "□"
        right = right or left
        key = (left, right)
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"- 🔹 {left}｜{right}")
    return '\n'.join(lines)


def _dedupe_section_lines(section_text: str) -> str:
    """Remove duplicate bullet lines within a section while keeping order."""
    if not section_text:
        return ""
    lines = section_text.splitlines()
    deduped: List[str] = []
    seen_bullets: Set[str] = set()
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if deduped and deduped[-1] == "":
                continue
            deduped.append("")
            continue
        bullet_match = re.match(r'^[-*•●▪︎▶︎▹➤]\s*(.*)', stripped)
        if bullet_match:
            bullet_body = bullet_match.group(1) or ""
            bullet_key = re.sub(r'\s+', ' ', bullet_body).strip()
            if bullet_key and bullet_key in seen_bullets:
                continue
            if bullet_key:
                seen_bullets.add(bullet_key)
            deduped.append(line)
        else:
            deduped.append(line)
    while deduped and deduped[-1] == "":
        deduped.pop()
    return '\n'.join(deduped)


def _remove_repeated_sections(note_text: str) -> str:
    """Deduplicate sections with identical content."""
    try:
        pattern = re.compile(r'^##\s+[^\n]+', re.MULTILINE)
        matches = list(pattern.finditer(note_text))
        if not matches:
            return note_text
        output: List[str] = []
        cursor = 0
        seen_sections: Set[Tuple[str, str]] = set()
        for idx, match in enumerate(matches):
            start = match.start()
            if start > cursor:
                output.append(note_text[cursor:start])
            heading = match.group(0)
            content_start = match.end()
            content_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(note_text)
            raw_section = note_text[content_start:content_end]
            deduped_section = _dedupe_section_lines(raw_section)
            normalized_key = re.sub(r'\s+', ' ', deduped_section.strip())
            section_key = (heading.strip(), normalized_key)
            if normalized_key and section_key in seen_sections:
                cursor = content_end
                continue
            if normalized_key:
                seen_sections.add(section_key)
                output.append(heading)
                output.append('\n' + deduped_section.strip('\n') + '\n')
            else:
                simple_key = (heading.strip(), "")
                if simple_key in seen_sections:
                    cursor = content_end
                    continue
                seen_sections.add(simple_key)
                output.append(heading)
                output.append('\n')
            cursor = content_end
        if cursor < len(note_text):
            output.append(note_text[cursor:])
        return ''.join(output)
    except Exception:
        return note_text


def _clean_duplicate_content(text: str) -> str:
    """Remove duplicated '日文原文' / '繁中解釋' blocks and repeated headings."""
    try:
        # 首先移除大量重複的反例
        text = re.sub(r'(## ⚠️ 反例.*?)(\n## ⚠️ 反例.*?){3,}', r'\1', text, flags=re.DOTALL)
        
        # 移除重複的個人資訊
        text = re.sub(r'24ca0244林家誠', '[個人資訊]', text)
        text = re.sub(r'宇山亮\(画面を共有し[^)]*\)', '[老師畫面分享]', text)
        
        lines = text.splitlines()
        cleaned: List[str] = []
        seen_sections: Set[Tuple[str, str]] = set()
        i = 0
        while i < len(lines):
            line = lines[i]
            heading_match = re.match(r'^(##\s+[^\n]+)', line.strip())
            if heading_match:
                heading = heading_match.group(1).strip()
                block_lines: List[str] = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("## "):
                    block_lines.append(lines[i])
                    i += 1
                normalized_block = re.sub(r'\s+', ' ', '\n'.join(block_lines).strip())
                key = (heading, normalized_block)
                if normalized_block and key in seen_sections:
                    continue
                seen_sections.add(key)
                cleaned.append(line)
                cleaned.extend(block_lines)
                continue
            cleaned.append(line)
            i += 1
        return '\n'.join(cleaned)
    except Exception:
        return text


def _normalize_section_headings(text: str) -> str:
    """Remove legacy headings; keep only canonical ②-⑥ sections."""
    if not text:
        return text

    legacy_patterns = [
        r"^##?\s*📝\s*本章重點.*$",
        r"^##?\s*日文原文內容.*$",
        r"^##?\s*繁體中文解釋.*$",
        r"^##?\s*📖\s*重點說明.*$",
        r"^##?\s*💡\s*補充知識.*$",
        r"^##?\s*📚\s*(重要術語對照|術語對照).*$",
        r"^###\s*💻\s*程式碼分析.*$",
    ]

    lines = []
    for ln in text.splitlines():
        stripped = ln.strip()
        if any(re.match(pat, stripped) for pat in legacy_patterns):
            continue
        lines.append(ln)
    return "\n".join(lines)


def _strip_empty_code_sections(text: str) -> str:
    """Drop '程式碼/數學公式' sections that explicitly contain no code."""
    if not text:
        return text

    def _should_drop(section: str) -> bool:
        no_code_markers = [
            "無程式碼",
            "未包含程式碼",
            "僅包含理論",
            "僅為概念",
            "本圖未包含程式碼",
            "非程式碼",
        ]
        if any(marker in section for marker in no_code_markers):
            return "```" not in section and "$$" not in section
        return False

    pattern = re.compile(r"(^##\s+⑤\s*程式碼\s*/\s*數學公式（若有）[\s\S]*?)(?=\n##\s+|\n#\s+|\Z)", re.MULTILINE)

    def _replace(match: re.Match) -> str:
        section = match.group(1)
        return "" if _should_drop(section) else section

    cleaned = pattern.sub(_replace, text)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def _strip_broken_glossary_sections(text: str) -> str:
    """Remove glossary blocks with malformed tables."""
    if not text:
        return text
    lines = text.splitlines()
    output = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.match(r"^\s*(?:#+\s*)?📚\s*重要術語對照", line):
            block = [line]
            i += 1
            while i < len(lines) and not re.match(r"^\s*#", lines[i]):
                block.append(lines[i])
                i += 1
            table_lines = [l for l in block if "|" in l]
            has_separator = any(re.search(r"\|\s*-+\s*\|", l) for l in table_lines)
            valid_rows = True
            for l in table_lines:
                cells = [c for c in l.strip().split("|") if c.strip()]
                if len(cells) < 3:
                    valid_rows = False
                    break
            if has_separator and valid_rows:
                output.extend(block)
            continue
        output.append(line)
        i += 1
    return "\n".join(output)


def _strip_broken_math_lines(text: str) -> str:
    """Remove lines with obvious broken LaTeX or repeated tokens."""
    if not text:
        return text
    cleaned = []
    for line in text.splitlines():
        if re.search(r"(Math){3,}", line):
            continue
        if re.search(r"パララ{3,}", line):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _normalize_headings(text: str) -> str:
    """Fix malformed headings and inline code-fence leaks."""
    if not text:
        return text
    lines = []
    for line in text.splitlines():
        # Fix headings that accidentally include code fences
        line = re.sub(r"^(#+\s+[^\n]*?)```\w+\s*$", r"\1", line)
        # Normalize inline heading markers like '# #' or '## ##'
        line = re.sub(r"^(#+)\s+#\s+", r"\1 ", line)
        lines.append(line)
    return "\n".join(lines)


def _split_inline_code_headings(text: str) -> str:
    """Split headings that were merged into a previous line."""
    if not text:
        return text
    lines = []
    in_code = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            lines.append(line)
            continue
        if in_code:
            lines.append(line)
            continue
        marker = "### 💻 程式碼分析"
        if marker in line and not stripped.startswith(marker):
            prefix, _, suffix = line.partition(marker)
            if prefix.strip():
                lines.append(prefix.rstrip())
            lines.append(marker + suffix)
            continue
        lines.append(line)
    return "\n".join(lines)


def _force_section_headings(text: str) -> str:
    """Ensure key section labels are proper headings."""
    if not text:
        return text
    heading_map = {
        "② 日文重點大綱（原講義語言）": "##",
        "③ 母語解析（中文）": "##",
        "④ 關鍵術語 / 名詞對照": "##",
        "⑤ 程式碼 / 數學公式（若有）": "##",
        "⑥ 補充說明 / 延伸理解": "##",
    }
    lines = []
    in_code = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            lines.append(line)
            continue
        if in_code:
            lines.append(line)
            continue
        normalized = stripped.lstrip("#").strip()
        matched = None
        for label, prefix in heading_map.items():
            if normalized == label:
                matched = f"{prefix} {label.lstrip('#').strip()}"
                break
        if matched:
            lines.append(matched)
            continue
        lines.append(line)
    return "\n".join(lines)


def _strip_malformed_tables(text: str) -> str:
    """Remove malformed markdown table blocks outside code fences."""
    if not text:
        return text

    def is_table_line(line: str) -> bool:
        return line.count("|") >= 2

    def is_separator(line: str) -> bool:
        return bool(re.match(r"^\s*\|(?:\s*:?-+:?\s*\|)+\s*$", line))

    def column_count(line: str) -> int:
        cells = [c for c in line.strip().strip("|").split("|") if c.strip()]
        return len(cells)

    lines = text.splitlines()
    output = []
    in_code = False
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            output.append(line)
            i += 1
            continue
        if in_code:
            output.append(line)
            i += 1
            continue
        if is_table_line(line):
            block = [line]
            i += 1
            while i < len(lines) and is_table_line(lines[i]):
                block.append(lines[i])
                i += 1
            has_separator = any(is_separator(l) for l in block)
            if not has_separator:
                continue
            data_lines = [l for l in block if not is_separator(l)]
            if not data_lines:
                continue
            expected = column_count(data_lines[0])
            if expected < 2:
                continue
            valid = all(column_count(l) == expected for l in data_lines[1:])
            if valid:
                output.extend(block)
            continue
        output.append(line)
        i += 1
    return "\n".join(output)



def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        stripped = stripped[3:-3]
    return stripped.strip()


def _standardize_blueprint(note_text: str) -> str:
    sections = _split_sections_by_heading(note_text)
    if not sections:
        return note_text

    ordered_titles = [
        "## 🟢 重點",
        "## 🔍 例子",
        "## ⚠️ 反例",
        "## 📚 筆記",
        "## 💻 程式碼詳解",
        "## 🔖 學習重點總結",
        "## 📓 延伸學習建議",
        "## 🔹 术语表",
        "## 🔹 術語表",
        "## 🔹 延伸练习",
        "## 🔹 延伸練習",
    ]

    seen_blocks: Set[str] = set()
    output_parts: List[str] = []

    for title in ordered_titles:
        body = sections.get(title)
        if not body:
            continue
        normalized = _dedupe_section_lines(_strip_code_fences(body))
        normalized = _remove_placeholder_lines(normalized)
        normalized = re.sub(r'\n{3,}', '\n\n', normalized).strip()
        block_key = f"{title}\n{normalized}"
        if not normalized or block_key in seen_blocks:
            continue
        if normalized in seen_blocks:
            continue
        seen_blocks.add(block_key)
        seen_blocks.add(normalized)
        normalized = normalized.replace("```markdown", "").replace("```", "").strip()
        output_parts.append(f"{title}\n{normalized}\n")

    remaining_parts: List[str] = []
    for title, body in sections.items():
        if title in ordered_titles:
            continue
        cleaned_body = re.sub(r'\n{3,}', '\n\n', body.strip())
        if cleaned_body:
            remaining_parts.append(f"{title}\n{cleaned_body}\n")

    if not output_parts and not remaining_parts:
        return note_text

    return "\n".join(output_parts + remaining_parts).strip()


def _parse_term_table(section_text: str) -> List[Tuple[str, str]]:
    rows = []
    table_lines = [line for line in section_text.splitlines() if '|' in line]
    if len(table_lines) < 3:
        return rows
    # 假設第一行是表頭，第二行為分隔
    data_lines = [line for line in table_lines if re.match(r'^\|', line)]
    if len(data_lines) < 3:
        return rows
    data_rows = data_lines[2:]
    for row in data_rows:
        cells = [cell.strip() for cell in row.strip().split('|')]
        if len(cells) < 5:
            continue
        jp = cells[1]
        zh = cells[3]
        if jp and zh:
            rows.append((jp, zh))
    return rows


def _pick_first_nonempty(sections: Dict[str, str], titles: List[str]) -> str:
    for title in titles:
        if title in sections and sections[title].strip():
            return sections[title].strip()
    return ""


def _convert_legacy_to_blueprint(note_text: str) -> str:
    if "## 🟢 重點" in note_text:
        return note_text
    if "## 🎯 課程主題" not in note_text:
        return note_text

    sections = _split_sections_by_heading(note_text)

    topic_section = _pick_first_nonempty(sections, LEGACY_SECTION_TITLES["topic"])
    summary_section = _pick_first_nonempty(sections, LEGACY_SECTION_TITLES["summary_highlights"])
    legacy_highlights = _pick_first_nonempty(sections, LEGACY_SECTION_TITLES["legacy_highlights"])
    example_section = _pick_first_nonempty(sections, LEGACY_SECTION_TITLES["example"])
    counter_section = _pick_first_nonempty(sections, LEGACY_SECTION_TITLES["counter"])
    practice_section = _pick_first_nonempty(sections, LEGACY_SECTION_TITLES["practice"])
    terms_section = _pick_first_nonempty(sections, LEGACY_SECTION_TITLES["terms"])

    keypoint_candidates = _extract_bullets(summary_section) or _extract_bullets(legacy_highlights)
    if not keypoint_candidates and topic_section:
        keypoint_candidates = [topic_section.replace("\n", " ")]
    keypoint_pairs = []
    seen_keypoints = set()
    for line in keypoint_candidates:
        left, right = _split_dual_line(line)
        right = right if right and right != left else "（資訊不足）"
        key = (left, right)
        if left and key not in seen_keypoints:
            seen_keypoints.add(key)
            keypoint_pairs.append(key)
        if len(keypoint_pairs) >= 5:
            break
    if not keypoint_pairs:
        keypoint_pairs = [("（資訊不足）", "請重新檢查原始講義內容")]

    example_bullets = _extract_bullets(example_section)
    example_pair = None
    for line in example_bullets:
        left, right = _split_dual_line(line)
        if left and (left, right) not in seen_keypoints:
            example_pair = (left, right if right and right != left else "（資訊不足）")
            break

    counter_bullets = _extract_bullets(counter_section)
    counter_pair = None
    for line in counter_bullets:
        left, right = _split_dual_line(line)
        if left:
            counter_pair = (left, right if right and right != left else "（資訊不足）")
            break

    term_pairs = _parse_term_table(terms_section)[:5]
    filtered_terms = []
    seen_terms = set()
    keypoint_jp = {jp for jp, _ in keypoint_pairs}
    for jp, zh in term_pairs:
        if jp in keypoint_jp:
            continue
        entry = (jp, zh or "（資訊不足）")
        if entry in seen_terms:
            continue
        seen_terms.add(entry)
        filtered_terms.append(entry)
        if len(filtered_terms) >= 5:
            break
    term_pairs = filtered_terms

    practice_bullets = _extract_bullets(practice_section)
    practice_pairs = []
    seen_practice = set()
    for line in practice_bullets:
        left, right = _split_dual_line(line)
        entry = (left or "（資訊不足）", right if right and right != left else "（資訊不足）")
        if entry in seen_practice:
            continue
        seen_practice.add(entry)
        practice_pairs.append(entry)
        if len(practice_pairs) >= 2:
            break

    blueprint_parts = []
    blueprint_parts.append("## 🟢 重點\n" + _format_dual_bullets(keypoint_pairs))

    if example_pair:
        blueprint_parts.append("## 🔍 例子\n- 🔹 {}｜{}".format(example_pair[0] or "□", example_pair[1] or example_pair[0]))
    if counter_pair:
        blueprint_parts.append("## ⚠️ 反例\n- 🔹 {}｜{}".format(counter_pair[0] or "□", counter_pair[1] or counter_pair[0]))

    if term_pairs:
        term_lines = _format_dual_bullets(term_pairs)
        blueprint_parts.append(
            f'<details class="terms" data-count="{len(term_pairs)}">\n<summary>術語 {len(term_pairs)}</summary>\n\n{term_lines}\n\n</details>'
        )

    if practice_pairs:
        practice_lines = []
        for idx, (left, right) in enumerate(practice_pairs, start=1):
            practice_lines.append(f"{idx}. {left or '□'}｜{right or left}")
        blueprint_parts.append(
            f'<details class="practice" data-count="{len(practice_lines)}">\n<summary>延伸練習 {len(practice_lines)}</summary>\n\n' +
            "\n".join(practice_lines) + "\n\n</details>"
        )

    return "\n\n".join(blueprint_parts).strip()

COMMON_SYMBOLS = {
    "a_on", "a_off", "A_on", "A_off",
    "s_on", "s_off", "S_on", "S_off",
    "π(a", "π(a|s)", "π(a|s",
    "π(s|a)", "π(a|s)=1", "Σ π(a|s)"
}

FALLBACK_TRANSLATION_MODEL = "qwen3-vl:4b"

TRANSLATION_LANG_NAMES = {
    "zh-TW": "繁體中文",
    "zh-CN": "簡體中文",
    "en": "英文",
    "ja": "日文",
    "ko": "韓文",
    "vi": "越南文",
    "my": "緬甸文",
}

FORMULA_SYMBOLS = set("＝=≠≈≡≤≥±＋-*/÷→↦⇒⇔→←↔∑ΣπΠ√∫∆∇∞％‰‰°λμθβγδαωΩφψχκηζξσρτν∂∀∃∈∉⊆⊂⊇⊃∪∩∧∨¬⊕⊗⊥⊤")
FORMULA_REGEXES = [
    re.compile(r'[A-Za-z]\s*\([\w\s,+\-*/^]+\)'),
    re.compile(r'\b(?:π|sigma|lambda|mu|theta|beta|gamma)\b', re.IGNORECASE),
    re.compile(r'\d+\s*[=→⇒≡]+\s*\d+'),
    re.compile(r'[A-Za-z]+\s*[=→⇒≡]+\s*[A-Za-z0-9]'),
]
MATH_KEYWORDS = [
    "問題", "問", "求め", "求めてください", "求めよ", "求めよ。", "求めなさい",
    "期待値", "確率", "式を", "式の", "方程式", "計算", "導出", "解いて", "証明",
    "Σ", "∑", "π(", "π (", "→", "⇒", "＝", "=", "≡", "積分", "微分"
]

def _japanese_char_ratio(text: str) -> float:
    if not text:
        return 0.0
    jp_count = sum(
        1 for ch in text
        if re.match(r'[\u3040-\u30ff\u3400-\u9fff]', ch)
    )
    total = sum(1 for ch in text if not ch.isspace())
    if total == 0:
        return 0.0
    return jp_count / total

def remove_prompt_leakage(text):
    """
    移除VLM輸出中洩露的提示詞格式說明
    
    這個函數會檢測並移除包含以下特徵的行:
    1. [🚨 ...] 格式的警告標記
    2. [從這張圖片...] [格式範例:...] 等指令文字
    3. [日文原文(假名) → 保持日文!] 等佔位符
    4. [2-3句話說明主題] 等提示文字
    5. [從實際內容中提取] 等指令
    
    Args:
        text: VLM原始輸出
    
    Returns:
        str: 清理後的文字
    """
    logger.info("[NoteFormatter] 開始清理提示詞洩露")
    
    # 🔧 定義需要移除的提示詞模式
    prompt_patterns = [
        # 警告標記
        r'^\s*\[🚨.*?\]\s*$',
        # 指令文字
        r'^\s*\[從這張圖片.*?\]\s*$',
        r'^\s*\[格式範例?:.*?\]\s*$',
        r'^\s*\[從實際?內容中?.*?提取.*?\]\s*$',
        r'^\s*\[.*?句話說明.*?\]\s*$',
        r'^\s*\[.*?保持日文.*?\]\s*$',
        r'^\s*\[中文翻譯\]\s*$',
        r'^\s*\[日文原文.*?\]\s*$',
        r'^\s*\[\.\.\..*?\]\s*$',
        # 包含🚨的任何行
        r'^.*?🚨.*?$',
        # 包含多個[...]的行
        r'^\s*\[.*?\].*?\[.*?\]\s*$',
    ]
    
    lines = text.split('\n')
    filtered_lines = []
    removed_count = 0
    
    for line in lines:
        should_remove = False
        
        for pattern in prompt_patterns:
            if re.match(pattern, line, re.IGNORECASE | re.MULTILINE):
                should_remove = True
                removed_count += 1
                logger.debug(f"[NoteFormatter] 移除提示詞: {line[:50]}...")
                break
        
        if not should_remove:
            filtered_lines.append(line)
    
    if removed_count > 0:
        logger.info(f"[NoteFormatter] 移除了 {removed_count} 行提示詞洩露")
    
    return '\n'.join(filtered_lines)


def _remove_placeholder_lines(text: str) -> str:
    """移除殘留的提示詞或範例佔位符。"""
    placeholder_patterns = [
        r'\[.*?用一個句子.*?\]',
        r'\[Explain the theme.*?\]',
        r'\[2-3.*?\]',
        r'\[以\s*2[-〜~]3.*?\]',
        r'\[用\s*2[-〜~]3.*?\]',
        r'\[Use the actual OCR sentences.*?\]',
        r'\[必須引用上面列出的句子.*?\]',
        r'日文原文:\s*例\d+.*',
        r'意思:\s*例\d+.*',
        r'為什麼重要:\s*例\d+.*',
        r'Key Point \d+:.*',
        r'Point \d+:.*',
        r'^\s*\*\*輸出規則.*',
        r'^\s*輸出規則:.*',
        r'^\s*注意: 只輸出實際內容.*',
    ]
    for pattern in placeholder_patterns:
        text = re.sub(pattern, '', text, flags=re.MULTILINE | re.DOTALL)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def _contains_japanese(text: str) -> bool:
    return bool(re.search(r'[\u3040-\u30ff\u3400-\u9fff]', text or ""))


def _is_formula_like(text: str) -> bool:
    """偵測是否為公式或符號主導的短句。"""
    if not text:
        return False
    stripped = text.strip()
    if not stripped:
        return False
    if any(symbol in stripped for symbol in FORMULA_SYMBOLS):
        return True
    if re.search(r'[A-Za-z]_[A-Za-z0-9]', stripped):
        return True
    if re.search(r'[A-Za-z]\d', stripped):
        return True
    if re.search(r'\d', stripped) and any(op in stripped for op in "=≠≈≡→↦⇒⇔+-*/"):
        return True
    for pattern in FORMULA_REGEXES:
        if pattern.search(stripped):
            return True
    return False


def _normalize_for_lookup(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'\s+', '', text)


def _contains_math_context(text: str) -> bool:
    if not text:
        return False
    for keyword in MATH_KEYWORDS:
        if keyword in text:
            return True
    return False


def _prepare_ocr_excerpt(ocr_text: str, max_length: int = 2000) -> Tuple[str, bool]:
    """整理 OCR 原文，必要時進行裁剪。"""
    if not ocr_text:
        return "", False
    normalized = ocr_text.strip()
    if len(normalized) <= max_length:
        return normalized, False
    truncated = normalized[:max_length]
    newline_idx = truncated.rfind("\n")
    if newline_idx > 0 and (len(truncated) - newline_idx) < 200:
        truncated = truncated[:newline_idx]
    return truncated.strip(), True


async def _get_fallback_translation(
    ocr_excerpt: str,
    language: str,
    cache: Dict[Tuple[str, str], str],
) -> str:
    """呼叫 LLM 產生粗略翻譯，並在同次處理中快取結果。"""
    if not ocr_excerpt or len(ocr_excerpt.strip()) < 4:
        return ""

    key = (language, ocr_excerpt)
    if cache is not None and key in cache:
        return cache[key]

    try:
        from modules.llm_utils import call_llm  # 延遲載入避免循環依賴
        from modules.services.gpu_utils import prepare_llm_inference
    except Exception as exc:
        logger.warning(f"[NoteFormatter] 無法載入 LLM 工具以產生翻譯: {exc}")
        if cache is not None:
            cache[key] = ""
        return ""

    target_lang = TRANSLATION_LANG_NAMES.get(language, "繁體中文")
    prompt = (
        f"請將以下日文 OCR 文字翻譯為{target_lang}，保持原有的換行與符號。"
        "若內容難以辨識，請以「[無法辨識]」標記，避免添加猜測內容。\n\n"
        "--- OCR 原文 ---\n"
        f"{ocr_excerpt}\n"
        "---\n"
        "請僅輸出翻譯內容，無需額外說明。"
    )

    try:
        prepare_llm_inference("note-formatter:translation")
        translation = await call_llm(
            prompt=prompt,
            model=FALLBACK_TRANSLATION_MODEL,
            use_cache=False,
            language=language,
        )
    except Exception as exc:
        logger.error(f"[NoteFormatter] 粗翻譯生成失敗: {exc}")
        translation = ""

    clean_translation = (translation or "").strip()
    if cache is not None:
        cache[key] = clean_translation
    return clean_translation


async def _get_math_explanation(
    ocr_excerpt: str,
    language: str,
    cache: Dict[Tuple[str, str], str],
) -> str:
    if not ocr_excerpt or len(ocr_excerpt.strip()) < 20:
        return ""
    if not _contains_math_context(ocr_excerpt):
        return ""

    key = (language, ocr_excerpt)
    if cache is not None and key in cache:
        return cache[key]

    try:
        from modules.llm_utils import call_llm
        from modules.services.gpu_utils import prepare_llm_inference
    except Exception as exc:
        logger.warning(f"[NoteFormatter] 無法載入 LLM 工具以產生數學解題說明: {exc}")
        if cache is not None:
            cache[key] = ""
        return ""

    target_lang = TRANSLATION_LANG_NAMES.get(language, "繁體中文")
    prompt = (
        f"以下是日文講義的 OCR 內容，包含數學或機率相關題目，請用{target_lang}提供粗略的解題指引。\n"
        "規則：\n"
        "1. 僅能根據 OCR 原文推導，不可擴寫未出現的條件。\n"
        "2. 逐題整理：先重述題目，再列出推導步驟與結論。\n"
        "3. 若資料不足，請註明需要補充資訊。\n"
        "4. 保持條列格式，標註『需人工複核』。\n\n"
        "--- OCR 原文 ---\n"
        f"{ocr_excerpt}\n"
        "-----------------\n"
        "請直接輸出條列解題步驟，不要加入其他說明。"
    )

    try:
        prepare_llm_inference("note-formatter:math-explanation")
        explanation = await call_llm(
            prompt=prompt,
            model=FALLBACK_TRANSLATION_MODEL,
            use_cache=False,
            language=language,
        )
    except Exception as exc:
        logger.error(f"[NoteFormatter] 數學解題提示生成失敗: {exc}")
        explanation = ""

    clean_explanation = (explanation or "").strip()
    if cache is not None:
        cache[key] = clean_explanation
    return clean_explanation


async def _compose_fallback_section(
    header: str,
    preserved_text: str,
    message: str,
    ocr_text: str,
    language: str,
    translation_cache: Dict[Tuple[str, str], str],
    math_cache: Dict[Tuple[str, str], str],
) -> str:
    """建立包含 OCR 原文與粗翻譯的降級區塊。"""
    parts = [header]
    if preserved_text:
        parts.append(preserved_text)
    parts.append("")
    parts.append(message)

    if ocr_text and ocr_text.strip():
        excerpt, truncated = _prepare_ocr_excerpt(ocr_text)
        if excerpt:
            parts.append("")
            parts.append("### 📝 OCR 原文")
            parts.append("```text")
            parts.append(excerpt)
            parts.append("```")
            if truncated:
                parts.append("_註：OCR 原文已截斷，請參考原圖取得完整內容。_")

            translation = await _get_fallback_translation(excerpt, language, translation_cache)
            parts.append("")
            parts.append("### 🌐 粗翻譯 (需人工複核)")
            if translation:
                parts.append(translation)
            else:
                parts.append("自動翻譯未成功，請人工複核。")

            math_steps = await _get_math_explanation(excerpt, language, math_cache)
            if math_steps:
                parts.append("")
                parts.append("### 🧮 粗略解題步驟 (需人工複核)")
                parts.append(math_steps)
    else:
        parts.append("")
        parts.append("目前無法取得 OCR 原文，請重新擷取截圖或調整 OCR 設定。")

    result = "\n".join(parts).rstrip()
    return result + "\n"


def _sanitize_vocab_table(text: str, ocr_text: str) -> str:
    """僅保留 OCR 中出現過的詞彙，避免幻覺詞條。"""
    if not ocr_text:
        return text
    normalized_ocr = ocr_text.replace(" ", "").replace("\n", "")
    table_pattern = re.compile(r"(\|.*\|\n\|[-\s\|]+\|\n(?:\|.*\|\n)+)", re.MULTILINE)

    def _filter_block(match: re.Match) -> str:
        block = match.group(0)
        lines = block.strip("\n").splitlines()
        if len(lines) < 3:
            return block
        header = lines[:2]
        data_rows = lines[2:]
        filtered_rows = []
        for row in data_rows:
            cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
            if not cells:
                continue
            japanese_cell = cells[0].replace(" ", "")
            if not _contains_japanese(japanese_cell):
                continue
            normalized_symbol = re.sub(r'\W+', '', japanese_cell)
            if normalized_symbol in COMMON_SYMBOLS:
                continue
            if japanese_cell and japanese_cell in normalized_ocr:
                filtered_rows.append(row)
        if not filtered_rows:
            logger.warning("[NoteFormatter] 詞彙表行全部被過濾，僅保留表頭")
            return "\n".join(header) + "\n"
        return "\n".join(header + filtered_rows) + "\n"

    return table_pattern.sub(_filter_block, text)


async def _fallback_highlight_section(
    section: str,
    ocr_text: str,
    language: str,
    translation_cache: Dict[Tuple[str, str], str],
    math_cache: Dict[Tuple[str, str], str],
) -> str:
    lines = section.strip("\n").split("\n")
    if not lines:
        return section
    header = lines[0]
    preserved = []
    for line in lines[1:]:
        stripped = line.strip()
        if stripped.startswith("核心內容"):
            break
        preserved.append(line)
    preserved_text = "\n".join(preserved).strip()
    message = "⚠️ 自動解析未能擷取可靠的日文重點，已附上 OCR 原文與粗翻譯，請人工複核後決定是否重處理。"
    return await _compose_fallback_section(
        header,
        preserved_text,
        message,
        ocr_text,
        language,
        translation_cache,
        math_cache,
    )


async def _fallback_detail_section(
    section: str,
    ocr_text: str,
    language: str,
    translation_cache: Dict[Tuple[str, str], str],
    math_cache: Dict[Tuple[str, str], str],
) -> str:
    lines = section.strip("\n").split("\n")
    if not lines:
        return section
    header = lines[0]
    preserved = []
    for line in lines[1:]:
        stripped = line.strip()
        if re.match(r"\d+\.", stripped):
            break
        preserved.append(line)
    preserved_text = "\n".join(preserved).strip()
    message = "⚠️ 自動解析未能產生可信的中文詳解，以下提供 OCR 原文與粗翻譯，請人工檢視。"
    return await _compose_fallback_section(
        header,
        preserved_text,
        message,
        ocr_text,
        language,
        translation_cache,
        math_cache,
    )


async def _sanitize_highlight_sections(
    text: str,
    ocr_text: str,
    language: str,
    translation_cache: Dict[Tuple[str, str], str],
    math_cache: Dict[Tuple[str, str], str],
) -> str:
    pattern = re.compile(r"(## 📌 講義重點.*?)(?=\n## |\Z)", re.DOTALL)
    cursor = 0
    parts: List[str] = []
    normalized_ocr = _normalize_for_lookup(ocr_text)

    for match in pattern.finditer(text):
        start, end = match.span()
        parts.append(text[cursor:start])
        section = match.group(0)
        lowered = section.lower()

        if "use the actual ocr sentences" in lowered or "[用" in section or "[以" in section:
            replacement = await _fallback_highlight_section(
                section, ocr_text, language, translation_cache, math_cache
            )
        else:
            lines = section.split('\n')
            if not lines:
                replacement = section
            else:
                header = lines[0]
                body_lines = lines[1:]
                processed_lines = [header]
                kept_blocks = 0
                removed_blocks = False
                i = 0

                while i < len(body_lines):
                    line = body_lines[i]
                    bullet_match = re.match(r'^\s*-\s*日文:\s*(.*)$', line)
                    if bullet_match:
                        block = [line]
                        i += 1
                        # 收集對應的子項 (中文、重要性等)
                        while i < len(body_lines):
                            next_line = body_lines[i]
                            if re.match(r'^\s*-\s*日文:\s*', next_line):
                                break
                            if next_line.startswith('  ') or not next_line.strip():
                                block.append(next_line)
                                i += 1
                            else:
                                break

                        jp_text = bullet_match.group(1).strip()
                        normalized_jp = _normalize_for_lookup(jp_text)

                        keep = True
                        if len(jp_text) < 6 and not _is_formula_like(jp_text):
                            keep = False
                        if not _contains_japanese(jp_text) and not _is_formula_like(jp_text):
                            keep = False
                        if _japanese_char_ratio(jp_text) < 0.3 and not _is_formula_like(jp_text):
                            keep = False
                        if normalized_ocr and normalized_jp and normalized_jp not in normalized_ocr and not _is_formula_like(jp_text):
                            keep = False

                        if keep:
                            processed_lines.extend(block)
                            kept_blocks += 1
                        else:
                            removed_blocks = True
                        continue

                    processed_lines.append(line)
                    i += 1

                if kept_blocks <= 1:
                    replacement = await _fallback_highlight_section(
                        section, ocr_text, language, translation_cache, math_cache
                    )
                else:
                    if removed_blocks:
                        replacement = "\n".join(processed_lines)
                    else:
                        replacement = section

        parts.append(replacement)
        cursor = end

    parts.append(text[cursor:])
    return "".join(parts)


async def _sanitize_detail_sections(
    text: str,
    ocr_text: str,
    language: str,
    translation_cache: Dict[Tuple[str, str], str],
    math_cache: Dict[Tuple[str, str], str],
) -> str:
    pattern = re.compile(r"(## 📖 繁體中文詳解.*?)(?=\n## |\Z)", re.DOTALL)
    cursor = 0
    parts: List[str] = []
    normalized_ocr = _normalize_for_lookup(ocr_text)

    for match in pattern.finditer(text):
        start, end = match.span()
        parts.append(text[cursor:start])
        section = match.group(0)

        if "[用" in section or "[以" in section or "必須引用上面列出的句子" in section:
            replacement = await _fallback_detail_section(
                section, ocr_text, language, translation_cache, math_cache
            )
        else:
            lines = section.split('\n')
            if not lines:
                replacement = section
            else:
                header = lines[0]
                body_lines = lines[1:]
                processed_lines = [header]
                kept_blocks = 0
                removed_blocks = False
                i = 0

                while i < len(body_lines):
                    line = body_lines[i]
                    select_match = re.match(r'^\s*\d+\.\s', line)
                    if select_match:
                        block = [line]
                        i += 1
                        while i < len(body_lines):
                            next_line = body_lines[i]
                            if re.match(r'^\s*\d+\.\s', next_line):
                                break
                            if next_line.startswith('   ') or next_line.startswith('\t') or next_line.strip().startswith('- ') or not next_line.strip():
                                block.append(next_line)
                                i += 1
                            else:
                                break

                        jp_text = ""
                        for block_line in block:
                            jp_match = re.match(r'^\s*-\s*日文原文:\s*(.*)$', block_line)
                            if jp_match:
                                jp_text = jp_match.group(1).strip()
                                break

                        keep = True
                        if jp_text:
                            normalized_jp = _normalize_for_lookup(jp_text)
                            if len(jp_text) < 6 and not _is_formula_like(jp_text):
                                keep = False
                            if not _contains_japanese(jp_text) and not _is_formula_like(jp_text):
                                keep = False
                            if _japanese_char_ratio(jp_text) < 0.3 and not _is_formula_like(jp_text):
                                keep = False
                            if normalized_ocr and normalized_jp and normalized_jp not in normalized_ocr and not _is_formula_like(jp_text):
                                keep = False

                        if keep and jp_text:
                            processed_lines.extend(block)
                            kept_blocks += 1
                        elif keep and not jp_text:
                            # 如果沒有日文原文,但整個區塊提供有效說明,保留
                            processed_lines.extend(block)
                            kept_blocks += 1
                        else:
                            removed_blocks = True
                        continue

                    processed_lines.append(line)
                    i += 1

                if kept_blocks == 0:
                    replacement = await _fallback_detail_section(
                        section, ocr_text, language, translation_cache, math_cache
                    )
                else:
                    if removed_blocks:
                        replacement = "\n".join(processed_lines)
                    else:
                        replacement = section

        parts.append(replacement)
        cursor = end

    parts.append(text[cursor:])
    return "".join(parts)


def convert_to_furigana(japanese_text):
    """
    將日文文字轉換為假名
    
    使用 pykakasi 自動生成正確的假名,避免 VLM 幻覺產生錯誤假名
    
    規則:
    1. 片假名詞彙保持片假名 (例: サーバ → サーバ)
    2. 平假名詞彙轉換為平假名 (例: 失敗 → しっぱい)
    3. 外來語保持片假名 (例: クラウド → クラウド)
    
    Args:
        japanese_text: 日文原文
    
    Returns:
        str: 假名讀音
    """
    if not japanese_text or not japanese_text.strip():
        return ""
    
    japanese_text = japanese_text.strip()
    
    # 🎯 檢查是否全部是片假名
    katakana_pattern = r'^[ァ-ヶー]+$'
    if re.match(katakana_pattern, japanese_text):
        # 全片假名詞彙 (外來語) 保持原樣
        logger.debug(f"[FuriganaConverter] 片假名詞彙保持原樣: {japanese_text}")
        return japanese_text
    
    # 🎯 檢查是否全部是平假名
    hiragana_pattern = r'^[ぁ-ん]+$'
    if re.match(hiragana_pattern, japanese_text):
        # 已經是平假名,直接返回
        logger.debug(f"[FuriganaConverter] 已是平假名: {japanese_text}")
        return japanese_text
    
    # 🎯 使用 pykakasi 轉換
    if PYKAKASI_AVAILABLE:
        try:
            result = kks.convert(japanese_text)
            # pykakasi 返回的是字典列表
            furigana_parts = []
            for item in result:
                # 檢查是否為片假名原文
                orig = item.get('orig', '')
                hira = item.get('hira', '')  # 平假名
                
                # 如果原文是片假名,保持片假名
                if re.match(katakana_pattern, orig):
                    furigana_parts.append(orig)
                # 否則使用平假名
                elif hira:
                    furigana_parts.append(hira)
                else:
                    furigana_parts.append(orig)
            
            furigana = ''.join(furigana_parts)
            logger.debug(f"[FuriganaConverter] pykakasi 轉換: {japanese_text} → {furigana}")
            return furigana
        except Exception as e:
            logger.warning(f"[FuriganaConverter] pykakasi 轉換失敗: {japanese_text}, 錯誤: {e}")
    
    # 🎯 如果工具失敗,返回原文
    logger.warning(f"[FuriganaConverter] 無法轉換假名,返回原文: {japanese_text}")
    return japanese_text


def format_japanese_highlights(text, language="zh-TW"):
    """
    強制格式化日文重點部分 - 使用正確的格式
    
    正確格式 (根據文檔):
    **學習要點**
    - 日文原文 → 中文翻譯
    
    Args:
        text: VLM原始輸出
        language: 語言代碼
    
    Returns:
        str: 格式化後的文字
    """
    logger.info("[NoteFormatter] 開始格式化日文重點")
    
    # 🔧 清理提示詞模板文字和範例
    cleanup_patterns = [
        r'從OCR文字中提取.*?格式如下:',
        r'MANDATORY FORMAT.*?translation\]',
        r'範例:',
        r'EXAMPLE OUTPUT:',
        r'請按照以下格式輸出:',
        r'每個重點格式如下:',
        # 清理範例文字
        r'- 日文原文句子\d+ → 中文翻譯\d+',
        r'學習要點\s*\n\s*- 日文原文句子',
    ]
    
    for pattern in cleanup_patterns:
        text = re.sub(pattern, '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # 轉換為正確格式: - 日文 → 中文
    # 移除 **粗體** 標記 (除了 **學習要點**)
    text = re.sub(r'\*\*([^*學習要點]+?)\*\*', r'\1', text)
    
    # 統一箭頭格式: "→ 中文:" 改為 " → "
    text = re.sub(r'→\s*中文[:：]\s*', ' → ', text)
    
    # 🔧 強制轉換 • 為 -
    text = re.sub(r'^\s*[•●]\s*', '- ', text, flags=re.MULTILINE)
    
    # 🔧 確保有 "**學習要點**" 標題
    # 如果在 "講義重點" 後面有 bullet list 但沒有 "學習要點" 標題
    if '## 📌 講義重點' in text:
        # 檢查是否已經有 **學習要點**
        if '**學習要點**' not in text:
            # 在第一個 "- " 前面加上標題
            text = re.sub(
                r'(## 📌 講義重點.*?\n\n)(- )',
                r'\1**學習要點**\n\2',
                text,
                count=1,
                flags=re.DOTALL
            )
    
    # 🔧 移除重複的 "學習要點" 標題(可能出現兩次)
    # 保留第一個,刪除後續的
    first_found = False
    lines = text.split('\n')
    result_lines = []
    for line in lines:
        if line.strip() == '學習要點':
            if not first_found:
                first_found = True
                result_lines.append(line)
            # 否則跳過(不加入)
        else:
            result_lines.append(line)
    text = '\n'.join(result_lines)
    
    logger.info("[NoteFormatter] 格式化完成")
    return text


async def _classify_vocab_terms(entries: List[Dict[str, str]], language: str) -> Dict[str, bool]:
    """
    使用 LLM 判斷每個詞彙是否屬於「專門／高難度」用語。
    返回 mapping: term -> is_expert
    """
    if not entries:
        return {}

    instruction = (
        "You are a bilingual Japanese CS instructor evaluating vocabulary difficulty. "
        "Students already passed JLPT N2, so only specialized, technical, or rare terms "
        "should be flagged as true. Common networking words (network, server, service, stable, operation, point, etc.) "
        "must be false. Return STRICT JSON array with objects: "
        "{\"term\": \"...\", \"isExpert\": true/false, \"reason\": \"...\"}. "
        "If unsure, output false.\n\nEntries:\n"
    )
    prompt = instruction + json.dumps(entries, ensure_ascii=False, indent=2)
    try:
        response = await call_llm(
            prompt=prompt,
            model="qwen3-vl:4b",
            language=language or "en",
            use_cache=False,
        )
        cleaned = response.strip().strip("`")
        cleaned = re.sub(r"^json", "", cleaned, flags=re.IGNORECASE).strip()
        data = json.loads(cleaned)
        result: Dict[str, bool] = {}
        for item in data:
            term = str(item.get("term") or "").strip()
            if not term:
                continue
            result[term] = bool(item.get("isExpert"))
        return result
    except Exception as exc:  # pragma: no cover - network/LLM failure
        logger.warning("[NoteFormatter] Vocab classification failed: %s", exc)
        return {}


async def filter_vocabulary_table(text, language: str = "zh-TW"):
    """
    過濾詞彙表中不合適的項目
    
    過濾規則:
    1. 移除單字詞(日文長度=1)
    2. 移除過於通用的詞(如:點、動、傷)
    3. 去除重複項
    4. 優先保留複合詞和技術術語
    
    Args:
        text: 包含詞彙表的Markdown文本
    
    Returns:
        str: 過濾後的文本
    """
    logger.info("[NoteFormatter] 開始過濾詞彙表")
    
    try:
        import re
        
        # 通用詞黑名單(太簡單或通用的詞)
        blacklist = {
            '點', 'ポイント', 'point',
            '動', 'どう', 'move',
            '傷', 'きず', 'wound',
            '終局', 'じゅうご', 'end',
            '重要', 'じゅうよう', 'important',
            # 常見且過於基礎的術語（使用者提供）
            'ネットワーク', '網絡', 'network',
            'サービス', '服務', 'service',
            'サーバ', '服務器', 'server',
            '安定的', '穩定的', 'stable',
            '運用', '運行', '操作', 'operation', '運営',
            'ポイント', '重點', 'point',
        }
        
        table_patterns = [
            re.compile(r'(重要詞彙表[:：].*?\n)((?:\|[^\n]+\n)+)', re.MULTILINE),
            re.compile(r'(##\s+📚[^\n]*\n)((?:\|[^\n]+\n)+)', re.MULTILINE),
        ]
        table_matches = []
        for pattern in table_patterns:
            for match in pattern.finditer(text):
                table_matches.append(
                    {
                        "start": match.start(),
                        "end": match.end(),
                        "full": match.group(0),
                        "header": match.group(1),
                        "table": match.group(2),
                    }
                )
        
        if not table_matches:
            logger.info("[NoteFormatter] 未找到詞彙表")
            return text
        
        for match in sorted(table_matches, key=lambda m: m["start"], reverse=True):
            header = match["header"]
            table_content = match["table"]
            
            # 解析表格行
            lines = table_content.strip().split('\n')
            if len(lines) < 3:  # 至少需要 header + separator + 1 row
                continue
            
            # 保留表頭
            table_header = lines[0]
            separator = lines[1]
            data_rows = lines[2:]
            
            # 過濾數據行
            filtered_rows = []
            seen_japanese = set()
            entries_for_llm: List[Dict[str, str]] = []
            
            parsed_rows: List[Tuple[str, Dict[str, str]]] = []
            for row in data_rows:
                parts = [p.strip() for p in row.split('|')]
                if len(parts) < 5:  # | 日文 | 假名 | 中文 | 備註 |
                    continue
                
                japanese = parts[1].strip()
                vlm_furigana = parts[2].strip()  # VLM 生成的假名(可能錯誤)
                chinese = parts[3].strip()
                remark = parts[4].strip()
                
                # 🎯 使用自動假名轉換替換 VLM 生成的假名
                correct_furigana = convert_to_furigana(japanese)
                
                # 記錄假名修正
                if vlm_furigana != correct_furigana:
                    logger.info(f"[FuriganaFix] 修正假名: {japanese} | {vlm_furigana} → {correct_furigana}")
                
                # 更新 row 中的假名
                parts[2] = correct_furigana
                normalized_row = '|'.join(parts)
                parsed_rows.append((normalized_row, {
                    "term": japanese,
                    "reading": correct_furigana,
                    "translation": chinese,
                    "remark": remark,
                }))
                entries_for_llm.append({
                    "term": japanese,
                    "reading": correct_furigana,
                    "translation": chinese,
                    "remark": remark[:80],
                })

            llm_decisions: Dict[str, bool] = {}
            if entries_for_llm:
                llm_decisions = await _classify_vocab_terms(entries_for_llm, language)

            for normalized_row, info in parsed_rows:
                japanese = info["term"]
                chinese = info["translation"]
                reading = info["reading"]

                if len(japanese) == 1:
                    logger.debug(f"[NoteFormatter] 過濾單字詞: {japanese}")
                    continue

                if japanese in blacklist or chinese in blacklist or reading in blacklist:
                    logger.debug(f"[NoteFormatter] 過濾黑名單詞: {japanese}")
                    continue

                decision = llm_decisions.get(japanese)
                if decision is not None and decision is False:
                    logger.debug(f"[NoteFormatter] VLM 判定為基礎詞彙: {japanese}")
                    continue

                if japanese in seen_japanese:
                    logger.debug(f"[NoteFormatter] 過濾重複詞: {japanese}")
                    continue

                seen_japanese.add(japanese)
                filtered_rows.append(normalized_row)
            
            # 重建表格
            if filtered_rows:
                new_table = '\n'.join([table_header, separator] + filtered_rows) + '\n'
                new_content = header + new_table
                text = text[:match["start"]] + new_content + text[match["end"]:]
                logger.info(
                    "[NoteFormatter] 詞彙表過濾: %s → %s 項",
                    len(data_rows),
                    len(filtered_rows),
                )
            else:
                text = text[:match["start"]] + '' + text[match["end"]:]
                logger.warning("[NoteFormatter] 詞彙表全部被過濾,已移除")
        
        return text
        
    except Exception as e:
        logger.error(f"[NoteFormatter] 過濾詞彙表失敗: {e}")
        return text


async def format_vlm_output(vlm_output, language="zh-TW", ocr_text=""):
    """
    完整格式化VLM輸出
    
    Args:
        vlm_output: VLM原始輸出文字
        language: 語言代碼
    
    Returns:
        str: 格式化後的筆記
    """
    logger.info("[NoteFormatter] 開始完整格式化")
    
    if not vlm_output or not vlm_output.strip():
        logger.warning("[NoteFormatter] 輸入為空")
        return vlm_output
    
    result = vlm_output
    
    # 如果已經是 Blueprint 結構，僅做最小清理並返回
    if "## 🟢 重點" in result:
        logger.info("[NoteFormatter] 偵測到 Blueprint 格式，執行精簡清理流程")
        result = remove_prompt_leakage(result)
        result = _remove_placeholder_lines(result)
        result = _remove_repeated_sections(result)
        result = _clean_duplicate_content(result)
        result = _standardize_blueprint(result)
        result = re.sub(r'\n{3,}', '\n\n', result)
        return result.strip()
    
    # 🎯 優先移除提示詞洩露 (新增)
    result = remove_prompt_leakage(result)
    result = _remove_placeholder_lines(result)

    if "# 📚 講義筆記" in result and "## 🟢 重點" not in result:
        logger.info("[NoteFormatter] 偵測到舊版模板，嘗試轉換為 Blueprint 格式")
        converted = _convert_legacy_to_blueprint(result)
        if "## 🟢 重點" in converted:
            logger.info("[NoteFormatter] 舊版模板已成功轉換為 Blueprint")
            return converted
        result = converted
    
    # 1. 🔧 清理提示詞模板文字(VLM可能把範例也輸出了)
    template_patterns = [
        r'- 日文原文句子\d+ → 中文翻譯\d+',
        r'學習要點\n- 日文原文句子',
        r'範例:\s*\n',
        # 新增:清理提示詞中的範例格式
        r'- 日文\d+\(ふりがな\) → 中文翻譯',
        r'- \[日文原文\] → \[中文翻譯\]',
        r'\[一句話.*?\]',
        r'\[第.*?重點.*?\]',
        r'\[簡.*?說明.*?\]',
        # 清理輸出規則說明
        r'輸出規則:.*?開始輸出:',
        r'請開始輸出.*?不要重複.*?:',
        r'\*\*輸出規則\*\*:.*?開始輸出:',
    ]
    for pattern in template_patterns:
        result = re.sub(pattern, '', result, flags=re.MULTILINE | re.DOTALL)
    
    # 2. 🔧 移除VLM自己加的圖片標記(圖片由note_generator統一處理)
    result = re.sub(r'!\[.*?\]\(.*?\)', '', result)
    result = result.replace('{{image_placeholder}}', '')
    
    # 2.5. 🔧 移除國旗emoji(避免前端UI異常顯示)
    result = re.sub(r'[🇯🇵🇹🇼🇨🇳🇰🇷🇺🇸🇻🇳]+', '', result)
    # 也移除可能的 JP TW 標記
    result = re.sub(r'^\s*🇯🇵\s*', '', result, flags=re.MULTILINE)
    result = re.sub(r'^\s*🇹🇼\s*→\s*', '→ ', result, flags=re.MULTILINE)
    
    # 3. 格式化日文重點部分
    if '📌 講義重點' in result or '→ 中文:' in result or '→中文:' in result:
        result = format_japanese_highlights(result, language)
    
    # 3.5. 🔧 過濾詞彙表 - 移除單字詞、通用詞、重複項
    vocab_triggers = ('重要詞彙表', '📚 重要術語對照', '📚 術語對照')
    if any(trigger in result for trigger in vocab_triggers):
        result = await filter_vocabulary_table(result, language)
        result = _sanitize_vocab_table(result, ocr_text)
    
    # 3.6. 🔧 清理品質不佳的重點與詳解區塊
    translation_cache: Dict[Tuple[str, str], str] = {}
    math_cache: Dict[Tuple[str, str], str] = {}

    if '📌 講義重點' in result:
        result = await _sanitize_highlight_sections(result, ocr_text, language, translation_cache, math_cache)
    if '📖 繁體中文詳解' in result:
        result = await _sanitize_detail_sections(result, ocr_text, language, translation_cache, math_cache)
    
    result = _remove_repeated_sections(result)
    result = _standardize_blueprint(result)
    result = _normalize_section_headings(result)
    result = _split_inline_code_headings(result)
    result = _force_section_headings(result)
    result = _normalize_headings(result)
    result = _strip_empty_code_sections(result)
    result = _strip_broken_glossary_sections(result)
    result = _strip_malformed_tables(result)
    result = _strip_broken_math_lines(result)

    if language == "zh-TW":
        result = _ensure_traditional_zh(result)

    # 4. 清理多餘的空行
    result = re.sub(r'\n{3,}', '\n\n', result)
    
    # 5. 🔧 移除結尾的說明文字
    result = re.sub(r'---\s*$', '', result)

    # 6. 🔁 移除重複內容
    result = _clean_duplicate_content(result)
    
    logger.info("[NoteFormatter] 格式化完成")
    return result


def _ensure_traditional_zh(text: str) -> str:
    if not text:
        return text

    simplified_markers = re.compile(r"[马尔决动归灯为场复计验类条况输出]")

    def has_simplified(segment: str) -> bool:
        return bool(simplified_markers.search(segment))

    def fallback_convert(segment: str) -> str:
        # Focused mapping for common technical terms; keep ASCII/code intact.
        replacements = [
            ("马尔可夫", "馬爾可夫"),
            ("决策", "決策"),
            ("状态", "狀態"),
            ("动作", "動作"),
            ("行动", "行動"),
            ("概率", "機率"),
            ("归一化", "歸一化"),
            ("条件", "條件"),
            ("计算", "計算"),
            ("说明", "說明"),
            ("输出", "輸出"),
            ("验证", "驗證"),
            ("示例", "示例"),
            ("场景", "場景"),
            ("问题", "問題"),
            ("理论", "理論"),
            ("实现", "實作"),
            ("学习", "學習"),
            ("简单", "簡單"),
            ("复杂", "複雜"),
            ("总结", "總結"),
            ("结果", "結果"),
            ("步骤", "步驟"),
            ("奖励", "獎勵"),
            ("报酬", "報酬"),
        ]
        out = segment
        for src, dst in replacements:
            out = out.replace(src, dst)
        return out

    def convert_segment(segment: str) -> str:
        if not has_simplified(segment):
            return segment
        try:
            from opencc import OpenCC  # type: ignore
            converter = OpenCC("s2t")
            return converter.convert(segment)
        except Exception:
            return fallback_convert(segment)

    parts = re.split(r"(```[\s\S]*?```)", text)
    converted = []
    for part in parts:
        if part.startswith("```"):
            converted.append(part)
            continue
        converted.append(convert_segment(part))
    return "".join(converted)


def ensure_highlights_format(note_text):
    """
    確保講義重點部分有正確的格式
    
    如果VLM完全沒有輸出日文重點,嘗試從OCR文字補充
    """
    if '## 📌 講義重點' not in note_text:
        logger.warning("[NoteFormatter] 缺少講義重點區塊")
        return note_text
    
    # 檢查是否有實際的日文內容
    highlights_section = re.search(r'## 📌 講義重點.*?(?=\n##|\Z)', note_text, re.DOTALL)
    if highlights_section:
        content = highlights_section.group(0)
        # 如果區塊內沒有日文字符,標記警告
        if not re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', content):
            logger.warning("[NoteFormatter] 講義重點區塊缺少日文內容")
    
    return note_text
