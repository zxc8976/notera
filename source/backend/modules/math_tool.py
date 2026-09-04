import os
import re
import logging
from functools import lru_cache
from typing import List, Dict, Any

try:
    from sympy import Eq, Sum, Integral, Product, simplify
    from sympy.parsing.latex import parse_latex
except Exception:  # pragma: no cover - 安裝前可能缺少 sympy
    Eq = Sum = Integral = Product = None
    parse_latex = None

logger = logging.getLogger(__name__)

_FORMULA_PATTERN = re.compile(
    r'\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\)|\$\$[\s\S]+?\$\$|\$[^$]+\$'
)


def math_tool_enabled() -> bool:
    """
    判斷是否啟用數學工具（透過環境變數 ENABLE_MATH_TOOL 控制）
    """
    return os.getenv("ENABLE_MATH_TOOL", "false").lower() in {"1", "true", "yes", "on"}


def _strip_delimiters(formula: str) -> str:
    formula = formula.strip()
    if formula.startswith(r"\[") and formula.endswith(r"\]"):
        return formula[2:-2].strip()
    if formula.startswith(r"\(") and formula.endswith(r"\)"):
        return formula[2:-2].strip()
    if formula.startswith("$$") and formula.endswith("$$"):
        return formula[2:-2].strip()
    if formula.startswith("$") and formula.endswith("$"):
        return formula[1:-1].strip()
    return formula


def _detect_formulas(text: str) -> List[str]:
    if not text:
        return []
    seen = set()
    ordered = []
    for match in _FORMULA_PATTERN.findall(text):
        normalized = match.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    return ordered


def _summarise_sum(sum_expr) -> str:
    segments = []
    for limits in getattr(sum_expr, "limits", []):
        symbol = limits[0]
        lower = limits[1] if len(limits) > 1 else None
        upper = limits[2] if len(limits) > 2 else None
        segment = f"{symbol}"
        if lower is not None and upper is not None:
            segment += f" 從 {lower} 到 {upper}"
        elif upper is not None:
            segment += f" ≤ {upper}"
        segments.append(segment)
    limits_str = "；".join(str(s) for s in segments) if segments else "未指定上下界"
    return f"求和項目：{sum_expr.function}；指標設定：{limits_str}"


def _summarise_integral(integral_expr) -> str:
    segments = []
    for limits in getattr(integral_expr, "limits", []):
        symbol = limits[0]
        lower = limits[1] if len(limits) > 1 else None
        upper = limits[2] if len(limits) > 2 else None
        segment = f"對 {symbol} 積分"
        if lower is not None and upper is not None:
            segment += f"，區間 [{lower}, {upper}]"
        segments.append(segment)
    return f"被積函數：{integral_expr.function}；{('；'.join(str(s) for s in segments) or '未提供積分範圍')}"


def _summarise_product(prod_expr) -> str:
    segments = []
    for limits in getattr(prod_expr, "limits", []):
        symbol = limits[0]
        lower = limits[1] if len(limits) > 1 else None
        upper = limits[2] if len(limits) > 2 else None
        segment = f"{symbol}"
        if lower is not None and upper is not None:
            segment += f" 從 {lower} 到 {upper}"
        segments.append(segment)
    limits_str = "；".join(str(s) for s in segments) if segments else "未指定上下界"
    return f"乘積項目：{prod_expr.function}；指標設定：{limits_str}"


@lru_cache(maxsize=128)
def _analyze_formula_cached(formula: str) -> Dict[str, Any]:
    if parse_latex is None:
        return {
            "formula": formula,
            "status": "parser_unavailable",
            "analysis": [
                "未安裝 SymPy，無法提供符號推導分析。",
                f"原始表達式：{formula}"
            ]
        }

    stripped = _strip_delimiters(formula)
    stripped = stripped.replace("|", r"\mid ")
    stripped = stripped.replace(r"\left\mid", r"\mid").replace(r"\right\mid", r"\mid")

    try:
        parsed = parse_latex(stripped)
    except Exception as exc:
        logger.debug("parse_latex 解析失敗: %s", exc)
        heuristics = []
        if r"\sum" in stripped:
            heuristics.append("偵測到求和符號 `\\sum`，請說明求和指標範圍與其物理/機率意義。")
        if r"\int" in stripped:
            heuristics.append("偵測到積分符號 `\\int`，請標註積分變數與上下限。")
        if r"\pi" in stripped:
            heuristics.append("公式包含 `\\pi` 策略函數，請解釋該符號代表的條件機率。")
        if "|" in formula or r"\mid" in stripped:
            heuristics.append("請補充條件機率 `|`（或 `\\mid`）的含義與上下文條件。")
        if not heuristics:
            heuristics.append("工具無法直接解析此 LaTeX 公式，請在回應中以文字解釋符號含義。")
        return {
            "formula": formula,
            "status": "parse_failed",
            "analysis": [
                *heuristics,
                f"原始表達式：{formula}"
            ]
        }

    analysis_lines: List[str] = []

    if hasattr(parsed, "free_symbols"):
        symbols_list = sorted(str(sym) for sym in parsed.free_symbols)
        if symbols_list:
            analysis_lines.append(f"涉及符號：{', '.join(symbols_list)}")

    if isinstance(parsed, Eq):
        lhs = parsed.lhs
        rhs = parsed.rhs
        analysis_lines.append(f"等式左側：{lhs}")
        analysis_lines.append(f"等式右側：{rhs}")
        try:
            diff = simplify(lhs - rhs)
            if diff == 0:
                analysis_lines.append("推導檢查：左右兩側相減可化為 0，表示等式恆成立。")
            else:
                analysis_lines.append(f"推導檢查：左右差異化簡為 {diff}，可再說明其意義或條件。")
        except Exception:
            analysis_lines.append("推導檢查：無法簡化等式差異，請在說明中補充條件。")
    else:
        analysis_lines.append(f"解析後的主要結構：{parsed}")

    if Sum is not None and parsed.has(Sum):
        for sum_expr in parsed.atoms(Sum):
            analysis_lines.append(_summarise_sum(sum_expr))

    if Integral is not None and parsed.has(Integral):
        for integral_expr in parsed.atoms(Integral):
            analysis_lines.append(_summarise_integral(integral_expr))

    if Product is not None and parsed.has(Product):
        for prod_expr in parsed.atoms(Product):
            analysis_lines.append(_summarise_product(prod_expr))

    try:
        simplified = simplify(parsed)
        if simplified != parsed:
            analysis_lines.append(f"化簡結果：{simplified}")
    except Exception:
        logger.debug("化簡時發生例外，忽略", exc_info=True)

    if not analysis_lines:
        analysis_lines.append("工具已解析該表達式，但未獲得特別可用的結構資訊，請以語意方式說明。")

    return {
        "formula": formula,
        "status": "ok",
        "analysis": analysis_lines
    }


def build_math_analysis(text: str) -> str:
    """
    根據文字內容提取並分析 LaTeX 公式，回傳結構化的提示字串
    """
    if not math_tool_enabled():
        return ""

    formulas = _detect_formulas(text or "")
    if not formulas:
        return ""

    logger.info("[math_tool] 檢測到 %d 個公式", len(formulas))
    results = [_analyze_formula_cached(formula) for formula in formulas]

    lines: List[str] = []
    lines.append("【數學工具解析摘要】")
    for idx, item in enumerate(results, 1):
        lines.append(f"### 公式 {idx}")
        lines.append(f"原式：{item['formula']}")
        lines.append("解析要點：")
        for note in item["analysis"]:
            lines.append(f"- {note}")
        lines.append("")

    return "\n".join(lines).strip()
