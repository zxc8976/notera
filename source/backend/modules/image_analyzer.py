"""
共享的圖片分析模組
用於影片截圖和獨立圖片的分析處理
"""
import asyncio
import os
import logging
import base64
import tempfile
import shutil
import traceback
from typing import List, Optional, cast


from PIL import Image

from modules.core.structured_ocr import (
    StructuredBlock,
    StructuredOcrResult,
    get_structured_ocr_processor,
)
from modules.llm_utils import call_llm
from modules.llm_prompts_optimized import get_optimized_image_note_prompt
from modules.services.gpu_utils import prepare_llm_inference

from modules.file_handlers import file_processor

logger = logging.getLogger(__name__)


class ImageAnalyzer:
    """圖片分析器 - 統一處理圖片分析邏輯"""

    def __init__(self, config, llm_config, device="gpu"):
        self.config = config or {}
        self.llm_config = llm_config or {}
        self.device = device
        self._ocr = None
        self._structured_ocr = None
        ocr_cfg = self.config.get("ocr") or {}
        structured_cfg = ocr_cfg.get("structured_ocr") or {}
        self._ocr_enabled = bool(ocr_cfg.get("enabled", True))
        self._structured_enabled = self._ocr_enabled and bool(structured_cfg.get("enabled", True))
        if not self._structured_enabled:
            logger.info("[ImageAnalyzer] 結構化 OCR 已停用 (ocr.structured_ocr.enabled=false 或 OCR 關閉)")

    @property
    def ocr(self):
        """延遲初始化OCR"""
        if not self._ocr_enabled:
            logger.info("[ImageAnalyzer] OCR 全域停用，跳過初始化")
            return None
        if self._ocr is None:
            self._ocr = self._init_ocr()
        return self._ocr

    def _init_ocr(self):
        """初始化OCR引擎 - 使用统一的OCR管理器"""
        try:
            from modules.core.ocr_utils import ocr_manager
            ocr = ocr_manager.get_ocr(self.config, self.device)
            logger.info(f"OCR管理器初始化完成 (设备: {self.device})")
            return ocr
        except Exception as e:
            logger.error(f"OCR初始化失败: {e}")
            return None

    @property
    def structured_ocr(self):
        """延遲初始化結構化OCR處理器"""
        if not self._ocr_enabled:
            return None
        if self._structured_ocr is None:
            try:
                self._structured_ocr = get_structured_ocr_processor(
                    self.config, self.device
                )
                logger.info("[ImageAnalyzer] 結構化OCR處理器就緒")
            except Exception as exc:
                logger.warning(f"[ImageAnalyzer] 無法初始化結構化OCR: {exc}")
                self._structured_ocr = None
        return self._structured_ocr

    async def analyze_image(self, image_path, context="", skip_ocr=False, language="zh-TW", include_japanese=True):
        """
        分析圖片並生成描述

        Args:
            image_path: 圖片路徑
            context: 額外的上下文信息（如ASR文字）
            skip_ocr: 是否跳過OCR，直接使用多模態模型
            language: 輸出語言

        Returns:
            dict: 包含分析結果的字典
        """
        # 🔴 強制日誌輸出
        print(f"🔴 [ImageAnalyzer] ===== 開始分析圖片 ===== skip_ocr={skip_ocr}")
        logger.warning(f"🔴 [ImageAnalyzer] ===== 開始分析圖片 ===== skip_ocr={skip_ocr}")
        logger.info(f"[ImageAnalyzer] 圖片路徑: {image_path}")
        logger.info(f"[ImageAnalyzer] 語言: {language}, 包含日文: {include_japanese}")

        structured_result: Optional[StructuredOcrResult] = None
        structured_summary = ""

        try:

            # 檢查圖片是否存在
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"圖片不存在: {image_path}")

            # 1. 處理HEIC格式
            logger.info(f"[ImageAnalyzer] 步驟1: 檢查 HEIC 格式")
            processed_image_path = self._handle_heic_format(image_path)
            logger.info(f"[ImageAnalyzer] 處理後圖片路徑: {processed_image_path}")

            # 2. 結構化 OCR + 版面分析 (若停用則回退到精簡 OCR)
            structured_result = self._acquire_structured_result(processed_image_path, skip_ocr)

            ocr_text = (structured_result.raw_text or "").strip() if structured_result else ""
            structured_summary = (
                structured_result.to_prompt_sections() if structured_result else ""
            )

            logger.info(
                "[ImageAnalyzer] 結構化摘要長度: %d, 公式數: %d",
                len(structured_summary or ""),
                len(structured_result.formulas if structured_result else []),
            )
            if ocr_text:
                preview = ocr_text[:120].replace("\n", " ")
                logger.info(
                    "[ImageAnalyzer] ✅ OCR 抽取完成: %d 字, 預覽: %s",
                    len(ocr_text),
                    preview,
                )
            else:
                if skip_ocr:
                    logger.warning(
                        "[ImageAnalyzer] ⚠️ skip_ocr=True 但 OCR 無內容，將依賴 VLM 補述"
                    )
                    print("ℹ️ [ImageAnalyzer] OCR 無結果，僅依賴 VLM 輔助理解")
                else:
                    logger.warning("[ImageAnalyzer] ⚠️ OCR 未取得文字，後續依賴 VLM")

            combined_ocr_context = self._compose_ocr_context(
                ocr_text, structured_summary
            )

            # 3. 準備多模態分析
            logger.info(f"[ImageAnalyzer] 步驟3: 編碼圖片為 Base64")
            image_b64 = self._encode_image_to_base64(processed_image_path)
            logger.info(f"[ImageAnalyzer] Base64 長度: {len(image_b64) if image_b64 else 0}")

            # 4. 生成提示詞 - 使用新的強化版提示詞
            logger.info(f"[ImageAnalyzer] 步驟4: 生成提示詞")
            enhanced_prompt = self._get_ocr_prompt(
                context, combined_ocr_context, language, include_japanese
            )
            logger.info(
                "[ImageAnalyzer] 📝 使用強化版提示詞,長度: %d (combined_ocr_len=%d)",
                len(enhanced_prompt),
                len(combined_ocr_context or ""),
            )
            logger.info(f"[ImageAnalyzer] 提示詞前200字: {enhanced_prompt[:200]}")

            # 5. 調用LLM進行分析（多輪重試，避免輸出過短）
            logger.info(f"[ImageAnalyzer] 步驟5: 調用 LLM 進行分析")
            summary_text = ""
            llm_ok = False
            llm_failure_reason: Optional[str] = None
            min_chars = max(60, int(self.llm_config.get("image_llm_min_chars", 140)))
            if skip_ocr or not self._ocr_enabled:
                # 純 VLM 模式下允許較短輸出，避免因篇幅不足直接降級
                min_chars = min(min_chars, 60)
            attempt_limit = max(1, int(self.llm_config.get("image_llm_attempts", 3)))
            llm_extra = {
                "temperature": self.llm_config.get("temperature"),
                "top_p": self.llm_config.get("top_p"),
                "top_k": self.llm_config.get("top_k"),
                "max_tokens": self.llm_config.get("max_tokens") or 2048,
            }
            prompt_variants = [
                enhanced_prompt,
                enhanced_prompt
                + "\n\n請輸出完整的教學內容，至少 6 段落、400 字以上，逐條列出日文原文、中文說明與補充，必要時補充程式碼與實務建議。",
            ]

            for variant_idx, prompt_variant in enumerate(prompt_variants):
                for attempt in range(attempt_limit):
                    try:
                        logger.info(
                            "[ImageAnalyzer] 調用 LLM variant=%s attempt=%s",
                            variant_idx,
                            attempt + 1,
                        )
                        prepare_llm_inference("image-analyzer:scene-analysis")
                        llm_response = await call_llm(
                            prompt=prompt_variant,
                            model=self.llm_config.get('image_model', 'qwen3-vl:4b'),
                            image=image_b64,
                            use_cache=False,
                            language=language,
                            extra=llm_extra,
                        )
                        summary_text = self._extract_llm_text(llm_response)
                        summary_len = len(summary_text or "")
                        logger.info(
                            "[ImageAnalyzer] summary variant=%s attempt=%s len=%s preview=%s",
                            variant_idx,
                            attempt + 1,
                            summary_len,
                            (summary_text or "")[:120].replace("\n", " "),
                        )
                        accepts_short = skip_ocr or not self._ocr_enabled
                        if summary_text and not summary_text.startswith("🚨"):
                            if summary_len >= min_chars:
                                llm_ok = True
                                break
                            if accepts_short:
                                logger.info(
                                    "[ImageAnalyzer] ✅ 接受短字數摘要 (len=%s) 因 OCR=OFF/skip_ocr",
                                    summary_len,
                                )
                                llm_ok = True
                                break
                        llm_failure_reason = f"LLM 輸出過短（{summary_len}字）"
                        logger.warning(
                            "[ImageAnalyzer] ⚠️ VLM 輸出過短 (len=%s) variant=%s attempt=%s",
                            summary_len,
                            variant_idx,
                            attempt + 1,
                        )
                    except Exception as exc:
                        llm_failure_reason = f"LLM 執行例外: {exc}"
                        logger.error(f"[ImageAnalyzer] ❌ LLM分析失敗: {exc}")
                        logger.error(traceback.format_exc())
                    await asyncio.sleep(min(4.0, 1.5 * (attempt + 1)))
                if llm_ok:
                    break

            # 🚨 新邏輯: LLM 失敗時不要切換到 OCR,而是返回明確錯誤
            if not llm_ok:
                fallback_reason = llm_failure_reason or "LLM 未回傳有效內容"
                logger.warning(f"[ImageAnalyzer] ⚠️ 啟用 OCR 降級: {fallback_reason}")
                fallback_note = self._build_llm_fallback_note(
                    ocr_text=ocr_text or (structured_result.raw_text if structured_result else ""),
                    structured_summary=structured_summary,
                    language=language,
                    reason=fallback_reason,
                )
                visual_focus = await self._generate_visual_focus(image_b64, structured_result, language)
                if visual_focus:
                    fallback_note = self._merge_visual_focus(fallback_note, visual_focus, language)

                final_image_path = processed_image_path if (processed_image_path != image_path) else image_path
                final_image_fs_path = final_image_path
                if final_image_path.startswith('/data/images/'):
                    final_image_path = final_image_path.replace('/data/images/', '/images/')

                needs_restart = "執行例外" in (fallback_reason or "") or "未回傳" in (fallback_reason or "")
                return {
                    'success': True,
                    'analysis': fallback_note,
                    'ocr_text': ocr_text or (structured_result.raw_text if structured_result else ""),
                    'structured_ocr': structured_result.to_dict() if structured_result else {},
                    'structured_summary': structured_summary,
                    'visual_focus': visual_focus,
                    'image_path': final_image_path,
                    'image_path_web': final_image_path,
                    'image_path_fs': final_image_fs_path,
                    'degraded': True,
                    'llm_error': fallback_reason,
                    'needs_ollama_restart': needs_restart,
                    'ocr_disabled': not self._ocr_enabled,
                }

            # 5.5 補充視覺重點 (箭頭、框線、顏色)
            visual_focus = await self._generate_visual_focus(
                image_b64, structured_result, language
            )
            if visual_focus:
                summary_text = self._merge_visual_focus(summary_text, visual_focus, language)

            # 6. LLM 分析成功,保留轉換後的圖片
            # 如果是轉換後的圖片,返回轉換後的路徑供前端使用
            final_image_path = processed_image_path if (processed_image_path != image_path) else image_path
            final_image_fs_path = final_image_path
            
            # 🔧 修正路徑格式: /data/images/ -> /images/
            if final_image_path.startswith('/data/images/'):
                final_image_path = final_image_path.replace('/data/images/', '/images/')
                logger.info(f"[ImageAnalyzer] 路徑格式化: {final_image_path}")
            
            logger.info(f"[ImageAnalyzer] 返回圖片路徑: {final_image_path}")

            return {
                'success': True,
                'analysis': summary_text,
                'ocr_text': ocr_text,
                'structured_ocr': structured_result.to_dict() if structured_result else {},
                'structured_summary': structured_summary,
                'visual_focus': visual_focus,
                'image_path': final_image_path,  # 返回轉換後的路徑
                'image_path_web': final_image_path,
                'image_path_fs': final_image_fs_path,
                'ocr_disabled': not self._ocr_enabled,
            }

        except Exception as e:
            logger.error(f"[ImageAnalyzer] 圖片分析失敗: {e}")
            logger.error(f"[ImageAnalyzer] 詳細錯誤: {traceback.format_exc()}")
            
            # 🔧 修正路徑格式
            exception_image_path = image_path
            if exception_image_path.startswith('/data/images/'):
                exception_image_path = exception_image_path.replace('/data/images/', '/images/')
            
            return {
                'success': False,
                'error': str(e),
                'analysis': f"圖片分析失敗: {str(e)}",
                'ocr_text': "",
                'structured_ocr': structured_result.to_dict() if structured_result else {},
                'structured_summary': structured_summary,
                'image_path': exception_image_path,
                'image_path_web': exception_image_path,
                'image_path_fs': image_path,
                'ocr_disabled': not self._ocr_enabled,
            }

    def _handle_heic_format(self, image_path):
        """處理HEIC格式圖片 - 檢測真實格式而非僅依賴擴展名"""
        # 先嘗試共用 FileProcessor 的邏輯，避免維護兩套流程
        try:
            processed_path = file_processor.handle_heic_format(image_path)
            if processed_path and processed_path != image_path and os.path.exists(processed_path):
                return processed_path
        except Exception as e:
            logger.debug(f"[ImageAnalyzer] 使用 FileProcessor 處理 HEIC 失敗，改用備援: {e}")

        # 檢測真實文件格式(通過文件頭magic bytes)
        is_heic = False
        if image_path.lower().endswith(('.heic', '.heif')):
            is_heic = True
        else:
            # 檢查文件頭,即使擴展名不是 .heic
            try:
                with open(image_path, 'rb') as f:
                    header = f.read(12)
                    # HEIC/HEIF 文件特徵: "ftyp" + ("heic", "heix", "hevc", "hevx", "mif1")
                    if b'ftyp' in header:
                        if any(brand in header for brand in [b'heic', b'heix', b'hevc', b'hevx', b'mif1']):
                            logger.warning(f"[ImageAnalyzer] ⚠️ 檢測到 HEIC 文件偽裝成其他格式: {image_path}")
                            is_heic = True
            except Exception as e:
                logger.debug(f"[ImageAnalyzer] 無法讀取文件頭: {e}")

        if not is_heic:
            return image_path

        try:
            import pillow_heif  # type: ignore

            pillow_heif.register_heif_opener()

            with Image.open(image_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                # 🔧 優化: 直接在原位置生成 JPG,避免雙倍容量
                # 生成新檔名: xxx.HEIC -> xxx_converted.jpg (與原文件同目錄)
                dir_name = os.path.dirname(image_path)
                base_name = os.path.splitext(os.path.basename(image_path))[0]
                output_path = os.path.join(dir_name, f"{base_name}_converted.jpg")

                # 保存為 JPG (質量95,平衡品質與大小)
                img.save(output_path, 'JPEG', quality=90, optimize=True)
                
                # 📦 節省空間: 刪除原始 HEIC 文件
                try:
                    original_size = os.path.getsize(image_path) / 1024 / 1024  # MB
                    converted_size = os.path.getsize(output_path) / 1024 / 1024  # MB
                    
                    os.remove(image_path)
                    logger.info(f"[ImageAnalyzer] ✅ HEIC轉換成功並刪除原文件")
                    logger.info(f"[ImageAnalyzer] 📊 空間節省: {original_size:.2f}MB -> {converted_size:.2f}MB (減少 {original_size - converted_size:.2f}MB)")
                except Exception as e:
                    logger.warning(f"[ImageAnalyzer] ⚠️ 無法刪除原始 HEIC 文件: {e}")
                
                return output_path

        except ImportError:
            logger.warning("[ImageAnalyzer] pillow-heif未安裝，無法處理HEIC格式")
        except Exception as e:
            logger.error(f"[ImageAnalyzer] HEIC轉換失敗: {e}")

        return image_path

    def _extract_text_from_image(self, image_path):
        """從圖片中提取文字,包含失敗檢測和去重"""
        if not self._ocr_enabled:
            logger.debug("[ImageAnalyzer] OCR 已停用，跳過文字提取")
            return ""
        if not self.ocr:
            logger.error("[ImageAnalyzer] ❌ OCR 引擎未初始化")
            return ""

        try:
            logger.info(f"[ImageAnalyzer] 開始 OCR 識別: {image_path}")
            structured = self.ocr.extract_text(image_path)
            text_lines = structured.get("lines") if isinstance(structured, dict) else None

            if not text_lines:
                logger.warning(f"[ImageAnalyzer] ⚠️ OCR 未識別到任何文字")
                return ""

            text_blocks = []
            seen_lines = set()
            seen_normalized = set()
            low_confidence_count = 0
            duplicate_count = 0

            for payload in text_lines:
                if not isinstance(payload, dict):
                    continue

                text = (payload.get("text") or "").strip()
                confidence = float(payload.get("confidence", 0.0))

                if not text:
                    continue
                if confidence <= 0.4:
                    low_confidence_count += 1
                    continue
                if len(text) <= 2:
                    continue

                normalized = " ".join(text.split()).lower()
                if text in seen_lines or normalized in seen_normalized:
                    duplicate_count += 1
                    if duplicate_count <= 5:
                        logger.info(
                            f"[OCR] 🔄 檢測到重複行(#{duplicate_count}),已跳過: {text[:50]}..."
                        )
                    continue

                seen_lines.add(text)
                seen_normalized.add(normalized)
                text_blocks.append(text)

            ocr_text = "\n".join(text_blocks)

            total_lines = len(text_lines)

            # 🔧 新增: 智能截斷OCR文字,避免超出context限制
            MAX_OCR_LENGTH = 1500  # 保留前1500字
            if len(ocr_text) > MAX_OCR_LENGTH:
                original_length = len(ocr_text)
                ocr_text = ocr_text[:MAX_OCR_LENGTH]
                # 在截斷點找最近的換行符,避免截斷到句子中間
                last_newline = ocr_text.rfind('\n')
                if last_newline > MAX_OCR_LENGTH * 0.8:  # 至少保留80%
                    ocr_text = ocr_text[:last_newline]
                ocr_text += f"\n\n...(原文共{original_length}字,為避免超出處理限制,已截取前{len(ocr_text)}字)"
                logger.warning(f"[OCR] ⚠️ 文字過長({original_length}字),已截斷至{len(ocr_text)}字")
            
            # OCR 品質檢查
            if duplicate_count > 0:
                logger.info(f"[ImageAnalyzer] 🔄 OCR 去重: 移除了 {duplicate_count} 行重複文字")
            
            if len(ocr_text) < 50:
                logger.warning(f"[ImageAnalyzer] ⚠️ OCR 識別文字過少({len(ocr_text)}字),圖片可能模糊或無文字")
            elif low_confidence_count > len(text_blocks):
                logger.warning(f"[ImageAnalyzer] ⚠️ OCR 低信心度文字過多({low_confidence_count}/{total_lines}),圖片品質可能不佳")
            else:
                logger.info(f"[ImageAnalyzer] ✅ OCR 識別成功,共 {len(text_blocks)} 行文字 (原始: {total_lines} 行)")
            
            return ocr_text

        except Exception as e:
            logger.error(f"[ImageAnalyzer] ❌ OCR提取失敗: {e}")
            return ""

    def _run_structured_ocr(self, image_path: str) -> StructuredOcrResult:
        # pragma: no cover - 依賴外部模型，測試環境通常不啟用
        """執行結構化 OCR，失敗時自動回退到簡易 OCR"""
        processor = self.structured_ocr
        if processor:
            try:
                result = processor.analyze(image_path)
                logger.info(
                    "[ImageAnalyzer] 結構化OCR完成: layout=%s, raw_len=%d, formulas=%d",
                    result.used_layout,
                    len(result.raw_text or ""),
                    len(result.formulas or []),
                )
                return result
            except Exception as exc:
                logger.warning(
                    "[ImageAnalyzer] 結構化OCR失敗，改用簡易OCR: %s", exc
                )
        else:
            logger.debug("[ImageAnalyzer] 結構化OCR未啟用或不可用，使用純 OCR")

        fallback_text = self._extract_text_from_image(image_path)
        fallback = StructuredOcrResult(raw_text=fallback_text, used_layout=False)
        if fallback_text:
            fallback.blocks.append(
                StructuredBlock(
                    block_type="paragraph",
                    text=fallback_text,
                    confidence=0.85,
                )
            )
        fallback.errors.append("structured_ocr_unavailable")
        return fallback

    def _build_plain_structured_result(self, text: str, *, reason: str) -> StructuredOcrResult:
        """將純 OCR 文字包裝成 StructuredOcrResult 供下游使用。"""
        result = StructuredOcrResult(raw_text=text or "", used_layout=False)
        if text:
            for line in (text.splitlines() or [""]):
                stripped = line.strip()
                if not stripped:
                    continue
                result.blocks.append(
                    StructuredBlock(
                        block_type="paragraph",
                        text=stripped,
                        confidence=0.85,
                    )
                )
        result.errors.append(reason)
        return result

    def _acquire_structured_result(
        self, image_path: str, skip_ocr: bool
    ) -> Optional[StructuredOcrResult]:
        """依據設定取得結構化結果，若停用則回退到精簡 OCR。"""
        if skip_ocr:
            logger.info("[ImageAnalyzer] skip_ocr=True，跳過 OCR 流程")
            return None
        if not self._ocr_enabled:
            logger.info("[ImageAnalyzer] OCR 全域停用，僅依賴 VLM")
            return None

        if self._structured_enabled:
            logger.info(
                "[ImageAnalyzer] 步驟2: 結構化 OCR (skip_ocr=%s)",
                skip_ocr,
            )
            print(f"🟦 [ImageAnalyzer] 啟動結構化OCR流程: skip_ocr={skip_ocr}")
            return self._run_structured_ocr(image_path)

        logger.info(
            "[ImageAnalyzer] 結構化 OCR 被停用，使用精簡 OCR 流程 (skip_ocr=%s)",
            skip_ocr,
        )
        plain_text = self._extract_text_from_image(image_path)
        if not plain_text:
            logger.warning(
                "[ImageAnalyzer] ⚠️ 精簡 OCR 流程未擷取到文字 (structured_ocr.disabled)"
            )
        return self._build_plain_structured_result(
            plain_text,
            reason="structured_ocr_disabled",
        )

    def _compose_ocr_context(self, raw_text: str, structured_summary: str) -> str:
        """組合結構化重點與原始 OCR 文字"""
        segments: List[str] = []
        if structured_summary:
            segments.append("【版面重點摘要】\n" + structured_summary.strip())
        if raw_text:
            segments.append("【OCR全文】\n" + raw_text.strip())
        combined = "\n\n".join(segment for segment in segments if segment)
        logger.debug(
            "[ImageAnalyzer] 組合OCR內容: summary_len=%d, raw_len=%d, combined_len=%d",
            len(structured_summary or ""),
            len(raw_text or ""),
            len(combined or ""),
        )
        return combined

    @staticmethod
    def _resolve_language_mode(language: str, include_japanese: bool) -> str:
        lang = (language or "").lower()
        if lang.startswith("ja") and not include_japanese:
            return "ja-only"
        return "bilingual" if include_japanese else "target-only"

    def _get_ocr_prompt(self, context: str, ocr_text: str, language: str, include_japanese: bool) -> str:
        language_mode = self._resolve_language_mode(language, include_japanese)
        return get_optimized_image_note_prompt(
            ocr_text,
            language_code=language,
            context=context or "",
            has_ocr=bool((ocr_text or "").strip()),
            language_mode=language_mode,
        )

    def _build_llm_fallback_note(

        self,
        *,
        ocr_text: str,
        structured_summary: str,
        language: str,
        reason: str,
    ) -> str:
        """當 LLM 無法產生內容時，根據 OCR/版面資訊建構緊急降級筆記。"""
        locales = {
            "zh-TW": {
                "header": "## ⚠️ 降級筆記（OCR 摘要）",
                "reason": "LLM 目前無法提供內容，系統已改用 OCR 與版面摘要。",
                "ocr_header": "### 📝 OCR 文字節錄",
                "summary_header": "### 🧩 版面結構重點",
            },
            "zh-CN": {
                "header": "## ⚠️ 降级笔记（OCR 摘要）",
                "reason": "LLM 暂时无法提供内容，系统改用 OCR 与版面摘要。",
                "ocr_header": "### 📝 OCR 文本节录",
                "summary_header": "### 🧩 版面结构重点",
            },
            "en": {
                "header": "## ⚠️ Degraded Note (OCR Snapshot)",
                "reason": "The VLM could not respond. Showing OCR text and layout summary instead.",
                "ocr_header": "### 📝 OCR Excerpt",
                "summary_header": "### 🧩 Layout Highlights",
            },
        }
        locale = locales.get(language, locales["zh-TW"])
        reason_line = f"- {reason}" if reason else ""

        def _excerpt(text: str) -> List[str]:
            lines = []
            for line in (text or "").splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                lines.append(f"- {stripped}")
                if len(lines) >= 8:
                    break
            if not lines:
                lines.append("- （暫無可用 OCR 內容）")
            return lines

        ocr_lines = _excerpt(ocr_text)
        summary_lines = _excerpt(structured_summary)

        parts = [
            locale["header"],
            "",
            locale["reason"],
        ]
        if reason_line:
            parts.append(reason_line)
        parts.extend(
            [
                "",
                locale["ocr_header"],
                "\n".join(ocr_lines),
                "",
                locale["summary_header"],
                "\n".join(summary_lines),
            ]
        )
        return "\n".join(parts).strip()

    def _extract_llm_text(self, response) -> str:
        """將 LLM 回應統一轉換成純文字"""
        if isinstance(response, str):
            return response.strip()
        if isinstance(response, dict):
            message = response.get("message") or response.get("data") or {}
            if isinstance(message, dict):
                content = message.get("content") or message.get("text")
                if isinstance(content, str):
                    return content.strip()
            reply = response.get("reply") or response.get("response")
            if isinstance(reply, str):
                return reply.strip()
        return ""

    def _should_generate_visual_focus(self, structured_result: Optional[StructuredOcrResult]) -> bool:
        if not structured_result:
            return False
        if structured_result.formulas:
            return True
        if structured_result.used_layout and len(structured_result.blocks) >= 2:
            return True
        if len(structured_result.raw_text or "") < 120:
            return True
        return False

    def _build_visual_focus_prompt(
        self, structured_result: StructuredOcrResult, language: str
    ) -> str:
        templates = {
            "zh-TW": """你是一位專業的教學助理。請忽略已透過 OCR 取得的文字，專注描述圖片中的「視覺或圖解資訊」。

任務：
1. 確認箭頭、框線、顏色標記各代表的狀態或流程 (例如 S_off → a_off → ...)
2. 解釋圖片中的圖表、流程圖、重點框選或手寫註記
3. 說明這些圖像與講義主題的關聯與教學價值

輸出格式：
- 視覺重點1：...
- 視覺重點2：...
- 教學提醒：...

請使用精簡條列，但要寫出具體資訊。""",
            "zh-CN": """你是一名专业教学助理。忽略 OCR 已得到的文字，专注描述图片中的视觉或图解信息。

任务：
1. 说明箭头、边框、颜色标记的含义
2. 解读图片中的流程图、重点框选、手写提示
3. 描述这些图像与课程主题之间的联系

输出格式：
- 视觉重点1：...
- 视觉重点2：...
- 教学提醒：...
""",
            "ja": """あなたは教育アシスタントです。OCRで取得したテキストではなく、画像上の「視覚的な情報」に焦点を当てて説明してください。

タスク:
1. 矢印・枠線・色ハイライトが示す状態や遷移を説明
2. 図表・フローチャート・手書きメモの意味を解説
3. これらが講義テーマにどう貢献するかを述べる

出力形式:
- ビジュアル重点1: ...
- ビジュアル重点2: ...
- 学習上の注意: ...
""",
            "en": """You are an instructional assistant. Ignore raw OCR text and focus on the visual cues inside the image.

Tasks:
1. Explain arrows, boxes, color highlights and what they denote
2. Interpret diagrams, flow charts, annotations or hand-written notes
3. Connect these visuals back to the lecture topic and learning value

Output format:
- Visual highlight #1: ...
- Visual highlight #2: ...
- Teaching tip: ...
""",
        }
        prompt = templates.get(language, templates["zh-TW"])
        formula_lines = ""
        if structured_result.formulas:
            formula_lines = "\n".join(
                f"- {block.compact_text()}" for block in structured_result.formulas[:6]
            )
        summary = structured_result.to_prompt_sections(max_chars=1000)
        context_hint = f"""
【OCR 文字概要】
{summary or '(無 OCR 概要)'}

【疑似公式 / 程式段落】
{formula_lines or '(未偵測到公式)'}

請勿重複上述文本內容，只需補充圖片中的視覺重點。"""
        return f"{prompt}\n\n{context_hint}".strip()

    def _merge_visual_focus(self, summary_text: str, visual_focus: str, language: str) -> str:
        if not visual_focus:
            return summary_text
        headers = {
            "zh-TW": "### 🔎 圖像補充重點",
            "zh-CN": "### 🔎 图像补充要点",
            "ja": "### 🔎 画像上の補足ポイント",
            "en": "### 🔎 Visual Highlights",
        }
        header = headers.get(language, headers["zh-TW"])
        if header in summary_text:
            return summary_text
        combined = summary_text.rstrip() + "\n\n---\n" + header + "\n" + visual_focus.strip()
        return combined

    async def _generate_visual_focus(
        self,
        image_b64: Optional[str],
        structured_result: Optional[StructuredOcrResult],
        language: str,
    ) -> str:
        if not image_b64:
            return ""
        if not structured_result:
            return ""
        if not self._should_generate_visual_focus(structured_result):
            return ""
        prompt = self._build_visual_focus_prompt(
            cast(StructuredOcrResult, structured_result),
            language,
        )

        if not prompt:
            return ""
        model_name = (
            self.llm_config.get("visual_focus_model")
            or self.llm_config.get("image_model", "qwen3-vl:4b")
        )
        try:
            prepare_llm_inference("image-analyzer:independent-image")
            response = await call_llm(
                prompt=prompt,
                model=model_name,
                image=image_b64,
                use_cache=False,
                language=language,
            )
            text = self._extract_llm_text(response)
            if text:
                logger.info(
                    "[ImageAnalyzer] 視覺補充生成成功: %d 字 (model=%s)",
                    len(text),
                    model_name,
                )
            return text
        except Exception as exc:
            logger.warning(f"[ImageAnalyzer] 視覺補充生成失敗: {exc}")
            return ""

    def _encode_image_to_base64(self, image_path):
        """將圖片編碼為base64"""
        try:
            with open(image_path, "rb") as img_f:
                return base64.b64encode(img_f.read()).decode()
        except Exception as e:
            logger.error(f"[ImageAnalyzer] 圖片編碼失敗: {e}")
            return None

    def _get_enhanced_multimodal_prompt(self, context, ocr_text, language, include_japanese):
        """生成增強的多模態分析提示詞 - 要求完整詳細的內容輸出"""
        if language.startswith("zh"):
            base_prompt = """你是專業的日語程式設計教育專家。請仔細分析這張圖片並生成**完整詳細**的雙語學習筆記。

� 分析要求：
1. 🔍 識別圖片中的**所有文字**（日文、中文、英文）
2. 📸 觀察**所有可見元素**（標題、說明、程式碼、圖表、練習題）
3. 💡 提供**詳細解釋**（不要使用"請參考圖片"等敷衍語句）
4. 📝 **完整列出**所有練習題和答案提示

✨ 輸出格式：

# 🇯🇵🇹🇼 雙語程式設計學習筆記

## 🎯 學習主題
[用1-2句話概括這張圖的教學重點]

## 🇯🇵 日文原文內容
```
[完整保留圖片中看到的所有日文文字，包括：
- 標題文字
- 說明段落
- 程式碼註解
- 練習題題目
- 任何其他日文內容]
```

## 🇹🇼 中文詳細解釋

### 📖 內容概覽
[詳細說明這張圖在講什麼，至少3-5行]

### 💻 程式碼分析
[如果有程式碼，請：
1. 列出完整程式碼
2. 逐行或逐段解釋
3. 說明執行結果]

### 📝 練習問題
[如果圖片中有練習題：
1. 完整列出每道題目
2. 提供解題思路
3. 給出參考答案]

### � 詳細解釋
[對圖片內容進行深入講解，包括：
- 為什麼要這樣設計
- 背後的原理是什麼
- 常見錯誤和注意事項]

## 📚 重要術語對照
| 日文 | 中文 | 詳細說明 |
|------|------|----------|
| [術語1] | [翻譯1] | [用途和範例] |
| [術語2] | [翻譯2] | [用途和範例] |

## � 學習重點
1. **重點1**：[詳細說明]
2. **重點2**：[詳細說明]
3. **重點3**：[詳細說明]

## � 實踐建議
1. [具體的練習方法]
2. [延伸學習建議]
3. [實際應用場景]

---

⚠️ **重要提醒：**
- ✅ 必須輸出**完整的日文原文**
- ✅ 必須提供**詳細的解釋**（不能只寫標題）
- ✅ 如果有練習題，必須**完整列出**
- ✅ 每個章節都要有**實質內容**（至少2-3行）
- ❌ 如果某區塊真的沒有內容，明確寫"本圖無此內容"而不是留空

請確保輸出內容完整、詳細、有教育價值！
"""
        else:
            base_prompt = f"""
You are a professional programming education expert. Please analyze the content in this image and generate high-quality learning notes.

Analysis requirements:
1. Directly observe image content, identify text, charts, code, etc.
2. Understand programming concepts and technical points
3. Provide accurate, clear explanations and practical examples
4. Avoid repetitive or meaningless content

Output format:
## Content Overview
(Brief concept explanation)

## Code Analysis
```java
// Actual code examples
```

## Learning Points
1. Point 1
2. Point 2
"""

        # OCR僅作為輔助信息，不作為主要依據
        if ocr_text and len(ocr_text.strip()) > 20:
            base_prompt += f"\n\n輔助信息（OCR識別，可能不準確）：\n{ocr_text[:200]}...\n"
        
        if context:
            base_prompt += f"\n額外上下文：{context}\n"
        
        return base_prompt

    def _get_multimodal_prompt(self, context="", language="zh-TW", include_japanese=True):
        """獲取多模態分析提示詞"""

        # 雙語分析提示詞（日本語 + 選擇語言）
        bilingual_prompts = {
            "zh-TW": """你是一位專業的日文程式設計教師和技術分析專家。請對這個圖片進行深度雙語分析。

**🎯 分析目標：**
創建一份詳細的雙語學習筆記（日文+繁體中文），幫助學習者理解程式設計概念。

**📋 分析要求：**
1. **🔍 視覺內容識別**：仔細觀察圖片中的所有元素
2. **🇯🇵 日文內容提取**：識別並保留所有日文文字
3. **💻 程式碼深度解析**：逐行分析程式碼邏輯
4. **🇹🇼 中文詳細解釋**：提供清晰的中文說明
5. **📚 術語對照建立**：建立日中技術術語對照表

**✨ 輸出格式：**

# 🇯🇵🇹🇼 雙語程式設計學習筆記

## 🎯 學習主題
[簡潔描述這張圖片的主要教學內容]

## 🇯🇵 日文原文內容（非程式碼，避免被高亮）
[請直接以一般段落列出原文，不要使用 ``` 代碼圍欄。若辨識到「目次/目錄/項目一覧/章/節」等目錄型區塊，請以條列清單輸出，避免誤判為程式碼。]

## 🇹🇼 繁體中文解釋
### 📖 內容概述
[詳細的中文解釋]

### 💻 程式碼分析
```java
// String vs StringBuilder 基礎範例
public class StringExample {
    public static void main(String[] args) {
        // String 範例 - 不可變
        String s1 = "Hello";
        String s2 = s1 + " World";
        System.out.println(s1.equals(s2.substring(0, 5))); // true
        
        // StringBuilder 範例 - 可變
        StringBuilder sb = new StringBuilder("Hello");
        sb.append(" World");
        System.out.println(sb.toString()); // Hello World
        
        // equals() 比較範例
        System.out.println(s1.equals("Hello")); // true
    }
}
```

**程式碼說明：**
- String 是不可變的，任何修改都會創建新物件
- StringBuilder 是可變的，適合大量字串操作
- equals() 方法比較字串內容而非引用

## 📚 重要術語對照
| 🇯🇵 日文 | 🇹🇼 中文 | 📝 說明 |
|----------|----------|---------|
| [術語1] | [翻譯1] | [解釋1] |
| [術語2] | [翻譯2] | [解釋2] |

## 💡 學習重點（結合此張講義內容量身整理）
- 針對本張圖的3~5個核心概念逐點說明，不要套版句。

## 🔧 實踐建議（對應本張圖）
- 設計2~3個操作題（含期望結果）讓學生立即練習。

**要求：內容要詳細、準確、具有教育價值。**""",

            "zh-CN": """你是一位专业的日文程序设计教师与技术分析专家。请对这张图片进行深入的双语分析。

**🎯 分析目标：**
产出详细的双语学习笔记（日文+简体中文），帮助学习者理解编程概念。

**📋 分析要求：**
1. **🔍 视觉内容识别**：仔细观察图片中的所有元素
2. **🇯🇵 日文内容提取**：识别并保留所有日文文本
3. **💻 代码深度解析**：逐行分析代码逻辑
4. **🇨🇳 中文详细解释**：提供清晰的中文说明
5. **📚 术语对照建立**：建立日中技术术语对照表

**✨ 输出格式：**

# 🇯🇵🇨🇳 双语程序设计学习笔记

## 🎯 学习主题
[简要描述这张图片的主要教学内容]

## 🇯🇵 日文原文内容
```
[保留图片中的原始日文文本，使用代码格式]
```

## 🇨🇳 中文解释
### 📖 内容概述
[详细的中文解释]

### 💻 代码分析
[如有代码，逐行或逐段分析]

## 📚 重要术语对照
| 🇯🇵 日文 | 🇨🇳 中文 | 📝 说明 |
|----------|----------|---------|
| [术语1] | [翻译1] | [说明1] |
| [术语2] | [翻译2] | [说明2] |

## 💡 学习重点
- **重点1**：[详细说明]
- **重点2**：[详细说明]

## 🔧 实践建议
[提供具体的学习与实践建议]

**要求：内容要详细、准确且具有教育价值。**
**⚠️ 重要：如果没有编程代码，请提供相关的示例代码演示概念。所有内容必须有明确的来源依据。**""",

            "en": """You are a professional Japanese programming instructor and technical analysis expert. Please provide an in-depth bilingual analysis of this image.

**🎯 Analysis Goal:**
Create detailed bilingual study notes (Japanese + English) to help learners understand programming concepts.

**📋 Analysis Requirements:**
1. **🔍 Visual Content Identification**: Carefully observe all elements in the image
2. **🇯🇵 Japanese Content Extraction**: Identify and preserve all Japanese text
3. **💻 Code Deep Analysis**: Analyze code logic line by line
4. **🇺🇸 English Detailed Explanation**: Provide clear English explanations
5. **📚 Terminology Comparison**: Build Japanese-English technical terminology table

**✨ Output Format:**

# 🇯🇵🇺🇸 Bilingual Programming Study Notes

## 🎯 Learning Topic
[Briefly describe the main educational content of this image]

## 🇯🇵 Japanese Original Content
```
[Preserve original Japanese text from image in code format]
```

## 🇺🇸 English Explanation
### 📖 Content Overview
[Detailed English explanation]

### 💻 Code Analysis
[If there's code, provide line-by-line analysis]

## 📚 Important Terminology Comparison
| 🇯🇵 Japanese | 🇺🇸 English | 📝 Explanation |
|---------------|--------------|----------------|
| [Term1] | [Translation1] | [Explanation1] |
| [Term2] | [Translation2] | [Explanation2] |

## 💡 Learning Points
- **Point1**: [Detailed explanation]
- **Point2**: [Detailed explanation]

## 🔧 Practice Suggestions
[Provide specific learning and practice suggestions]

**Requirements: Content should be detailed, accurate, and educational.**""",

            "ko": """당신은 전문적인 일본어 프로그래밍 강사이자 기술 분석 전문가입니다. 이 이미지에 대해 심층적인 이중 언어 분석을 제공해 주세요.

**🎯 분석 목표:**
프로그래밍 개념을 이해하는 데 도움이 되는 상세한 이중 언어 학습 노트(일본어+한국어)를 작성합니다.

**📋 분석 요구사항:**
1. **🔍 시각적 내용 식별**: 이미지의 모든 요소를 주의 깊게 관찰
2. **🇯🇵 일본어 내용 추출**: 모든 일본어 텍스트 식별 및 보존
3. **💻 코드 심층 분석**: 코드 로직을 한 줄씩 분석
4. **🇰🇷 한국어 상세 설명**: 명확한 한국어 설명 제공
5. **📚 용어 대조 구축**: 일한 기술 용어 대조표 구축

**✨ 출력 형식:**

# 🇯🇵🇰🇷 이중 언어 프로그래밍 학습 노트

## 🎯 학습 주제
[이 이미지의 주요 교육 내용을 간결하게 설명]

## 🇯🇵 일본어 원문 내용
```
[이미지의 원본 일본어 텍스트를 코드 형식으로 보존]
```

## 🇰🇷 한국어 설명
### 📖 내용 개요
[상세한 한국어 설명]

### 💻 코드 분석
[코드가 있다면 한 줄씩 분석 제공]

## 📚 중요 용어 대조
| 🇯🇵 일본어 | 🇰🇷 한국어 | 📝 설명 |
|------------|------------|---------|
| [용어1] | [번역1] | [설명1] |
| [용어2] | [번역2] | [설명2] |

## 💡 학습 포인트
- **포인트1**: [상세 설명]
- **포인트2**: [상세 설명]

## 🔧 실습 제안
[구체적인 학습 및 실습 제안 제공]

**요구사항: 내용은 상세하고 정확하며 교육적 가치가 있어야 합니다.**""",

            "ja": """あなたは日本語のプログラミング講師かつ技術分析の専門家です。この画像について、詳細な二言語（日本語＋選択言語）学習ノートを作成してください。

**🎯 目的：**
学習者が内容を体系的に理解できるよう、視覚要素、コード、専門用語を整理します。

**📋 出力フォーマット：**

# 🇯🇵 二言語プログラミング学習ノート

## 🎯 学習テーマ
[画像の主な教育内容を簡潔に説明]

## 🇯🇵 日本語原文
```
[画像に含まれる日本語テキストをそのまま記載]
```

## 📝 解説
### 📖 内容概要
[詳細な解説]

### 💻 コード解析
[コードがあれば逐一解説]

## 📚 重要用語対応表
| 用語 | 説明 |
|------|------|
| [用語1] | [説明1] |
| [用語2] | [説明2] |

## 💡 学習ポイント
- ポイント1：[詳細]
- ポイント2：[詳細]

## 🔧 実践のヒント
[学習・実践の具体的アドバイス]
"""
        }

        # 單語分析提示詞（選擇語言單語）
        monolingual_prompts = {
            "zh-TW": """你是一位專業的程式設計教師和技術分析專家。請對這個圖片進行深度分析。

**分析要求：**
1. **視覺內容解析**：仔細觀察圖片中的每個細節
2. **程式碼分析**：如果有程式碼，請逐行解釋
3. **技術概念講解**：解釋相關的技術概念和原理
4. **學習價值提取**：提供學習重點和建議

**輸出格式：**
### 📋 圖片分析

**🎯 主要內容：** 
[描述圖片的主要教學內容]

**💻 技術詳解：** 
[詳細分析技術內容]

**💡 重點總結：**
[總結學習重點]

內容要詳細且具有教育價值。""",

            "zh-CN": """你是一位专业的程序设计教师与技术分析专家。请对这张图片进行深入分析。

**分析要求：**
1. **视觉内容解析**：仔细观察图片中的每个细节
2. **代码分析**：如有代码，请逐行解释
3. **技术概念讲解**：解释相关的技术概念与原理
4. **学习价值提炼**：提供学习重点与建议

**输出格式：**
### 📋 图片分析

**🎯 主要内容：** 
[描述图片的主要教学内容]

**💻 技术详解：** 
[详细分析技术内容]

**💡 重点总结：**
[总结学习重点]

内容需详尽且具有教育价值。""",

            "en": """You are a professional programming instructor and technical analysis expert. Please provide an in-depth analysis of this image.

**Analysis Requirements:**
1. **Visual Content Analysis**: Carefully observe every detail in the image
2. **Code Analysis**: If there's code, explain it line by line
3. **Technical Concept Explanation**: Explain related technical concepts and principles
4. **Learning Value Extraction**: Provide learning points and suggestions

**Output Format:**
### 📋 Image Analysis

**🎯 Main Content:** 
[Describe the main educational content of the image]

**💻 Technical Details:** 
[Detailed analysis of technical content]

**💡 Key Summary:**
[Summarize learning points]

The content should be detailed and educational.""",

            "ko": """당신은 전문적인 프로그래밍 강사이자 기술 분석 전문가입니다. 이 이미지에 대해 심층 분석을 제공해 주세요.

**분석 요구사항:**
1. **시각적 내용 분석**: 이미지의 모든 세부사항을 주의 깊게 관찰
2. **코드 분석**: 코드가 있다면 한 줄씩 설명
3. **기술 개념 설명**: 관련 기술 개념과 원리 설명
4. **학습 가치 추출**: 학습 포인트와 제안 제공

**출력 형식:**
### 📋 이미지 분석

**🎯 주요 내용:** 
[이미지의 주요 교육 내용 설명]

**💻 기술 세부사항:** 
[기술 내용의 상세 분석]

**💡 핵심 요약:**
[학습 포인트 요약]

내용은 상세하고 교육적 가치가 있어야 합니다.""",

            "ja": """あなたはプロのプログラミング講師および技術分析の専門家です。この画像について詳細な分析を行ってください。

**分析要件：**
1. 視覚的内容の分析：画像内の全ての要素を丁寧に観察
2. コード分析：コードがあれば逐一解説
3. 技術概念の説明：関連する技術概念や原理を説明
4. 学習価値の抽出：学習ポイントと提案を提示

**出力形式：**
### 📋 画像分析

**🎯 主な内容：** 
[画像の主な教育内容を記述]

**💻 技術詳細：** 
[技術内容の詳細分析]

**💡 重要ポイント：**
[学習ポイントの要約]

内容は詳細で教育的価値があること。"""
        }

        # 根據是否包含日文選擇提示詞
        base_prompt = (
            bilingual_prompts.get(language, bilingual_prompts["zh-TW"]) if include_japanese
            else monolingual_prompts.get(language, monolingual_prompts["zh-TW"])
        )

        if context:
            context_labels = {
                "zh-TW": "**額外上下文：**",
                "zh-CN": "**额外上下文：**",
                "ja": "**追加コンテキスト：**",
                "ko": "**추가 컨텍스트:**",
                "en": "**Additional Context:**"
            }
            context_label = context_labels.get(language, context_labels["zh-TW"])
            return f"{base_prompt}\n\n{context_label} {context}"
        return base_prompt

    def _get_ocr_prompt(self, context="", ocr_text="", language="zh-TW", include_japanese=True):
        """
        獲取OCR分析提示詞 - 使用統一 prompt 管理系統
        
        透過 prompt_registry.py 統一管理所有 prompt 函數，避免版本混亂。
        """
        from .prompt_registry import resolve_prompt_bundle
        
        # 使用統一管理系統獲取 prompt bundle
        bundle, profile = resolve_prompt_bundle(self.config)
        
        ocr_text = ocr_text or ""
        has_ocr = bool(ocr_text.strip())

        logger.info(f"🔍 [_get_ocr_prompt] 使用 prompt profile: {profile}, language={language}, has_ocr={has_ocr}")

        if has_ocr:
            # 使用統一的圖片 prompt 函數
            return bundle.image_prompt(ocr_text, language_code=language, context=context, has_ocr=has_ocr)
        else:
            # 沒有 OCR 文字時使用基本提示
            base = self._get_multimodal_prompt(context, language, include_japanese)
            return base


# 工廠函數
def create_image_analyzer(config, llm_config, device="gpu"):
    """創建圖片分析器實例"""
    runtime_state = (config or {}).get("_runtime", {}) if isinstance(config, dict) else {}
    if isinstance(runtime_state, dict):
        device = runtime_state.get("ocr", {}).get("device", device or "cpu") or "cpu"
    else:
        device = device or "cpu"
    return ImageAnalyzer(config, llm_config, device)
