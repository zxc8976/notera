"""
重構後的圖片摘要模組 - 使用模組化架構
"""
import os
import logging
import traceback
from datetime import datetime

from modules.utils.path_utils import normalize_host_path, resolve_container_path
from modules.cornell_pipeline import CornellNotePipeline
from modules.image_analyzer import create_image_analyzer
from modules.note_generator import create_note_generator
from modules.services.pipeline_trace import PipelineTrace
from modules.services.status_manager import StatusManager
from modules.services.gpu_utils import release_cuda_cache

logger = logging.getLogger(__name__)

def get_status_messages(language="zh-TW"):
    """根據語言獲取狀態訊息"""
    messages = {
        'zh-TW': {
            'processing': '處理中',
            'completed': '完成',
            'start_analyzing': '開始分析圖片...',
            'analyzing_with_model': '使用多模態模型分析圖片...',
            'generating_notes': '生成筆記格式...',
            'syncing_images': '同步圖片到前端...',
            'analysis_complete': '圖片分析完成！'
        },
        'zh-CN': {
            'processing': '处理中',
            'completed': '完成',
            'start_analyzing': '开始分析图片...',
            'analyzing_with_model': '使用多模态模型分析图片...',
            'generating_notes': '生成笔记格式...',
            'syncing_images': '同步图片到前端...',
            'analysis_complete': '图片分析完成！'
        },
        'en': {
            'processing': 'Processing',
            'completed': 'Completed',
            'start_analyzing': 'Starting image analysis...',
            'analyzing_with_model': 'Analyzing image with multimodal model...',
            'generating_notes': 'Generating note format...',
            'syncing_images': 'Syncing images to frontend...',
            'analysis_complete': 'Image analysis completed!'
        },
        'ko': {
            'processing': '처리 중',
            'completed': '완료',
            'start_analyzing': '이미지 분석 시작 중...',
            'analyzing_with_model': '멀티모달 모델로 이미지 분석 중...',
            'generating_notes': '노트 형식 생성 중...',
            'syncing_images': '프론트엔드로 이미지 동기화 중...',
            'analysis_complete': '이미지 분석 완료!'
        },
        'vi': {
            'processing': 'Đang xử lý',
            'completed': 'Hoàn tất',
            'start_analyzing': 'Bắt đầu phân tích ảnh...',
            'analyzing_with_model': 'Phân tích ảnh bằng mô hình đa phương thức...',
            'generating_notes': 'Đang tạo định dạng ghi chú...',
            'syncing_images': 'Đồng bộ ảnh với frontend...',
            'analysis_complete': 'Phân tích ảnh hoàn tất!'
        },
        'my': {
            'processing': 'လုပ်ဆောင်နေသည်',
            'completed': 'ပြီးစီး',
            'start_analyzing': 'ပုံကို ခွဲခြမ်းစိတ်ဖြာနေသည်...',
            'analyzing_with_model': 'မုဒ်အမြောက်အများဖြင့် ပုံကို ခွဲခြမ်းစိတ်ဖြာနေသည်...',
            'generating_notes': 'မှတ်စု ဖော်မတ်ကို ထုတ်လုပ်နေသည်...',
            'syncing_images': 'ပုံများကို frontend သို့ ပြောင်းလဲနေသည်...',
            'analysis_complete': 'ပုံ ခွဲခြမ်းစိတ်ဖြာမှု ပြီးစီးသည်!'
        },
        'mn': {
            'processing': 'Боловсруулж байна',
            'completed': 'Дууссан',
            'start_analyzing': 'Зургийг шинжилж эхэлж байна...',
            'analyzing_with_model': 'Олон хэлбэрийн загвараар зураг шинжилж байна...',
            'generating_notes': 'Тэмдэглэл формат үүсгэж байна...',
            'syncing_images': 'Зургийг frontend-т синк хийж байна...',
            'analysis_complete': 'Зураг шинжилгээ дууслаа!'
        }
    }
    return messages.get(language, messages['zh-TW'])


async def summarize_image(
    filename,
    config,
    llm_config,
    status_manager: StatusManager,
    device="gpu",
    skip_ocr=True,
    language="zh-TW",
    include_japanese=True,
):
    """
    圖片摘要主函數 - 使用重構後的模組化架構
    """
    logger.info(f"[summarize_image] 開始處理圖片: {filename} (跳過OCR: {skip_ocr})")
    
    # 解析圖片路徑
    image_path, display_filename = _resolve_image_path(filename)
    
    if not os.path.exists(image_path):
        error_msg = f'圖片檔案不存在: {image_path}'
        logger.error(f"[summarize_image] {error_msg}")
        raise FileNotFoundError(error_msg)

    trace = PipelineTrace()

    try:

        # 根據語言設定狀態訊息
        status_messages = get_status_messages(language)
        update_status(
            display_filename,
            status_messages['processing'],
            10,
            status_messages['start_analyzing'],
            status_manager,
            stage="ingest",
        )
        
        runtime_state = (config or {}).get("_runtime", {}) if isinstance(config, dict) else {}
        ocr_runtime = runtime_state.get("ocr", {}) if isinstance(runtime_state, dict) else {}
        device = ocr_runtime.get("device", device or "cpu") or "cpu"
        ocr_enabled = bool(((config or {}).get("ocr") or {}).get("enabled", True))

        # 1. 創建圖片分析器
        analyzer = create_image_analyzer(config, llm_config, device)
        
        # 2. 分析圖片

        ocr_detail = "擷取圖片文字 (OCR)..." if ocr_enabled else "OCR 已停用，直接進行多模態分析..."
        update_status(
            display_filename,
            status_messages['processing'],
            30,
            ocr_detail,
            status_manager,
            stage="ocr",
        )
        trace.mark_started("ocr", detail=f"device={device}")
        update_status(
            display_filename,
            status_messages['processing'],
            45,
            status_messages['analyzing_with_model'],
            status_manager,
            stage="vlm",
        )
        analysis_result = await analyzer.analyze_image(
            image_path=image_path,
            context="",
            skip_ocr=skip_ocr or not ocr_enabled,
            language=language,
            include_japanese=include_japanese
        )
        _log_image_analysis(display_filename, analysis_result)
        release_cuda_cache(reason="image_ocr_complete")
        ocr_text = analysis_result.get('ocr_text', '') or ''
        trace.mark_completed("ocr", detail=f"text_len={len(ocr_text)}")
        
        # 🚨 檢查是否需要重啟 Ollama
        if not analysis_result['success'] and analysis_result.get('needs_ollama_restart'):
            error_msg = "LLM 分析失敗 - Ollama 服務可能已崩潰"
            logger.error(f"[summarize_image] ❌ {error_msg}")
            trace.mark_failed("verification", error=error_msg)
            update_status(
                display_filename,
                'error',
                0,
                error_msg,
                status_manager,
                stage="error",
                pipeline_trace=trace.to_dict(),
            )

            return {
                'success': False,
                'error': 'LLM_ANALYSIS_FAILED',
                'needs_ollama_restart': True,
                'note': analysis_result.get('analysis', ''),  # 包含錯誤說明
                'base_name': os.path.splitext(display_filename)[0]
            }

        if not analysis_result['success']:
            trace.mark_failed("ocr", error=str(analysis_result.get('error')))
            raise Exception(analysis_result.get('error', 'Unknown error'))

        # 📌 獲取轉換後的圖片路徑(HEIC → JPG)
        final_image_path = analysis_result.get('image_path', image_path)
        final_image_fs = analysis_result.get('image_path_fs', image_path)
        final_display_filename = os.path.basename(final_image_path)
        logger.info(f"[summarize_image] 使用圖片: {final_display_filename} (原始: {display_filename})")

        update_status(
            display_filename,
            status_messages['processing'],
            60,
            "Qwen 進行 OCR 校對中...",
            status_manager,
            stage="verification",
            pipeline_trace=trace.to_dict(),
        )

        pipeline = CornellNotePipeline(llm_config)
        subject_hint = ""
        if isinstance(config, dict):
            output_cfg = config.get("output") or {}
            if isinstance(output_cfg, dict):
                subject_hint = output_cfg.get("default_subject") or output_cfg.get("subject") or ""
        note_generator = create_note_generator(llm_config)
        base_name = os.path.splitext(final_display_filename)[0]
        try:
            cornell_result = await pipeline.run(
                image_path=final_image_fs,
                ocr_text=ocr_text,
                structured_hint=analysis_result.get('structured_summary', ''),
                context=analysis_result.get('visual_focus', ''),
                image_summary=analysis_result.get('analysis', ''),
                suggested_title=os.path.splitext(final_display_filename)[0],
                subject_hint=subject_hint,
                pipeline_trace=trace,
            )
        except Exception as exc:
            logger.error(f"[summarize_image] ❌ Cornell 管線失敗: {exc}")
            trace.mark_failed("verification", error=str(exc))
            fallback_note = _build_fallback_markdown(
                base_name=base_name,
                display_filename=final_display_filename,
                ocr_text=ocr_text,
                analysis_result=analysis_result,
            )
            await note_generator.sync_image_to_frontend(final_image_path, final_display_filename)
            update_status(
                display_filename,
                'warning',
                85,
                f"Cornell 管線失敗，已回退至 OCR 筆記: {exc}",
                status_manager,
                stage="fallback",
                pipeline_trace=trace.to_dict(),
            )
            update_status(
                display_filename,
                status_messages['completed'],
                100,
                "已使用 OCR 結果生成筆記",
                status_manager,
                stage="completed",
                pipeline_trace=trace.to_dict(),
            )
            logger.info(f"[summarize_image] 使用 fallback 筆記，長度: {len(fallback_note)} 字符")
            return fallback_note, base_name

        final_note = cornell_result["markdown"]
        manifest_meta = {
            "prompt_manifest_id": cornell_result["manifest_id"],
            "prompt_manifest_version": cornell_result["manifest_version"],
            "prompt_manifest_hash": cornell_result["manifest_hash"],
        }

        update_status(
            display_filename,
            status_messages['processing'],
            85,
            status_messages['generating_notes'],
            status_manager,
            stage="synthesis",
            pipeline_trace=cornell_result["pipeline_trace"],
            prompt_manifest=manifest_meta,
        )

        note_generator = create_note_generator(llm_config)
        # 4. 同步圖片到前端 (使用轉換後的圖片)
        update_status(
            display_filename,
            status_messages['processing'],
            90,
            status_messages['syncing_images'],
            status_manager,
            stage="saving",
            pipeline_trace=cornell_result["pipeline_trace"],
            prompt_manifest=manifest_meta,
        )
        await note_generator.sync_image_to_frontend(final_image_path, final_display_filename)
        
        update_status(
            display_filename,
            status_messages['completed'],
            100,
            status_messages.get('analysis_complete', '圖片分析完成！'),
            status_manager,
            stage="completed",
            pipeline_trace=cornell_result["pipeline_trace"],
            prompt_manifest=manifest_meta,
        )
        logger.info(f"[summarize_image] 圖片處理完成，筆記長度: {len(final_note)} 字符")
        
        return final_note, base_name

    except Exception as e:
        error_msg = f"圖片處理發生錯誤: {e}"
        logger.error(f"[summarize_image] {error_msg}")
        logger.error(f"[summarize_image] 詳細錯誤跟踪: {traceback.format_exc()}")
        update_status(
            display_filename,
            "錯誤",
            100,
            f"處理失敗: {e}",
            status_manager,
            stage="error",
            pipeline_trace=trace.to_dict() if 'trace' in locals() else None,
        )
        raise


def _build_fallback_markdown(base_name: str, display_filename: str, ocr_text: str, analysis_result: dict) -> str:
    """生成簡單的 OCR fallback 筆記，避免整個流程因 LLM 失敗而產出空白結果。"""
    lines = [
        f"# {base_name}",
        "",
        f"![講義圖片](/images/{display_filename})",
        "",
    ]

    summary = (analysis_result.get("analysis") or "").strip()
    if summary:
        lines.append("## 🔍 自動摘要")
        lines.append(summary)
        lines.append("")

    structured = analysis_result.get("structured_summary")
    if structured and isinstance(structured, str) and structured.strip():
        lines.append("## 📑 結構化重點")
        lines.append(structured.strip())
        lines.append("")

    clean_ocr = [line.strip() for line in (ocr_text or "").splitlines() if line.strip()]
    lines.append("## 📝 OCR 擷取內容")
    if clean_ocr:
        for line in clean_ocr:
            lines.append(f"- {line}")
    else:
        lines.append("- （未擷取到可用文字）")

    return "\n".join(lines).strip() + "\n"

from modules.services.media_paths import get_media_path_service

def _resolve_image_path(filename):
    """統一使用 MediaPathService 解析圖片路徑"""
    _media_path_service = get_media_path_service()
    if os.path.isabs(filename):
        return filename, os.path.basename(filename)
    # 取得 image_path 設定並解析
    image_root = _media_path_service.get("image_path", "")
    result = _media_path_service.resolve(image_root)
    candidate_roots = [p for p in [result.accessible_path, result.container_path, result.normalized_path] if p]
    candidate_roots.append('/app/images')
    for root_path in candidate_roots:
        candidate_path = os.path.join(root_path, filename)
        if os.path.exists(candidate_path):
            if root_path == '/app/images' and image_root:
                logger.info(f"配置路徑無法使用，改為備選路徑: {candidate_path}")
            return candidate_path, filename
    # 若沒有任何候選存在，回傳首個非空路徑（即便目前不存在），確保呼叫端行為一致
    fallback_root = next((root for root in candidate_roots if root), '/app/images')
    return os.path.join(fallback_root, filename), filename

def update_status(filename, status, progress, message, status_manager: StatusManager, **extra):
    """更新處理狀態"""
    payload = {
        'status': status,
        'progress': progress,
        'message': message,
    }

    normalized = str(status).lower()
    if any(keyword in normalized for keyword in ("錯誤", "失敗", "error", "fail")):
        payload.setdefault("error_code", "IMAGE_PIPELINE_FAILURE")
        payload.setdefault("recommended_action", "請檢查 logs/notegen.log 並確認 Ollama / OCR 狀態。")
    elif any(keyword in normalized for keyword in ("警告", "warning")):
        payload.setdefault("recommended_action", "請檢查產出內容，必要時重新執行圖片分析。")

    payload.update(extra)
    status_manager.update(filename, payload)
    logger.info(f"[{filename}] {status} ({progress}%): {message}")


def _log_image_analysis(display_filename: str, analysis_result: dict) -> None:
    """記錄圖片解析結果，便於對照講義與輸出內容。"""
    try:
        traces_dir = os.path.join("logs", "traces", "images")
        os.makedirs(traces_dir, exist_ok=True)
        safe_name = os.path.splitext(display_filename)[0].replace(os.sep, "_")
        log_path = os.path.join(traces_dir, f"{safe_name}.log")
        with open(log_path, "a", encoding="utf-8") as trace:
            trace.write(f"[{datetime.now().isoformat()}] analysis_len={len(analysis_result.get('analysis') or '')}\n")
            trace.write("---- analysis ----\n")
            trace.write((analysis_result.get("analysis") or "").strip() + "\n")
            trace.write("---- ocr_text ----\n")
            trace.write((analysis_result.get("ocr_text") or "").strip()[:4000] + "\n")
            trace.write("---- end ----\n\n")
    except Exception:  #pragma: no cover
        pass
