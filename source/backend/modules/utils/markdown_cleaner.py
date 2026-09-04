import re
import html
from typing import Iterable


# Patterns to strip hallucinated HTML/span artifacts
_TAG_LIST = r"(?:span|spanclass|div|p|img|a|code|pre|br|strong|em|b|i|u|mark|table|thead|tbody|tr|td|th|ul|ol|li|figure|figcaption|section|article|header|footer|nav|math|mrow|mstyle|mtext|mfrac|msup|msub|mtable|mi|mo|mn)"
_RAW_TAG_RE = re.compile(rf"</?{_TAG_LIST}[^>]*>", re.IGNORECASE)
_ESCAPED_TAG_RE = re.compile(rf"&lt;/?{_TAG_LIST}[^&]*?&gt;", re.IGNORECASE)
_SPANCLASS_ATTR_RE = re.compile(r"spanclass\\s*=\\s*[\"'][^\"']*[\"']>?", re.IGNORECASE)
_HLJS_WORD_RE = re.compile(r"\\b(h?l?js-[a-z0-9_-]+|hjs-number)\\b", re.IGNORECASE)
_MATH_BLOCK_RE = re.compile(r"<math[^>]*?>.*?</math>", re.IGNORECASE | re.DOTALL)


def _collapse_punctuation_runs(line: str) -> str:
    if not line:
        return line
    return re.sub(r"([,，。.!?！？、])\1{3,}", r"\1\1", line)


def _is_repetitive_noise_line(line: str) -> bool:
    s = (line or "").strip()
    if not s or len(s) < 12:
        return False
    if s.startswith("```"):
        return False

    tokens = s.split()
    if len(tokens) >= 12 and len(set(tokens)) == 1:
        return True

    compact = re.sub(r"[\s\W_]+", "", s, flags=re.UNICODE)
    if len(compact) < 20:
        return False

    char_counts = {}
    for ch in compact:
        char_counts[ch] = char_counts.get(ch, 0) + 1
    top_count = max(char_counts.values()) if char_counts else 0
    if top_count / max(1, len(compact)) >= 0.8:
        return True

    if re.fullmatch(r"(.)\1{15,}", compact):
        return True

    return False


def _clean_math(text: str) -> str:
    """Best-effort math normalization: convert common ascii markers to LaTeX."""
    if not text:
        return ""
    cleaned = text
    # sigma/pi replacements (only when used as tokens)
    cleaned = re.sub(r"\bsigma\b", r"\\sum", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bpi\s*\(", r"\\pi(", cleaned)
    cleaned = re.sub(r"\bx\s+", r"\\times ", cleaned)
    return cleaned


def _repair_code_fences(text: str) -> str:
    """Remove malformed ``` patterns and balance fences in one pass."""
    if not text:
        return ""
    
    lines = text.splitlines()
    fence_re = re.compile(r"^(\s*)```(\S*)?\s*$")
    out = []
    in_fence = False
    i = 0
    
    while i < len(lines):
        line = lines[i]
        match = fence_re.match(line)
        
        if match:
            lang = (match.group(2) or "").strip()
            
            # Check for malformed patterns
            if i + 1 < len(lines):
                next_match = fence_re.match(lines[i + 1])
                if next_match:
                    next_lang = (next_match.group(2) or "").strip()
                    # Skip standalone ``` after ```lang OR consecutive ``` ```
                    if (lang and not next_lang) or (not lang and not next_lang):
                        out.append(line)
                        if lang:
                            in_fence = True
                        else:
                            in_fence = not in_fence
                        i += 2  # Skip malformed next line
                        continue
            
            # Normal fence handling
            if not in_fence:
                in_fence = True
                out.append(line)
            elif lang:
                out.append("```")
                out.append(line)
                in_fence = True
            else:
                in_fence = False
                out.append(line)
        else:
            out.append(line)
        
        i += 1
    
    if in_fence:
        out.append("```")
    
    return "\n".join(out)


def _normalize_latex_backslashes(text: str) -> str:
    if not text:
        return ""
    lines = text.splitlines()
    out = []
    in_fence = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue
        out.append(re.sub(r"\\{2,}([A-Za-z])", r"\\\1", line))
    return "\n".join(out)


def clean_markdown(text: str) -> str:
    """
    Remove hallucinated HTML/span artifacts and lightly normalize math before persistence.

    - Strips raw/escaped span/spanclass/hljs tags that leak into markdown
    - Removes inline style/width/height attributes
    - Normalizes common math tokens to LaTeX-friendly forms
    - Unescapes basic HTML entities (e.g., &quot; -> ")
    """
    if not text:
        return ""

    working = html.unescape(text)
    working = _RAW_TAG_RE.sub("", working)
    working = _ESCAPED_TAG_RE.sub("", working)
    working = _MATH_BLOCK_RE.sub("", working)
    working = _SPANCLASS_ATTR_RE.sub("", working)
    working = _HLJS_WORD_RE.sub("", working)

    # Strip inline style/size attributes
    working = re.sub(r"\\s(style|width|height)\\s*=\\s*\"[^\"]*\"", "", working, flags=re.IGNORECASE)
    working = re.sub(r"\\s(style|width|height)\\s*=\\s*'[^']*'", "", working, flags=re.IGNORECASE)

    working = _clean_math(working)
    working = _repair_code_fences(working)
    working = _normalize_latex_backslashes(working)

    # Remove highly repetitive noise lines outside fenced code blocks.
    cleaned_lines = []
    in_fence = False
    for line in working.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            cleaned_lines.append(line)
            continue
        if in_fence:
            cleaned_lines.append(line)
            continue
        line = _collapse_punctuation_runs(line)
        if _is_repetitive_noise_line(line):
            continue
        cleaned_lines.append(line)
    working = "\n".join(cleaned_lines)

    # Collapse excessive blank lines
    working = re.sub(r"\\n{3,}", "\\n\\n", working)
    return working.strip()


def clean_many(texts: Iterable[str]) -> Iterable[str]:
    """Convenience helper to clean multiple strings."""
    for t in texts:
        yield clean_markdown(t)
