"""Cornell/oteLedge note synthesis pipeline orchestrating OCR→verification→VLM stages."""
from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from modules.llm_utils import call_llm
    from modules.services.gpu_utils import prepare_llm_inference
    from modules.services.pipeline_trace import PipelineTrace
    from modules.services.prompt_manifest import (
        final_prompt_template,
        manifest_dict,
        manifest_hash,
        manifest_id,
        manifest_version,
        verification_prompt_template,
    )
except ModuleNotFoundError:  # pragma: no cover - fallback for unit tests
    from source.backend.modules.llm_utils import call_llm
    from source.backend.modules.services.gpu_utils import prepare_llm_inference
    from source.backend.modules.services.pipeline_trace import PipelineTrace
    from source.backend.modules.services.prompt_manifest import (
        final_prompt_template,
        manifest_dict,
        manifest_hash,
        manifest_id,
        manifest_version,
        verification_prompt_template,
    )
    from source.backend.utils.markdown_cleaner import clean_markdown
else:
    from modules.utils.markdown_cleaner import clean_markdown


class CornellNotePipeline:
    """Run PaddleOCR-VL → Qwen verification → Qwen VLM synthesis."""

    def __init__(self, llm_config: Dict[str, Any]) -> None:
        self._llm_config = llm_config or {}

    def _load_image_b64(self, image_path: str) -> str:
        with open(image_path, "rb") as fp:
            return base64.b64encode(fp.read()).decode("utf-8")

    async def _run_verification(
        self,
        *,
        ocr_text: str,
        image_b64: str,
        context: str,
        structured_hint: str,
        trace: PipelineTrace,
    ) -> Dict[str, Any]:
        trace.mark_started("verification", detail="qwen3-vl:4b double-pass")
        prompt = verification_prompt_template().format(
            ocr_text=ocr_text or "(未辨識到文字)",
            image_hint=structured_hint or "(沒有版面摘要)",
            context=context or "(無其他上下文)",
        )
        try:
            prepare_llm_inference("cornell:verification")
            response = await call_llm(
                prompt=prompt,
                model=self._llm_config.get("image_model", "qwen3-vl:4b"),
                image=image_b64,
                language="zh-TW",
                use_cache=False,
            )
            payload = self._ensure_json_dict(response, stage="verification")
        except Exception as exc:
            trace.mark_failed("verification", error=str(exc))
            raise

        trace.mark_completed(
            "verification",
            detail=f"verified_entries={len(payload.get('verified_text') or [])}",
        )
        return payload

    async def _run_synthesis(
        self,
        *,
        title: str,
        subject: str,
        date_str: str,
        context: str,
        image_findings: str,
        verification: Dict[str, Any],
        image_b64: str,
        trace: PipelineTrace,
    ) -> Dict[str, Any]:
        trace.mark_started("synthesis", detail="qwen3-vl:4b final note")

        prompt = final_prompt_template().format(
            image_findings=image_findings or "(無圖片摘要)",
            verified_text=json.dumps(verification.get("verified_text") or [], ensure_ascii=False),
            missing_items=json.dumps(verification.get("missing_items") or [], ensure_ascii=False),
            context=context or "(無補充上下文)",
            subject=subject or "未設定",
            date=date_str,
            title=title,
        )
        try:
            prepare_llm_inference("cornell:synthesis")
            response = await call_llm(
                prompt=prompt,
                model=self._llm_config.get("final_model", "qwen3-vl:4b"),
                image=image_b64,
                language="zh-TW",
                use_cache=False,
            )
            payload = self._ensure_json_dict(response, stage="synthesis")
        except Exception as exc:
            trace.mark_failed("synthesis", error=str(exc))
            raise

        trace.mark_completed(
            "synthesis",
            detail=f"cue={len(payload.get('cue') or [])},notes={len(payload.get('notes') or [])}",
        )
        return payload

    async def run(
        self,
        *,
        image_path: str,
        ocr_text: str,
        structured_hint: str,
        context: str,
        image_summary: str,
        suggested_title: Optional[str] = None,
        subject_hint: Optional[str] = None,
        pipeline_trace: PipelineTrace,
    ) -> Dict[str, Any]:
        """Run verification and synthesis, returning markdown + metadata."""
        image_b64 = self._load_image_b64(image_path)
        verification = await self._run_verification(
            ocr_text=ocr_text,
            image_b64=image_b64,
            context=context,
            structured_hint=structured_hint,
            trace=pipeline_trace,
        )

        today = datetime.now().strftime("%Y/%m/%d")
        synthesis = await self._run_synthesis(
            title=suggested_title or "未命名講義",
            subject=subject_hint or "待確認科目",
            date_str=today,
            context=context,
            image_findings=image_summary,
            verification=verification,
            image_b64=image_b64,
            trace=pipeline_trace,
        )

        markdown = self._build_markdown(synthesis)
        pipeline_trace.assert_sequence()
        return {
            "markdown": markdown,
            "verification": verification,
            "synthesis": synthesis,
            "manifest": manifest_dict(),
            "manifest_id": manifest_id(),
            "manifest_version": manifest_version(),
            "manifest_hash": manifest_hash(),
            "pipeline_trace": pipeline_trace.to_dict(),
        }

    def _ensure_json_dict(self, response: Any, *, stage: str) -> Dict[str, Any]:
        if isinstance(response, dict):
            candidate = response.get("message") or response.get("data") or response.get("reply") or response
            if isinstance(candidate, dict):
                return candidate
            if isinstance(candidate, str):
                response = candidate
        if isinstance(response, str):
            response = response.strip()
            try:
                return json.loads(response)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"[CornellPipeline] {stage} stage did not return valid JSON: {response[:200]}") from exc
        raise RuntimeError(f"[CornellPipeline] {stage} stage produced unsupported payload type: {type(response).__name__}")

    def _build_markdown(self, payload: Dict[str, Any]) -> str:
        title = payload.get("title") or "未命名講義"
        date_str = payload.get("date") or datetime.now().strftime("%Y/%m/%d")
        subject = payload.get("subject") or "待確認科目"

        lines: List[str] = [
            f"# 🗂 {title}",
            f"📅 日期：{date_str}  ",
            f"🎓 科目：{subject}",
            "",
            "---",
            "",
            "## 🧭 一、章節概要（Cornell：Cue）",
        ]

        cues = payload.get("cue") or []
        if not isinstance(cues, list) or not cues:
            cues = ["資訊不足，待補"]
        for idx, item in enumerate(cues, 1):
            item_str = str(item).strip()
            if not item_str:
                item_str = "資訊不足，待補"
            lines.append(f"{idx}. {item_str}")

        lines.extend(["", "---", "", "## 📖 二、中文解釋與理解（Cornell：Notes）"])
        notes = payload.get("notes") or []
        if not isinstance(notes, list) or not notes:
            notes = ["資訊不足，待補"]
        for note in notes:
            note_str = str(note).strip() or "資訊不足，待補"
            lines.append(f"- {note_str}")

        lines.extend(["", "---", "", "## 💡 三、補充知識（oteLedge：Extend）"])
        extend = payload.get("extend") or []
        if not isinstance(extend, list) or not extend:
            extend = ["資訊不足，待補"]
        for item in extend:
            item_str = str(item).strip() or "資訊不足，待補"
            lines.append(f"- {item_str}")

        formulas = payload.get("formulas") or []
        if isinstance(formulas, list):
            formulas = [str(f).strip() for f in formulas if str(f).strip()]
        else:
            formulas = []

        if formulas:
            lines.extend(["", "---", "", "## 🔢 四、數學公式", ""])
            for formula in formulas:
                lines.append("$$")
                lines.append(formula)
                lines.append("$$")
                lines.append("")

        code_blocks = payload.get("code_blocks") or []
        formatted_blocks: List[str] = []
        if isinstance(code_blocks, list):
            for block in code_blocks:
                if not isinstance(block, dict):
                    continue
                language = str(block.get("language") or "text").strip()
                code = str(block.get("code") or "").rstrip()
                if not code:
                    continue
                title = str(block.get("title") or "").strip()
                if title:
                    formatted_blocks.append(f"**{title}**")
                formatted_blocks.append(f"```{language}")
                formatted_blocks.append(code)
                formatted_blocks.append("```")
                formatted_blocks.append("")

        if formatted_blocks:
            lines.extend(["", "---", "", "## 💻 五、程式碼與技術重點", ""])
            lines.extend(formatted_blocks)

        markdown = "\n".join(lines).rstrip() + "\n"
        return clean_markdown(markdown)


__all__ = ["CornellNotePipeline"]
