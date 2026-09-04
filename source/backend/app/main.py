#!/usr/bin/env python3

# -*- coding: utf-8 -*-

import copy
import logging
import threading
from contextlib import suppress
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware

from starlette.staticfiles import StaticFiles
import os
import sys
import json
import asyncio
import traceback
import httpx
import re

import shutil
import time
from logging.handlers import RotatingFileHandler
from datetime import datetime

try:
    import psutil
except Exception:
    psutil = None


# Ensure backend source directory is importable before loading project modules
APP_DIR = Path(__file__).resolve().parent
BACKEND_SRC_DIR = APP_DIR.parent
if str(BACKEND_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC_DIR))

from modules.summarize_video import summarize
from modules.summarize_image import summarize_image
from modules.services.media_paths import PathResolution, get_media_path_service
from modules.services.status_manager import StatusManager
from modules.services.progress_events import ProgressEventBroadcaster
from modules.llm_utils import list_provider_metadata, reload_llm_providers
from modules.api_routes import chat_completion as router_chat_completion, ChatRequest as RouterChatRequest
from modules.services.config_manager import (
    load_config,
    refresh_runtime,
    runtime_summary,
    get_runtime_state,
    save_config,
)
from modules.services.paddleocr_vl import get_paddleocr_vl_status
from modules.services.runtime_paths import (
    DATA_ROOT,
    FRONTEND_DIST_DIR,
    FRONTEND_PUBLIC_IMAGES_DIR,
    LOG_ROOT,
    NOTES_ROOT,
    OUTPUT_ROOT,
    TMP_ROOT,
    ensure_runtime_dirs,
)
from modules.services.system_metrics import (
    capture_snapshot,
    resolve_monitored_paths,
)
from modules.services.prompt_manifest import (
    manifest_dict,
    manifest_hash,
    manifest_id,
    manifest_version,
)

ensure_runtime_dirs()

output_root_str = str(OUTPUT_ROOT)
output_images_root = str(OUTPUT_ROOT / "images")
output_tmp_root = str(OUTPUT_ROOT / "tmp")
notes_root_str = str(NOTES_ROOT)
log_root_path = LOG_ROOT
tmp_root_path = TMP_ROOT
data_dir = DATA_ROOT

UI_ALLOWED_MODELS = ("qwen3-vl:235b-cloud", "qwen3-vl:4b")


def _filter_ui_models(models: list[str]) -> list[str]:
    seen = set()
    filtered: list[str] = []
    for model in UI_ALLOWED_MODELS:
        if model in models and model not in seen:
            filtered.append(model)
            seen.add(model)
    return filtered

def get_status_messages(language="zh-TW"):
    """根據語言獲取狀態訊息"""
    messages = {
        'zh-TW': {
            'processing': '處理中',
            'completed': '完成',
            'start_processing': '開始處理...',
            'processing_complete': '處理完成',
            'preparing': '準備處理',
            'start_folder_processing': '開始處理圖片...',
            'folder_complete': '成功處理 {count} 張圖片並合併完成',
            'folder_processing_complete': '資料夾批量處理完成',
            'emergency_reset_complete': '緊急重置完成',
            'image_sync_complete': '圖片同步完成',
            'note_format_complete': '筆記格式處理完成'
        },
        'zh-CN': {
            'processing': '处理中',
            'completed': '完成',
            'start_processing': '开始处理...',
            'processing_complete': '处理完成',
            'preparing': '准备处理',
            'start_folder_processing': '开始处理图片...',
            'folder_complete': '成功处理 {count} 张图片并合并完成',
            'folder_processing_complete': '文件夹批量处理完成',
            'emergency_reset_complete': '紧急重置完成',
            'image_sync_complete': '图片同步完成',
            'note_format_complete': '笔记格式处理完成'
        },
        'en': {
            'processing': 'Processing',
            'completed': 'Completed',
            'start_processing': 'Starting processing...',
            'processing_complete': 'Processing complete',
            'preparing': 'Preparing to process',
            'start_folder_processing': 'Starting image processing...',
            'folder_complete': 'Successfully processed {count} images and merged',
            'folder_processing_complete': 'Folder batch processing complete',
            'emergency_reset_complete': 'Emergency reset complete',
            'image_sync_complete': 'Image sync complete',
            'note_format_complete': 'Note format processing complete'
        },
        'ko': {
            'processing': '처리 중',
            'completed': '완료',
            'start_processing': '처리 시작 중...',
            'processing_complete': '처리 완료',
            'preparing': '처리 준비 중',
            'start_folder_processing': '이미지 처리 시작 중...',
            'folder_complete': '{count}개 이미지를 성공적으로 처리하고 병합 완료',
            'folder_processing_complete': '폴더 일괄 처리 완료',
            'emergency_reset_complete': '긴급 재설정 완료',
            'image_sync_complete': '이미지 동기화 완료',
            'note_format_complete': '노트 형식 처리 완료'
        },
        'vi': {
            'processing': 'Đang xử lý',
            'completed': 'Hoàn tất',
            'start_processing': 'Bắt đầu xử lý...',
            'processing_complete': 'Xử lý hoàn tất',
            'preparing': 'Đang chuẩn bị',
            'start_folder_processing': 'Bắt đầu xử lý ảnh...',
            'folder_complete': 'Đã xử lý và gộp {count} ảnh',
            'folder_processing_complete': 'Hoàn tất xử lý thư mục',
            'emergency_reset_complete': 'Đặt lại khẩn cấp hoàn tất',
            'image_sync_complete': 'Đồng bộ ảnh hoàn tất',
            'note_format_complete': 'Hoàn tất định dạng ghi chú'
        },
        'my': {
            'processing': 'လုပ်ဆောင်နေသည်',
            'completed': 'ပြီးစီး',
            'start_processing': 'လုပ်ဆောင်ခြင်း စတင်နေသည်...',
            'processing_complete': 'လုပ်ဆောင်မှု ပြီးစီးသည်',
            'preparing': 'ပြင်ဆင်နေသည်',
            'start_folder_processing': 'ပုံများကို စတင်လုပ်ဆောင်နေသည်...',
            'folder_complete': 'ပုံ {count} ပုံကို လုပ်ဆောင်ပြီး ပေါင်းစည်းပြီးစီးသည်',
            'folder_processing_complete': 'ဖိုင်တွဲ အစုလိုက် လုပ်ဆောင်မှု ပြီးစီးသည်',
            'emergency_reset_complete': 'အရေးပေါ် ပြန်လည်သတ်မှတ်ခြင်း ပြီးစီးသည်',
            'image_sync_complete': 'ပုံများ စနစ်တကျပြောင်းလဲခြင်း ပြီးစီးသည်',
            'note_format_complete': 'မှတ်စု ဖော်မတ်ပြင်ဆင်မှု ပြီးစီးသည်'
        },
        'mn': {
            'processing': 'Боловсруулж байна',
            'completed': 'Дууссан',
            'start_processing': 'Боловсруулж эхэлж байна...',
            'processing_complete': 'Боловсруулалт дууслаа',
            'preparing': 'Бэлтгэж байна',
            'start_folder_processing': 'Зургийг боловсруулж эхэлж байна...',
            'folder_complete': '{count} зураг боловсруулж нэгтгэлээ',
            'folder_processing_complete': 'Фолдерын боловсруулалт дууслаа',
            'emergency_reset_complete': 'Яаралтай дахин тохируулга дууслаа',
            'image_sync_complete': 'Зураг синк хийж дууслаа',
            'note_format_complete': 'Тэмдэглэл форматлах дууслаа'
        },
        'ja': {
            'processing': '処理中',
            'completed': '完了',
            'start_processing': '処理を開始しています...',
            'processing_complete': '処理が完了しました',
            'preparing': '処理の準備',
            'start_folder_processing': '画像の処理を開始しています...',
            'folder_complete': '合計 {count} 枚の画像を処理して統合しました',
            'folder_processing_complete': 'フォルダーの一括処理が完了しました',
            'emergency_reset_complete': '緊急リセットが完了しました',
            'image_sync_complete': '画像の同期が完了しました',
            'note_format_complete': 'ノートのフォーマット処理が完了しました'
        }
    }
    return messages.get(language, messages['zh-TW'])


def resolve_language_mode(language: Optional[str], include_japanese: bool, language_mode: Optional[str]) -> Tuple[str, bool, Optional[str]]:
    """Normalize language mode and derive effective language flags."""
    normalized = (language_mode or "").strip().lower().replace("_", "-")
    if normalized in {"ja-only", "japanese-only", "ja"}:
        return "ja", False, "ja-only"
    if normalized in {"bilingual", "ja-bilingual", "jp-bilingual", "japanese-bilingual"}:
        return language or "zh-TW", True, "bilingual"
    return language or "zh-TW", include_japanese, None


config = load_config()
llm_config = config.get('llm', {})

# 設置日誌
log_dir = str(log_root_path)
os.makedirs(log_dir, exist_ok=True)

# 配置根logger,確保INFO級別生效
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 控制台輸出
        RotatingFileHandler(
            os.path.join(log_dir, 'notegen.log'), 
            maxBytes=5*1024*1024, 
            backupCount=3, 
            encoding='utf-8'
        )
    ]
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # 確保本模組的logger級別正確

app = FastAPI(title="自動筆記生成系統", version="3.0.7-enhanced")


@app.on_event("startup")
async def configure_progress_stream() -> None:
    """Bind FastAPI event loop to the progress broadcaster."""
    loop = asyncio.get_running_loop()
    progress_broadcaster.bind_loop(loop)
    runtime = refresh_runtime()
    if runtime.get("active_device") == "gpu":
        logger.info(
            "Runtime acceleration ready (device=gpu, device_id=%s)",
            runtime.get("ocr", {}).get("device_id"),
        )
    else:
        logger.info("Runtime operating in CPU mode (fallback_reason=%s)", runtime.get("fallback_reason"))
    try:
        cfg = load_config()
        ocr_status = get_paddleocr_vl_status(cfg)
        logger.info(
            "[Startup] PaddleOCR-VL ok=%s version=%s device=%s batch=%s model_root=%s layout_dir=%s",
            ocr_status.get("ok"),
            ocr_status.get("version") or "unknown",
            ocr_status.get("device"),
            ocr_status.get("batch_size"),
            ocr_status.get("model_root"),
            ocr_status.get("layout_model_dir"),
        )
        llm_cfg = cfg.get("llm", {}) if isinstance(cfg, dict) else {}
        logger.info(
            "[Startup] Qwen3-VL scene=%s image=%s final=%s",
            llm_cfg.get("scene_model"),
            llm_cfg.get("image_model"),
            llm_cfg.get("final_model"),
        )
    except Exception as exc:
        logger.warning("[Startup] Unable to log OCR/VLM status: %s", exc)


@app.websocket("/ws/progress")
async def progress_stream(websocket: WebSocket) -> None:
    """Stream task progress events to frontend clients."""
    await websocket.accept()
    subscriber_id, queue = progress_broadcaster.subscribe()
    logger.info("Progress websocket connected (subscriber %s)", subscriber_id)
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        logger.info("Progress websocket disconnected (subscriber %s)", subscriber_id)
    except Exception as exc:
        logger.warning("Progress websocket error: %s", exc)
    finally:
        progress_broadcaster.unsubscribe(subscriber_id)


@app.get("/api/progress/{task_id}")
async def get_task_progress(task_id: str, limit: int = 20) -> Dict[str, Any]:
    """Return recent progress events for a specific task."""
    limit = max(1, min(limit, 100))
    events = list(progress_broadcaster.recent(limit=limit, job_id=task_id))
    return {"events": events, "job_id": task_id}


@app.get("/api/progress")
async def get_recent_progress(limit: int = 20) -> Dict[str, Any]:
    """Return recent progress events across all tasks."""
    limit = max(1, min(limit, 100))
    events = list(progress_broadcaster.recent(limit=limit))
    return {"events": events}

# CORS 設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VIDEOS_ROOT = data_dir / "videos"
IMAGES_ROOT = data_dir / "images"
EXTERNAL_IMAGES_ROOT = data_dir / "external" / "f" / "講義圖片"

UPLOAD_FOLDER = str(VIDEOS_ROOT)
image_folder = str(IMAGES_ROOT)

# 確保主要資料目錄存在
for _path in (VIDEOS_ROOT, IMAGES_ROOT):
    _path.mkdir(parents=True, exist_ok=True)

# 檢測容器環境中的圖片目錄
def init_image_folder() -> str:
    external_image_dir = str(EXTERNAL_IMAGES_ROOT)
    if os.path.exists(external_image_dir):
        logger.info(f"使用外部圖片目錄: {external_image_dir}")
        return external_image_dir
    else:
        default_folder = str(IMAGES_ROOT)
        os.makedirs(default_folder, exist_ok=True)
        logger.info(f"使用本地圖片目錄: {default_folder}")
        return default_folder

# 初始化圖片目錄
IMAGE_FOLDER = init_image_folder()

# 狀態暫存（可用更進階方式替換）
status_manager = StatusManager()
progress_broadcaster = ProgressEventBroadcaster()

# 背景任務追蹤（用於後端實際取消）
_active_tasks: Dict[str, Dict[str, Any]] = {}
_active_tasks_lock = asyncio.Lock()


def _resolve_task_key(task_id: str) -> str:
    """標準化任務識別字，處理副檔名/基名差異。"""
    if status_manager.contains(task_id):
        return task_id
    base = os.path.basename(task_id)
    if status_manager.contains(base):
        return base
    similar = status_manager.find_similar(task_id)
    if similar:
        return similar[0]
    return task_id


async def register_active_task(
    task_id: str,
    task: asyncio.Task,
    cancel_event: Optional[asyncio.Event] = None,
    metrics_stop: Optional[threading.Event] = None,
) -> None:
    """記錄正在執行的背景任務，便於後續取消。"""
    async with _active_tasks_lock:
        _active_tasks[task_id] = {
            "task": task,
            "cancel_event": cancel_event,
            "metrics_stop": metrics_stop,
        }

    def _cleanup(_: asyncio.Task) -> None:
        asyncio.create_task(unregister_active_task(task_id))

    task.add_done_callback(_cleanup)


async def unregister_active_task(task_id: str) -> None:
    async with _active_tasks_lock:
        _active_tasks.pop(task_id, None)


async def cancel_active_task(task_id: str) -> bool:
    """嘗試取消背景任務，若存在則返回 True。"""
    candidate_ids = [task_id, os.path.basename(task_id)]
    async with _active_tasks_lock:
        resolved_id = next((cid for cid in candidate_ids if cid in _active_tasks), None)
        entry = _active_tasks.get(resolved_id) if resolved_id else None

    if not entry:
        return False

    cancel_event = entry.get("cancel_event")
    if isinstance(cancel_event, asyncio.Event):
        cancel_event.set()

    metrics_stop = entry.get("metrics_stop")
    if isinstance(metrics_stop, threading.Event):
        metrics_stop.set()

    task = entry.get("task")
    if isinstance(task, asyncio.Task) and not task.done():
        task.cancel()
        with suppress(asyncio.CancelledError, asyncio.TimeoutError):
            await asyncio.wait_for(task, timeout=1.0)

    await unregister_active_task(resolved_id or task_id)
    return True


def _mark_task_cancelled(task_id: str, detail: str = "使用者取消處理") -> Dict[str, Any]:
    """標記任務為已取消並回傳更新後的狀態。"""
    snapshot = status_manager.get(task_id, {})
    payload = {
        "status": "取消",
        "status_code": "cancelled",
        "progress": snapshot.get("progress", 0),
        "detail": detail,
        "timestamp": time.time(),
    }
    return status_manager.update(task_id, payload)


def _is_cancelled_status(task_id: str, cancel_event: Optional[asyncio.Event] = None) -> bool:
    """檢查任務是否已被標記取消或收到取消事件。"""
    if isinstance(cancel_event, asyncio.Event) and cancel_event.is_set():
        return True
    
    # Check if cancelled via StatusManager API
    if status_manager.is_cancelled(task_id):
        return True
    
    snapshot = status_manager.get(task_id, {})
    
    # Check the cancelled flag directly
    if snapshot.get("cancelled", False):
        return True
    
    # Check status text for cancellation keywords
    text = str(snapshot.get("status_code") or snapshot.get("status") or "").lower()
    return "cancel" in text or "取消" in text or "中止" in text


def _normalize_status_label(label: Any, event_type: str) -> str:
    text = str(label or "").lower()
    if event_type == "remove":
        return "removed"
    if event_type == "create" and not text:
        return "queued"
    if any(keyword in text for keyword in ("取消", "cancelled", "canceled", "中止", "停止", "cancel")):
        return "cancelled"
    if any(keyword in text for keyword in ("錯誤", "失敗", "error", "fail")):
        return "failed"
    if any(keyword in text for keyword in ("重試", "retry")):
        return "retrying"
    if any(keyword in text for keyword in ("完成", "成功", "complete", "done")):
        return "completed"
    if any(keyword in text for keyword in ("警告", "warning")):
        return "warning"
    if any(keyword in text for keyword in ("等待", "queued", "排程")):
        return "queued"
    if any(keyword in text for keyword in ("開始", "初始化", "準備", "starting")):
        return "starting"
    return "running"


def _normalize_requested_note_style(note_style: Optional[str]) -> str:
    raw = (note_style or "").strip().lower()
    if raw in {"detailed", "lecture", "class", "classroom", "lecturemode"}:
        return "lecture"
    if raw in {"summary", "meeting", "minutes", "meetingmode"}:
        return "meeting"
    return ""


_STAGE_KEYWORDS = (
    ("ingest", ("開始處理", "start", "初始化", "準備", "upload", "preparing")),
    ("scene-detection", ("偵測場景", "場景偵測", "偵測到", "scene detect", "切片")),
    ("scene-processing", ("處理場景", "scene ", "場景 ", "batch", "影格")),
    ("ocr", ("ocr", "文字辨識", "辨識", "文字", "擷取畫面")),
    ("vlm", ("vlm", "llm", "推論", "分析", "摘要", "model")),
    ("formatting", ("整合筆記", "格式", "markdown", "格式化", "組合")),
    ("saving", ("保存", "儲存", "寫入", "save", "同步", "sync")),
    ("completed", ("完成", "成功", "complete", "done")),
    ("error", ("錯誤", "失敗", "error", "fail")),
    ("cancelled", ("取消", "cancel", "中止", "停止")),
)


def _infer_stage(snapshot: Dict[str, Any], event_type: str) -> str:
    status_text = str(snapshot.get("status_code") or snapshot.get("status") or "").lower()
    if "cancel" in status_text or "取消" in status_text or "中止" in status_text:
        return "cancelled"
    explicit = snapshot.get("stage") or snapshot.get("detail_stage") or snapshot.get("pipeline_stage")
    if explicit:
        return str(explicit)

    detail = snapshot.get("detail") or snapshot.get("message") or ""
    variants = {str(detail), str(detail).lower()}

    for stage, keywords in _STAGE_KEYWORDS:
        for variant in variants:
            if any(keyword in variant for keyword in keywords):
                return stage

    if event_type == "create":
        return "queued"
    if event_type == "remove":
        return "finished"
    if snapshot.get("progress", 0) >= 100:
        return "completed"
    return "processing"


def _broadcast_status_update(task_id: str, snapshot: Dict[str, Any], event_type: str) -> None:
    event: Dict[str, Any] = {
        "job_id": task_id,
        "type": event_type,
        "status": _normalize_status_label(snapshot.get("status"), event_type),
        "status_label": snapshot.get("status"),
        "stage": _infer_stage(snapshot, event_type),
        "progress": snapshot.get("progress", 0),
        "message": snapshot.get("detail") or snapshot.get("message"),
        "estimated_remaining": snapshot.get("estimated_remaining"),
        "metrics": snapshot.get("metrics"),
    }

    if "structured" in snapshot:
        event["has_structured_payload"] = True
    if "error_code" in snapshot:
        event["error_code"] = snapshot["error_code"]
    if "recommended_action" in snapshot:
        event["recommended_action"] = snapshot["recommended_action"]

    if event["status"] in {"failed", "retrying"}:
        event.setdefault("error_code", snapshot.get("error_code") or "unknown")
        event.setdefault(
            "recommended_action",
            snapshot.get("recommended_action") or "請檢查 logs/notegen.log 取得詳細錯誤。",
        )

    progress_broadcaster.publish(event)


status_manager.add_listener(_broadcast_status_update)

# 預設分類
DEFAULT_CATEGORIES = [
    "日本電子課程/サーバーサイドプログラミングⅡ",
    "日本電子課程/ITストラテジー",
    "日本電子課程/クライアントサイドプログラミングⅡ",
    "日本電子課程/機械学習Ⅱ",
    "日本電子課程/オブジェクト指向分析・設計Ⅰ",
    "日本電子課程/データマイニング",
    "日本電子課程/AIプログラミングⅡ",
    "日本電子課程/エッジコンピューティングⅠ・Ⅱ"
]

# ---- 路徑配置服務 ----
media_path_service = get_media_path_service()
paths_config = media_path_service.paths_config


def _read_paths_config() -> dict:
    """Backwards-compatible shim to refresh path configuration from disk."""
    return media_path_service.refresh()


def _write_paths_config(paths: dict) -> None:
    """Backwards-compatible shim to persist path configuration to disk."""
    media_path_service.paths_config.clear()
    media_path_service.paths_config.update(paths)
    media_path_service.save()

def _resolve_media_directory(raw_path: str) -> tuple[Optional[str], Optional[PathResolution]]:
    """Return an accessible directory for the media path and its resolution."""
    if not raw_path:
        return None, None

    resolution = media_path_service.resolve(os.path.expandvars(raw_path))
    for candidate in (resolution.accessible_path, resolution.container_path, resolution.normalized_path):
        if candidate and os.path.exists(candidate):
            return candidate, resolution
    return None, resolution

# 啟動時自動建立預設分類資料夾
for cat in DEFAULT_CATEGORIES:
    cat_path = os.path.join(notes_root_str, cat)
    os.makedirs(cat_path, exist_ok=True)

# API 路由
@app.get("/api/version")
async def get_version():
    """獲取應用版本信息"""
    logger.info("獲取應用版本信息")
    return {"version": "3.0.7-enhanced", "status": "running"}

@app.get("/api/health")
async def health_check():
    """健康檢查端點"""
    summary = runtime_summary()
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "runtime": summary,
    }

@app.get("/api/models")
async def get_models():
    """獲取可用模型列表"""
    logger.info("獲取可用模型列表")
    metadata = list_provider_metadata()
    active = metadata.get("active")
    active_info = next((item for item in metadata.get("providers", []) if item.get("name") == active), None)

    if active == "ollama":
        base_url = (active_info or {}).get("base_url") or "http://ollama:11434"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{base_url.rstrip('/')}/api/tags")
                if response.status_code == 200:
                    models_data = response.json()
                    raw_models = [model["name"] for model in models_data.get("models", []) if isinstance(model, dict)]
                    models = _filter_ui_models(raw_models)
                    logger.info("Ollama 返回 %d 個模型，前端白名單保留 %d 個", len(raw_models), len(models))
                    return {"models": models}
                logger.warning("Ollama 回傳非 200 狀態碼: %s", response.status_code)
        except Exception as error:
            logger.error("向 Ollama 取得模型列表失敗: %s", error)

    # Default fallback
    fallback_models = []
    if active_info and active_info.get("model"):
        fallback_models.append(active_info["model"])
    fallback_models.extend(metadata.get("providers", [{}])[0].get("models", []))
    fallback_models = [m for m in fallback_models if m]
    filtered_fallback_models = _filter_ui_models(fallback_models)
    return {"models": filtered_fallback_models or ["qwen3-vl:4b"]}

@app.get("/api/get-paths")
async def get_paths():
    """獲取已設置的路徑"""
    logger.info("獲取已設置的路徑")
    try:
        paths = _read_paths_config()
        logger.info(f"成功讀取路徑配置: {paths}")
        return paths
    except Exception as e:
        logger.error(f"讀取路徑配置時出錯: {e}")
        return {"video_path": "", "image_path": ""}

@app.post("/api/set-paths")
async def set_paths(video_path: str = Form(""), image_path: str = Form("")):
    """設置路徑"""
    logger.info(f"設置路徑 - 視頻路徑: {video_path}, 圖片路徑: {image_path}")
    try:
        paths = {
            "video_path": video_path,
            "image_path": image_path
        }
        _write_paths_config(paths)
        logger.info("路徑配置保存成功")
        return {"status": "success", "message": "路徑設置成功"}
    except Exception as e:
        logger.error(f"保存路徑配置時出錯: {e}")
        return {"status": "error", "message": f"設置失敗: {str(e)}"}

@app.get("/api/videos")
async def list_videos():
    """列出所有視頻文件"""
    logger.info("列出所有視頻文件")
    try:
        paths_config = _read_paths_config()
        video_path = paths_config.get("video_path", "")
        if not video_path:
            logger.info("視頻路徑未設置")
            return {"videos": [], "folder": ""}

        resolved_path, resolution = _resolve_media_directory(video_path)
        logger.info(
            "影片路徑解析: %s -> %s",
            video_path,
            resolved_path or (resolution.container_path if resolution else "未解析"),
        )

        if not resolved_path:
            logger.warning(
                "影片路徑無法訪問: %s (container: %s, normalized: %s)",
                video_path,
                resolution.container_path if resolution else "未知",
                resolution.normalized_path if resolution else "未知",
            )
            return {"videos": [], "folder": video_path}
        
        video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv')
        videos = []
        for root, dirs, files in os.walk(resolved_path):
            for file in files:
                if file.lower().endswith(video_extensions):
                    full_path = os.path.join(root, file)
                    relative_path = os.path.relpath(full_path, resolved_path)
                    stat = os.stat(full_path)
                    # 获取目录类别
                    category = os.path.dirname(relative_path).replace("\\", "/")
                    if category == ".":
                        category = ""
                    # 檢查是否有處理結果
                    has_result = False
                    result_paths = [
                        os.path.join(notes_root_str, file.replace('.mp4', '.md')),
                        os.path.join(notes_root_str, os.path.splitext(file)[0] + '.md'),
                        os.path.join(output_root_str, file.replace('.mp4', '.md')),
                        os.path.join(output_root_str, os.path.splitext(file)[0] + '.md')
                    ]
                    for result_path in result_paths:
                        if os.path.exists(result_path):
                            has_result = True
                            break
                    
                    # 檢查暫存狀態
                    has_tmp = False
                    tmp_info = None
                    if status_manager.contains(file):
                        status_info = status_manager.get(file)
                        status_label = str(status_info.get('status') or '')
                        status_code = str(status_info.get('status_code') or '').lower()
                        is_completed = status_code == 'completed' or status_label in ['完成', 'completed', '完了'] or '完成' in status_label
                        is_idle = status_label in ['idle', 'unknown', '未知']
                        if not is_completed and not is_idle:
                            has_tmp = True
                            tmp_info = {
                                'type': 'processing',
                                'status': status_label or 'processing',
                                'progress': status_info.get('progress', 0),
                                'detail': status_info.get('detail') or '',
                                'current_file': status_info.get('current_file') or '',
                                'elapsed_time': status_info.get('elapsed_time', 0),
                            }
                        elif is_completed:
                            tmp_info = {
                                'type': 'completed',
                                'status': status_label or '完成',
                                'progress': 100
                            }
                            has_result = True
                    
                    # 獲取影片時長（簡化版本）
                    duration = None
                    try:
                        import cv2
                        cap = cv2.VideoCapture(full_path)
                        if cap.isOpened():
                            fps = cap.get(cv2.CAP_PROP_FPS)
                            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                            if fps > 0:
                                duration = int(frame_count / fps)
                        cap.release()
                    except Exception as e:
                        logger.debug(f"無法獲取影片時長 {file}: {e}")
                    
                    videos.append({
                        "name": file,
                        "path": relative_path,
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                        "category": category,
                        "duration": duration,
                        "hasResult": has_result,
                        "hasTmp": has_tmp,
                        "tmpInfo": tmp_info
                    })
        
        logger.info(f"找到 {len(videos)} 個視頻文件")
        return {"videos": videos, "folder": video_path}
    except Exception as e:
        logger.error(f"列出視頻文件時出錯: {e}")
        logger.error(traceback.format_exc())
        return {"videos": [], "folder": ""}

@app.get("/api/images")
async def list_images():
    """列出所有圖片文件"""
    logger.info("列出所有圖片文件")
    try:
        paths_config = _read_paths_config()
        image_path = paths_config.get("image_path", "")
        if not image_path:
            logger.info("圖片路徑未設置")
            return {"images": []}

        resolved_path, resolution = _resolve_media_directory(image_path)
        logger.info(
            "圖片路徑解析: %s -> %s",
            image_path,
            resolved_path or (resolution.container_path if resolution else "未解析"),
        )

        if not resolved_path:
            logger.warning(
                "圖片路徑無法訪問: %s (container: %s, normalized: %s)",
                image_path,
                resolution.container_path if resolution else "未知",
                resolution.normalized_path if resolution else "未知",
            )
            return {"images": []}
        
        image_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.heic', '.heif')
        images = []
        folders = {}  # 用於按資料夾分組
        
        for root, dirs, files in os.walk(resolved_path):
            for file in files:
                if file.lower().endswith(image_extensions):
                    full_path = os.path.join(root, file)
                    relative_path = os.path.relpath(full_path, resolved_path)
                    stat = os.stat(full_path)
                    
                    # 獲取資料夾路徑
                    folder_path = os.path.dirname(relative_path).replace("\\", "/")
                    if folder_path == ".":
                        folder_path = ""
                    
                    # 檢查是否有處理結果（個別圖片）
                    has_result = False
                    result_paths = [
                        os.path.join(notes_root_str, file.replace('.jpg', '.md')),
                        os.path.join(notes_root_str, file.replace('.jpeg', '.md')),
                        os.path.join(notes_root_str, file.replace('.png', '.md')),
                        os.path.join(notes_root_str, os.path.splitext(file)[0] + '.md'),
                        os.path.join(output_root_str, file.replace('.jpg', '.md')),
                        os.path.join(output_root_str, file.replace('.jpeg', '.md')),
                        os.path.join(output_root_str, file.replace('.png', '.md')),
                        os.path.join(output_root_str, os.path.splitext(file)[0] + '.md')
                    ]
                    for result_path in result_paths:
                        if os.path.exists(result_path):
                            has_result = True
                            break
                    
                    # 檢查資料夾是否有合併結果
                    folder_result_name = folder_path.replace('/', '_') + '_combined.md' if folder_path else 'root_combined.md'
                    folder_has_result = os.path.exists(os.path.join(notes_root_str, folder_result_name))
                    
                    image_info = {
                        "name": file,
                        "path": relative_path,
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                        "has_result": has_result,
                        "folder": folder_path
                    }
                    
                    images.append(image_info)
                    
                    # 按資料夾分組
                    if folder_path not in folders:
                        folders[folder_path] = {
                            "name": folder_path or "根目錄",
                            "path": folder_path,
                            "images": [],
                            "has_combined_result": folder_has_result,
                            "image_count": 0
                        }
                    
                    folders[folder_path]["images"].append(image_info)
                    folders[folder_path]["image_count"] += 1
        
        logger.info(f"找到 {len(images)} 個圖片文件, 分布在 {len(folders)} 個資料夾中")
        return {
            "images": images,
            "folders": list(folders.values())
        }
    except Exception as e:
        logger.error(f"列出圖片文件時出錯: {e}")
        logger.error(traceback.format_exc())
        return {"images": []}

@app.post("/api/process-video")
async def process_video(
    video_path: str = Form(...),
    with_images: bool = Form(True),
    device: Optional[str] = Form(None),
    parse_audio: bool = Form(True),
    language: str = Form("zh-TW"),
    include_japanese: bool = Form(True),
    language_mode: Optional[str] = Form(default=None),
    note_style: Optional[str] = Form(default=None),
    model: Optional[str] = Form(default=None),

    run_token: str = Form(default=""),
):
    """處理視頻文件"""
    logger.info("開始處理視頻: %s", video_path)

    language, include_japanese, resolved_mode = resolve_language_mode(
        language,
        include_japanese,
        language_mode,
    )
    if resolved_mode:
        logger.info(
            "language_mode=%s -> language=%s, include_japanese=%s",
            resolved_mode,
            language,
            include_japanese,
        )

    config_snapshot = load_config()

    runtime_state = config_snapshot.get("_runtime") or get_runtime_state()
    ocr_runtime = runtime_state.get("ocr", {})
    default_device = ocr_runtime.get("device", "cpu")
    requested_device = (device or default_device).lower()
    if requested_device not in {"cpu", "gpu"}:
        requested_device = default_device
    if requested_device == "gpu" and default_device != "gpu":
        logger.warning(
            "Requested GPU execution but runtime is in %s mode; falling back to %s.",
            default_device,
            default_device,
        )
        effective_device = default_device
    else:
        effective_device = requested_device

    logger.info(
        "處理參數 - with_images: %s, requested_device: %s, active_runtime_device: %s, parse_audio: %s",
        with_images,
        requested_device,
        default_device,
        parse_audio,
    )

    device = effective_device

    global config, llm_config
    config = config_snapshot
    llm_config = config.get('llm', {})

    requested_style = _normalize_requested_note_style(note_style)

    effective_config = copy.deepcopy(config)
    if requested_style:
        output_cfg = effective_config.setdefault("output", {})
        if requested_style == "meeting":
            output_cfg["note_style"] = "meeting"
            output_cfg["prompt_profile"] = "optimized"
            transcript_cfg = output_cfg.setdefault("transcript_notes", {})
            transcript_cfg["enabled"] = False
        else:
            output_cfg["note_style"] = "blueprint"
            output_cfg["prompt_profile"] = "optimized"
        logger.info("套用筆記風格: %s", requested_style)
    
    try:
        # 解析設定中的影片根目錄並構建最終路徑
        paths_config = _read_paths_config()
        base_video_path = paths_config.get("video_path", "")
        resolved_base_path, resolution = _resolve_media_directory(base_video_path)
        if not resolved_base_path:
            logger.error(
                "影片根路徑無法訪問: %s (container: %s, normalized: %s)",
                base_video_path,
                resolution.container_path if resolution else "未知",
                resolution.normalized_path if resolution else "未知",
            )
            raise HTTPException(status_code=400, detail="影片根路徑不可用，請重新設定")

        normalized_video_path = (video_path or "").strip()

        # Git Bash on Windows may rewrite absolute POSIX paths to
        # C:/Program Files/Git/...; recover the intended container path.
        if re.match(r"^[A-Za-z]:/Program Files/Git/", normalized_video_path):
            normalized_video_path = "/" + normalized_video_path.split("/Program Files/Git/", 1)[1].lstrip("/")
        elif re.match(r"^[A-Za-z]:\\\\Program Files\\\\Git\\\\", normalized_video_path):
            normalized_video_path = "/" + normalized_video_path.split("\\Program Files\\Git\\", 1)[1].lstrip("\\/").replace("\\", "/")

        if os.path.isabs(normalized_video_path):
            full_video_path = os.path.normpath(normalized_video_path)
            relative_video_path = os.path.relpath(full_video_path, resolved_base_path) if full_video_path.startswith(os.path.normpath(resolved_base_path) + os.sep) else normalized_video_path
        else:
            relative_video_path = normalized_video_path
            full_video_path = os.path.join(resolved_base_path, relative_video_path)

        logger.info(f"影片路徑轉換: {video_path} -> {full_video_path}")
        
        # 檢查文件是否存在
        if not os.path.exists(full_video_path):
            logger.error(f"視頻文件不存在: {full_video_path}")
            raise HTTPException(
                status_code=404,
                detail=(
                    "視頻文件不存在，請使用 /api/videos 回傳的 path 欄位。"
                    f" base={resolved_base_path}, requested={video_path}"
                ),
            )
        
        # 獲取文件名作為狀態鍵
        filename = os.path.basename(relative_video_path)

        # 強制重新處理：清理舊狀態與舊結果檔
        try:
            if status_manager.remove(filename):
                logger.debug(f"已清除既有狀態: {filename}")
            # 推導可能的舊結果檔並刪除（output 與 notes 兩處）
            base_name = os.path.splitext(os.path.basename(filename))[0]
            candidate_paths = [
                os.path.join(output_root_str, f'{filename}.md'),
                os.path.join(output_root_str, filename.replace('.mp4', '.md')),
                os.path.join(output_root_str, f'{base_name}.md'),
                os.path.join(notes_root_str, f'{filename}.md'),
                os.path.join(notes_root_str, filename.replace('.mp4', '.md')),
                os.path.join(notes_root_str, f'{base_name}.md'),
            ]
            for p in candidate_paths:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                        logger.info(f"已刪除舊結果檔: {p}")
                except Exception as clean_e:
                    logger.warning(f"刪除舊結果檔失敗 {p}: {clean_e}")
        except Exception as pre_e:
            logger.warning(f"處理前清理舊結果時發生問題: {pre_e}")

        # 更新狀態
        status_messages = get_status_messages(language)
        status_manager.create(
            filename,
            {
                "status": status_messages['processing'],
                "status_code": "processing",
                "progress": 0,
                "detail": status_messages['start_processing'],
                "timestamp": time.time(),
                "run_token": run_token,
                "start_time": time.time(),
                "requested_note_style": requested_style or None,
            },
        )
        
        # 使用asyncio.create_task來確保任務真正執行
        logger.info(f"🔥🔥🔥 [process_video] 準備創建背景任務 for {filename}")
        cancel_event = asyncio.Event()
        metrics_stop = threading.Event()
        task = asyncio.create_task(
            process_video_background(
                filename, 
                full_video_path,  # 使用轉換後的完整路徑
                effective_config,
                llm_config, 
                status_manager, 
                with_images, 
                device,
                parse_audio,
                language,
                include_japanese,
                model_override=model,
                cancel_event=cancel_event,
                metrics_stop=metrics_stop,
            )
        )
        await register_active_task(filename, task, cancel_event=cancel_event, metrics_stop=metrics_stop)
        logger.info(f"🔥 [process_video] 任務已創建,task對象: {task}")
        
        logger.info(f"視頻處理任務已啟動: {filename}")
        return {
            "status": "started", 
            "message": "視頻處理已啟動", 
            "filename": filename,
            "device": device,
            "note_style": requested_style or None,
            "runtime": runtime_state,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"處理視頻時出錯: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"處理視頻時出錯: {str(e)}")

def safe_int(val):
    """安全轉換為整數"""
    try:
        return int(val)
    except Exception:
        try:
            return int(float(val))
        except Exception:
            return None

def collect_system_metrics(
    filename: str,
    stop_event: threading.Event,
    status_dict: StatusManager | None = None,
    interval_sec: float = 1.0,
) -> None:
    """Collect host metrics at a fixed interval and persist to disk."""
    try:
        import time

        metrics_dir = os.path.join(log_dir, "system_metrics")
        os.makedirs(metrics_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(filename))[0]
        out_path = os.path.join(metrics_dir, f"{base}.jsonl")
        monitored_paths = resolve_monitored_paths()

        while not stop_event.is_set():
            loop_start = time.perf_counter()
            snapshot = capture_snapshot(monitored_paths)
            summary = snapshot.get("summary", {}) or {}
            compact_metrics = {
                "ts": snapshot.get("ts"),
                "timestamp": snapshot.get("timestamp"),
                "cpu_percent": summary.get("cpu_percent"),
                "ram_percent": summary.get("ram_percent"),
                "gpu_util_percent": summary.get("gpu_util_percent"),
                "gpu_mem_used_mb": summary.get("gpu_mem_used_mb"),
                "gpu_mem_total_mb": summary.get("gpu_mem_total_mb"),
                "status": snapshot.get("status"),
            }

            try:
                with open(out_path, "a", encoding="utf-8") as handle:
                    handle.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
            except Exception as exc:
                logger.debug(f"[metrics] write snapshot failed: {exc}")

            if isinstance(status_dict, StatusManager):
                try:
                    status_dict.update(
                        filename,
                        {
                            "metrics": compact_metrics,
                            "host_metrics": snapshot,
                        },
                    )
                except Exception as exc:
                    logger.debug(f"[metrics] status update failed: {exc}")
                try:
                    status_dict.set_meta("latest_host_metrics", snapshot)
                except Exception as exc:
                    logger.debug(f"[metrics] set meta failed: {exc}")

            elapsed = time.perf_counter() - loop_start
            wait_sec = max(interval_sec - elapsed, 0.1)
            stop_event.wait(wait_sec)
    except Exception as e:
        logger.warning(f"collect_system_metrics failed: {e}")

async def process_video_background(
    filename: str,
    video_path: str,
    config: dict,
    llm_config: dict,
    status_manager: StatusManager,
    with_images: bool,
    device: str,
    parse_audio: bool,
    language: str = "zh-TW",
    include_japanese: bool = True,
    model_override: Optional[str] = None,
    cancel_event: Optional[asyncio.Event] = None,
    metrics_stop: Optional[threading.Event] = None,
):
    """在背景中處理視頻"""
    logger.info(f"⭐⭐⭐ [背景任務] 開始處理視頻: {filename} ⭐⭐⭐")
    logger.info(f"⭐ [背景任務] video_path: {video_path}")
    logger.info(f"⭐ [背景任務] parse_audio: {parse_audio}, language: {language}")

    cancel_event = cancel_event or asyncio.Event()
    metrics_stop = metrics_stop or threading.Event()
    metrics_thread = threading.Thread(
        target=collect_system_metrics,
        args=(filename, metrics_stop, status_manager),
        daemon=True,
    )
    metrics_thread.start()
    try:
        if _is_cancelled_status(filename, cancel_event):
            raise asyncio.CancelledError()

        effective_llm_config = copy.deepcopy(llm_config)
        if model_override:
            logger.info("使用請求覆寫模型: %s", model_override)
            for key in ("scene_model", "image_model", "final_model"):
                effective_llm_config[key] = model_override
        final_note, base_name, structured_payload, note_metadata = await summarize(
            filename,
            video_path,
            config,
            effective_llm_config,
            status_manager,
            with_images,
            device,
            parse_audio=parse_audio,
            language=language,
            include_japanese=include_japanese,
        )

        if _is_cancelled_status(filename, cancel_event):
            raise asyncio.CancelledError()

        result_path = os.path.join(output_root_str, f'{base_name}.md')
        json_result_path = os.path.join(output_root_str, f'{base_name}.json')
        os.makedirs(os.path.dirname(result_path), exist_ok=True)

        # 🔧 清理 Markdown 內容:修復代碼塊、移除 HTML 標籤
        from utils.markdown_cleaner import clean_markdown
        cleaned_note = clean_markdown(final_note)

        with open(result_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_note)

        # 🔧 修正: 判斷筆記類型並決定 JSON 處理策略
        note_style = (note_metadata or {}).get("note_style", "blueprint")
        is_vlm_note = note_style == "blueprint"
        try:
            import json as _json
            persisted_payload = dict(structured_payload) if isinstance(structured_payload, dict) else {}

            if is_vlm_note:
                persisted_payload.setdefault("quality", "good")
                persisted_payload.setdefault("ocrConfidence", 0.85)
                persisted_payload["message"] = persisted_payload.get("message", "VLM 筆記已成功生成")
                persisted_payload["noteLength"] = len(final_note)
                persisted_payload["timestamp"] = time.time()
                persisted_payload["isVlmNote"] = True
                persisted_payload.setdefault("useMarkdown", True)
                logger.info("✅ [背景任務] 檢測到 VLM 筆記格式，整合結構化資訊")
            elif persisted_payload and persisted_payload.get("quality") != "poor":
                persisted_payload.setdefault("message", "結構化筆記已生成")
                persisted_payload.setdefault("timestamp", time.time())
                persisted_payload.setdefault("useMarkdown", True)
                persisted_payload.setdefault("isVlmNote", is_vlm_note)
                logger.info(f"✅ [背景任務] 使用結構化數據，quality: {persisted_payload.get('quality')}")
            else:
                persisted_payload = {
                    "quality": "fair",
                    "message": "處理完成但品質有限",
                    "noteLength": len(final_note),
                    "timestamp": time.time(),
                    "useMarkdown": True,
                    "noteStyle": note_style,
                    "isVlmNote": is_vlm_note,
                }
                logger.warning("⚠️ [背景任務] 降級數據，創建基本狀態")

            persisted_payload.setdefault("noteStyle", note_style)
            persisted_payload.setdefault("isVlmNote", is_vlm_note)
            persisted_payload.setdefault("useMarkdown", True)
            json_data = persisted_payload

            with open(json_result_path, 'w', encoding='utf-8') as jf:
                _json.dump(json_data, jf, ensure_ascii=False, indent=2)
            logger.info(f"✅ [背景任務] JSON 狀態文件已保存: {json_result_path}")
        except Exception as json_err:
            logger.warning(f"[背景任務] 保存結構化結果 JSON 失敗: {json_err}")

        status_messages = get_status_messages(language)
        status_manager.update(
            filename,
            {
                "status": status_messages['completed'],
                "status_code": "completed",
                "progress": 100,
                "detail": status_messages['processing_complete'],
                "result_path": result_path,
            },
        )
        if structured_payload:
            status_manager.update(filename, {"structured": structured_payload})
        if note_metadata:
            status_manager.update(filename, {"note_metadata": note_metadata})
        status_manager.update(filename, {"result_json_path": json_result_path})
    except asyncio.CancelledError:
        _mark_task_cancelled(filename, "使用者取消處理")
        logger.info(f"[背景任務] 任務已取消: {filename}")
        raise
    except Exception as e:
        error_msg = str(e)
        error_trace = traceback.format_exc()
        logger.error(f"[背景任務] 處理視頻時出錯: {error_msg}")
        logger.error(f"[背景任務] 錯誤堆疊: {error_trace}")
        status_manager.update(
            filename,
            {
                "status": "錯誤",
                "status_code": "error",
                "progress": 100,
                "detail": f"處理失敗: {error_msg}",
                "error": error_msg,
                "error_trace": error_trace,
            },
        )
    finally:
        metrics_stop.set()
        try:
            metrics_thread.join(timeout=3)
        except Exception:
            pass
@app.get("/api/status/{filename}")
async def get_status(filename: str):
    """獲取處理狀態；若找不到精確鍵，嘗試去副檔名比對；最後提供最近一次 metrics 快照（若有）。"""
    logger.info(f"🔍 [get_status] 獲取處理狀態: {filename}")
    key = filename.replace('\\', '/')

    status_data = status_manager.get(key)
    status_key = key
    if not status_data:
        base = os.path.basename(key)
        if status_manager.contains(base):
            status_data = status_manager.get(base)
            status_key = base
        else:
            similar = status_manager.find_similar(key)
            if similar:
                status_key, status_data = similar

    if status_data:
        status_data.setdefault("task_id", status_key)
        status_data.setdefault("metrics", status_data.get("metrics") or status_manager.latest_metrics())
        current_time = time.time()
        start_time = status_data.get("start_time", current_time)
        status_data["elapsed_time"] = max(0.0, current_time - float(start_time))
        status_data["timestamp"] = current_time
        if "host_metrics" not in status_data:
            latest_host = status_manager.get_meta("latest_host_metrics")
            if latest_host:
                status_data["host_metrics"] = latest_host
        return status_data

    # StatusManager 中沒有狀態，檢查實際輸出文件
    logger.info(f"🔎 [get_status] StatusManager 中無狀態，檢查實際輸出文件: {filename}")
    base_name = os.path.splitext(os.path.basename(key))[0]
    
    # 檢查筆記文件是否存在
    note_paths = [
        os.path.join(notes_root_str, f'{base_name}.md'),
        os.path.join(notes_root_str, filename.replace('.mp4', '.md')),
        os.path.join(output_root_str, f'{base_name}.md')
    ]
    
    for note_path in note_paths:
        if os.path.exists(note_path):
            logger.info(f"✅ [get_status] 找到已完成的筆記文件: {note_path}")
            return {
                "status": "完成",
                "status_code": "completed",
                "progress": 100,
                "detail": "處理已完成（從文件系統檢測）",
                "result_path": note_path,
                "timestamp": time.time(),
                "metrics": status_manager.latest_metrics(),
                "host_metrics": status_manager.get_meta("latest_host_metrics"),
            }
    
    # 檢查圖片資料夾是否存在（部分完成的情況）
    image_dirs = [
        os.path.join(output_root_str, 'images', base_name),
        os.path.join(output_root_str, 'images', filename)
    ]
    
    for image_dir in image_dirs:
        if os.path.exists(image_dir):
            logger.warning(f"⚠️ [get_status] 找到圖片資料夾但無筆記文件: {image_dir}")
            return {
                "status": "部分完成",
                "status_code": "partial",
                "progress": 50,
                "detail": "影片已分析但筆記生成未完成，請重新處理",
                "timestamp": time.time(),
                "metrics": status_manager.latest_metrics(),
                "host_metrics": status_manager.get_meta("latest_host_metrics"),
            }

    latest_metrics = status_manager.latest_metrics()
    available_keys = list(status_manager.keys())[:5]
    logger.warning(f"❌ [get_status] 未找到處理狀態和輸出文件: {key}, 可用的鍵: {available_keys}")
    return {
        "status": "未知",
        "status_code": "unknown",
        "progress": 0,
        "detail": "未找到處理狀態",
        "metrics": latest_metrics,
        "host_metrics": status_manager.get_meta("latest_host_metrics"),
    }


@app.get("/api/system/metrics")
async def api_system_metrics():
    snapshot = capture_snapshot()
    try:
        status_manager.set_meta("latest_host_metrics", snapshot)
    except Exception:
        pass
    return {"status": "ok", "metrics": snapshot}

@app.delete("/api/status/{filename}")
async def clear_status(filename: str):
    """清除卡住的處理狀態"""
    logger.info(f"🗑️ [clear_status] 清除處理狀態: {filename}")
    key = filename.replace('\\', '/')
    
    # 嘗試多種鍵名格式
    keys_to_try = [
        key,
        os.path.basename(key),
        key.replace(' ', '%20'),
        key.replace('%20', ' ')
    ]
    
    removed = False
    for try_key in keys_to_try:
        if status_manager.contains(try_key):
            status_manager.remove(try_key)
            logger.info(f"✅ [clear_status] 成功移除狀態: {try_key}")
            removed = True
            break
    
    if not removed:
        # 嘗試模糊匹配
        similar = status_manager.find_similar(key)
        if similar:
            similar_key, _ = similar
            status_manager.remove(similar_key)
            logger.info(f"✅ [clear_status] 成功移除相似鍵的狀態: {similar_key}")
            removed = True
    
    if removed:
        return {"success": True, "message": f"已清除 {filename} 的處理狀態"}
    else:
        available_keys = list(status_manager.keys())[:10]
        logger.warning(f"⚠️ [clear_status] 未找到要清除的狀態: {key}, 可用鍵: {available_keys}")
        return {"success": False, "message": f"未找到 {filename} 的處理狀態", "available_keys": available_keys}

@app.post("/api/cancel/{task_id}")
async def cancel_task(task_id: str):
    """
    取消正在執行的任務
    
    此端點會將任務標記為「已取消」，背景處理函數會檢查此標誌並停止處理。
    
    Args:
        task_id: 任務 ID (通常是檔案名稱)
    
    Returns:
        成功或失敗的 JSON 回應
    """
    logger.info(f"🚫 [cancel_task] 嘗試取消任務: {task_id}")
    key = task_id.replace('\\', '/')
    
    # 嘗試多種鍵名格式
    keys_to_try = [
        key,
        os.path.basename(key),
        key.replace(' ', '%20'),
        key.replace('%20', ' ')
    ]
    
    cancelled = False
    matched_key = None
    
    for try_key in keys_to_try:
        if status_manager.contains(try_key):
            if status_manager.mark_cancelled(try_key):
                logger.info(f"✅ [cancel_task] 成功標記任務為已取消: {try_key}")
                cancelled = True
                matched_key = try_key
                break
    
    if not cancelled:
        # 嘗試模糊匹配
        similar = status_manager.find_similar(key)
        if similar:
            similar_key, _ = similar
            if status_manager.mark_cancelled(similar_key):
                logger.info(f"✅ [cancel_task] 成功標記相似鍵的任務為已取消: {similar_key}")
                cancelled = True
                matched_key = similar_key
    
    if cancelled:
        # 更新狀態詳情
        status_manager.update(matched_key, {
            "detail": "用戶已取消任務",
            "progress": status_manager.get(matched_key).get("progress", 0),
            "timestamp": time.time()
        })
        return {
            "success": True, 
            "message": f"已取消任務 {task_id}",
            "task_id": matched_key,
            "note": "背景處理會在下次檢查時停止"
        }
    else:
        available_keys = list(status_manager.keys())[:10]
        logger.warning(f"⚠️ [cancel_task] 未找到要取消的任務: {key}, 可用鍵: {available_keys}")
        return {
            "success": False, 
            "message": f"未找到任務 {task_id}",
            "available_keys": available_keys
        }

@app.get("/api/folder-status/{task_id}")
async def get_folder_status(task_id: str):
    """獲取資料夾處理狀態"""
    logger.info(f"獲取資料夾處理狀態: {task_id}")
    try:
        if status_manager.contains(task_id):
            status_info = status_manager.get(task_id)
            current_time = time.time()
            start_time = status_info.get('start_time', current_time)
            elapsed_time = current_time - start_time
            status_info['elapsed_time'] = elapsed_time
            status_info['timestamp'] = current_time
            logger.debug(f"資料夾處理狀態: {status_info}")
            return status_info
        else:
            logger.info(f"未找到資料夾處理狀態: {task_id}")
            return {
                "status": "unknown",
                "progress": 0,
                "detail": "未找到處理狀態",
                "timestamp": time.time(),
                "elapsed_time": 0
            }
    except Exception as e:
        logger.error(f"獲取資料夾狀態失敗: {e}")
        return {
            "status": "error",
            "progress": 0,
            "detail": f"獲取狀態失敗: {str(e)}",
            "timestamp": time.time(),
            "elapsed_time": 0
        }

def perform_image_sync(language: str = 'zh-TW') -> dict:
    """實際執行圖片同步的內部函式。支援 Docker 與本地環境、遞迴複製與 HEIC 簡易處理。"""
    src_dir = output_images_root
    container_frontend_dir = Path("/app/source/frontend/public/images")
    local_frontend_dir = FRONTEND_PUBLIC_IMAGES_DIR
    dst_dir_path = container_frontend_dir if container_frontend_dir.exists() else local_frontend_dir
    dst_dir = str(dst_dir_path)

    logger.info(f"圖片同步: 從 {src_dir} 到 {dst_dir}")

    if not os.path.exists(src_dir):
        logger.warning(f"來源資料夾不存在: {src_dir}")
        return {
            "status": "error",
            "error": "來源資料夾不存在",
            "count": 0,
            "files": [],
            "src_dir": src_dir,
            "dst_dir": dst_dir,
            "message": get_status_messages(language).get('image_sync_source_missing', '來源資料夾不存在')
        }

    os.makedirs(dst_dir, exist_ok=True)
    count = 0
    copied_files = []

    try:
        # 先處理前端目錄中可能存在的 HEIC，簡單複製並改名為 _converted.jpg（實際轉換需額外庫）
        frontend_images_dir = str(local_frontend_dir)
        if os.path.exists(frontend_images_dir):
            for fname in os.listdir(frontend_images_dir):
                if fname.lower().endswith(('.heic', '.HEIC')):
                    src_file = os.path.join(frontend_images_dir, fname)
                    converted_name = fname.replace('.HEIC', '_converted.jpg').replace('.heic', '_converted.jpg')
                    dst_file = os.path.join(dst_dir, converted_name)
                    if not os.path.exists(dst_file):
                        try:
                            shutil.copy2(src_file, dst_file)
                            count += 1
                            copied_files.append(converted_name)
                            logger.info(f"複製HEIC圖片: {fname} -> {converted_name}")
                        except Exception as e:
                            logger.error(f"複製HEIC文件失敗: {e}")

        # 遞迴複製 output/images
        for root, dirs, files in os.walk(src_dir):
            for fname in files:
                if fname.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp')):
                    src_file = os.path.join(root, fname)
                    rel_path = os.path.relpath(src_file, src_dir)
                    dst_file = os.path.join(dst_dir, rel_path)
                    os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                    if not os.path.exists(dst_file) or os.path.getmtime(src_file) > os.path.getmtime(dst_file):
                        shutil.copy2(src_file, dst_file)
                        count += 1
                        copied_files.append(rel_path)
                        logger.debug(f"同步圖片: {rel_path}")

        logger.info(f"圖片同步完成, 共同步 {count} 個文件")
        status_messages = get_status_messages(language)
        return {
            "status": "success",
            "count": count,
            "files": copied_files,
            "src_dir": src_dir,
            "dst_dir": dst_dir,
            "message": status_messages.get('image_sync_complete', '圖片同步完成')
        }
    except Exception as e:
        logger.error(f"圖片同步失敗: {e}")
        return {
            "status": "error",
            "error": str(e),
            "count": count,
            "files": copied_files,
            "src_dir": src_dir,
            "dst_dir": dst_dir,
            "message": f"圖片同步失敗: {str(e)}"
        }

@app.post("/api/sync-images")
async def sync_images(request: Request):
    """同步圖片到前端目錄（JSON 請求，支援 language）"""
    logger.info("開始同步圖片")
    try:
        try:
            data = await request.json()
            language = data.get('language', 'zh-TW')
        except Exception as json_error:
            logger.warning(f"JSON解析失敗, 使用默認語言: {json_error}")
            language = 'zh-TW'

        result = perform_image_sync(language)
        # 根據是否錯誤決定 HTTP 狀態碼
        if result.get("status") == "error":
            return JSONResponse(status_code=500, content=result)
        return result
    except Exception as e:
        logger.error(f"圖片同步失敗: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"圖片同步失敗: {str(e)}"}
        )

@app.delete("/api/cancel-task/{task_id}")
async def cancel_task(task_id: str, run_token: Optional[str] = None):
    """取消處理任務（後端實際中斷背景任務）。"""
    logger.info(f"請求取消任務: {task_id}")
    try:
        resolved_id = _resolve_task_key(task_id)
        snapshot = status_manager.get(resolved_id, {})
        existing_token = snapshot.get("run_token")
        if run_token and existing_token and existing_token != run_token:
            logger.warning(f"取消請求 run_token 不匹配: {resolved_id} (existing={existing_token}, incoming={run_token})")

        cancelled = await cancel_active_task(resolved_id)
        if cancelled or status_manager.contains(resolved_id):
            _mark_task_cancelled(resolved_id, f"任務 {resolved_id} 已取消")
            logger.info(f"取消任務: {resolved_id} (active={cancelled})")
            return JSONResponse({"status": "cancelled", "message": f"任務 {resolved_id} 已取消"})

        logger.warning(f"要取消的任務不存在: {resolved_id}")
        return JSONResponse({"status": "not_found", "message": "任務不存在"})
    except Exception as e:
        logger.error(f"取消任務失敗: {e}")
        return JSONResponse({"status": "error", "message": f"取消任務失敗: {str(e)}"})

# 刪除重複的 get_result 函數定義，使用下面更完整的版本

@app.post("/api/upload-image")
async def upload_image(file: UploadFile = File(...)):
    """上傳講義圖片"""
    try:
        filename = file.filename
        # 檢查文件類型
        if not filename.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp")):
            raise HTTPException(status_code=400, detail="不支援的圖片格式")
        
        save_path = os.path.join(IMAGE_FOLDER, filename)
        with open(save_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"圖片上傳成功: {save_path}")
        return {"filename": filename, "message": "圖片上傳成功"}
    except Exception as e:
        logger.error(f"圖片上傳失敗: {e}")
        raise HTTPException(status_code=500, detail=f"圖片上傳失敗: {str(e)}")

@app.post("/api/process-folder-images")
async def process_folder_images(
    folder_path: str = Form(default=""),
    device: str = Form(default="gpu"),
    language: str = Form(default="zh-TW"),
    include_japanese: bool = Form(default=True),
    language_mode: Optional[str] = Form(default=None),
    run_mode: str = Form(default="auto")  # auto|sync
):

    """批量處理資料夾中的所有圖片並合併成一份筆記"""
    logger.info(f"開始批量處理資料夾圖片: '{folder_path}' (device: {device})")

    language, include_japanese, resolved_mode = resolve_language_mode(
        language,
        include_japanese,
        language_mode,
    )
    if resolved_mode:
        logger.info(
            "language_mode=%s -> language=%s, include_japanese=%s",
            resolved_mode,
            language,
            include_japanese,
        )
    
    try:

        # 獲取圖片路徑配置（使用統一輔助，避免 paths_config.json 讀寫錯誤導致 500）
        paths_config = _read_paths_config()
        image_path = paths_config.get("image_path", "")
        if not image_path:
            raise HTTPException(status_code=400, detail="圖片路徑未設置, 請先在設置中配置圖片資料夾路徑")

        resolved_base_path, resolution = _resolve_media_directory(image_path)
        if not resolved_base_path:
            logger.error(
                "圖片根路徑無法訪問: %s (container: %s, normalized: %s)",
                image_path,
                resolution.container_path if resolution else "未知",
                resolution.normalized_path if resolution else "未知",
            )
            raise HTTPException(status_code=400, detail="圖片根路徑不可用，請重新設定")

        if folder_path and folder_path.strip():
            full_folder_path = os.path.join(resolved_base_path, folder_path.strip())
        else:
            full_folder_path = resolved_base_path
        
        logger.info(f"完整資料夾路徑: {full_folder_path}")
        
        if not os.path.exists(full_folder_path):
            raise HTTPException(status_code=404, detail=f"資料夾不存在: {full_folder_path}")
        
        # 收集資料夾中的所有圖片(只掃描當前資料夾, 不包含子資料夾)
        image_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.heic', '.heif')
        folder_images = []
        
        logger.info(f"掃描資料夾: {full_folder_path}")
        if not os.path.isdir(full_folder_path):
            raise HTTPException(status_code=404, detail=f"路徑不是資料夾: {folder_path}")
        
        # 只掃描當前資料夾, 不遞歸子資料夾
        for file in os.listdir(full_folder_path):
            file_path = os.path.join(full_folder_path, file)
            # 確保是文件而不是資料夾
            if os.path.isfile(file_path) and file.lower().endswith(image_extensions):
                # 計算相對於圖片根目錄的路徑
                relative_path = os.path.relpath(file_path, resolved_base_path)
                folder_images.append({
                    'filename': file,
                    'relative_path': relative_path,
                    'full_path': file_path
                })
                logger.debug(f"找到圖片: {file} -> {relative_path}")
        
        if not folder_images:
            raise HTTPException(status_code=404, detail=f"資料夾中沒有找到圖片: {folder_path}")
        
        logger.info(f"找到 {len(folder_images)} 張圖片需要處理: {[img['filename'] for img in folder_images]}")
        
        # 啟動背景任務處理
        if folder_path and folder_path.strip():
            folder_name = folder_path.strip().replace('/', '_').replace('\\', '_')
        else:
            folder_name = 'root'
        task_id = f"folder_{folder_name}_{int(time.time())}"
        
        # 初始化狀態
        status_messages = get_status_messages(language)
        status_manager.create(task_id, {
            'status': status_messages['preparing'],
            'status_code': 'preparing',
            'progress': 0,
            'detail': f'{status_messages["preparing"]} {len(folder_images)} 張圖片...',
            'timestamp': time.time(),
            'start_time': time.time(),
            'elapsed_time': 0,
            'folder_path': folder_path,
            'total_images': len(folder_images)
        })
        
        # 同步模式：直接在當前請求中執行，便於先驗證流程可通
        if (run_mode or "").lower() == "sync":
            logger.info(f"[SYNC] 以同步模式處理資料夾: {folder_path} (task_id={task_id})")
            await process_folder_images_background(
                folder_images,
                folder_path,
                device,
                task_id,
                status_manager,
                language,
                include_japanese,
                language_mode=resolved_mode,
            )

            final_status = status_manager.get(task_id, {})
            return JSONResponse({
                "status": final_status.get("status", "completed"),
                "status_code": final_status.get("status_code", "completed"),
                "progress": final_status.get("progress", 100),
                "detail": final_status.get("detail", "處理完成"),
                "task_id": task_id,
                "result_file": final_status.get("result_file"),
            })
        
        # 背景模式：非阻塞
        folder_cancel_event = asyncio.Event()
        folder_task = asyncio.create_task(process_folder_images_background(
            folder_images,
            folder_path,
            device,
            task_id,
            status_manager,
            language,
            include_japanese,
            language_mode=resolved_mode,
            cancel_event=folder_cancel_event,
        ))

        await register_active_task(task_id, folder_task, cancel_event=folder_cancel_event)
        
        return JSONResponse({
            "status": "started",
            "task_id": task_id,
            "message": f"開始批量處理資料夾 {folder_path} 中的 {len(folder_images)} 張圖片"
        })
        
    except Exception as e:
        logger.error(f"批量處理資料夾圖片失敗: {e}")
        raise HTTPException(status_code=500, detail=f"批量處理失敗: {str(e)}")

# 第一個重複的圖片處理API已刪除，使用下方更完整的版本

# Remove static mount for /images; the dynamic endpoint `/images/{image_path:path}`
# will serve images by searching multiple directories. This avoids shadowing issues
# in development and supports nested folders and URL-encoded paths.

@app.get("/images/{image_path:path}")
async def serve_image(image_path: str):
    """直接提供圖片服務作為備用方案"""
    try:
        # 解碼 URL，處理 %20、中文、空白等
        from urllib.parse import unquote
        # 多次解碼，處理瀏覽器重複編碼與中文/空白/括號
        decoded_path = image_path
        for _ in range(2):
            decoded_path = unquote(decoded_path)
        decoded_path = decoded_path.lstrip('/').replace('..', '')
        logger.info(f"圖片請求: raw='{image_path}', decoded='{decoded_path}'")
        
        # 構建完整的圖片路徑 - 檢查多個可能的目錄（包含外部掛載）
        possible_dirs = [
            output_images_root,
            str(data_dir / "images"),
            str(FRONTEND_PUBLIC_IMAGES_DIR),
            # 外部來源（docker-compose 有掛載）
            str(data_dir / "external" / "f" / "講義圖片"),
            str(data_dir / "external" / "f"),
            str(data_dir / "external" / "c" / "Users"),
        ]
        
        def _resolve_scene_fallback(path: str) -> str | None:
            match = re.match(r"^(.*?/)?scene_(\d{3})\.(jpg|jpeg|png|webp|bmp)$", path, re.IGNORECASE)
            if not match:
                return None
            prefix = match.group(1) or ""
            scene_num = int(match.group(2))
            ext = match.group(3)
            # 優先嘗試 +1（常見於去重刪掉首張 scene_000）
            for delta in (1, -1, 2, -2):
                candidate_num = scene_num + delta
                if candidate_num < 0:
                    continue
                yield f"{prefix}scene_{candidate_num:03d}.{ext}"

        for base_dir in possible_dirs:
            full_path = os.path.join(base_dir, decoded_path)
            logger.info(f"檢查路徑: {full_path}, 存在: {os.path.exists(full_path)}")
            
            if os.path.exists(full_path):
                # 檢查文件是否為支援的圖片格式
                supported_formats = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.heic', '.HEIC')
                if not full_path.lower().endswith(supported_formats):
                    logger.warning(f"不支援的圖片格式: {full_path}")
                    continue
                
                # 確定 MIME 類型
                mime_type = "image/jpeg"
                if full_path.lower().endswith('.png'):
                    mime_type = "image/png"
                elif full_path.lower().endswith('.gif'):
                    mime_type = "image/gif"
                elif full_path.lower().endswith('.webp'):
                    mime_type = "image/webp"
                elif full_path.lower().endswith('.bmp'):
                    mime_type = "image/bmp"
                elif full_path.lower().endswith(('.heic', '.HEIC')):
                    mime_type = "image/heic"
                
                logger.info(f"提供圖片: {full_path}, MIME: {mime_type}")
                # 檢查文件大小
                file_size = os.path.getsize(full_path)
                logger.info(f"圖片文件大小: {file_size} bytes")
                
                return FileResponse(
                    full_path,
                    media_type=mime_type,
                    headers={
                        "Cache-Control": "public, max-age=3600",
                        "Content-Length": str(file_size)
                    }
                )

            # 兼容舊結果：若 scene_000 不存在，嘗試鄰近場景檔名
            for fallback_path in _resolve_scene_fallback(decoded_path) or []:
                fallback_full_path = os.path.join(base_dir, fallback_path)
                if os.path.exists(fallback_full_path):
                    logger.warning(
                        "圖片缺失自動回退: requested=%s fallback=%s",
                        decoded_path,
                        fallback_path,
                    )
                    return FileResponse(
                        fallback_full_path,
                        media_type="image/jpeg",
                        headers={
                            "Cache-Control": "public, max-age=3600",
                            "Content-Length": str(os.path.getsize(fallback_full_path))
                        }
                    )
        
        # 找不到圖片時返回詳細的錯誤訊息
        logger.error(f"圖片未找到: {decoded_path}")
        logger.error(f"已檢查目錄: {possible_dirs}")
        raise HTTPException(
            status_code=404,
            detail={
                "error": "圖片未找到",
                "requested_path": decoded_path,
                "checked_directories": possible_dirs
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"圖片服務錯誤: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"圖片服務錯誤: {str(e)}")

@app.head("/images/{image_path:path}")
async def image_head(image_path: str):
    """為圖片提供HEAD請求支援（用於前端檢查圖片是否存在）"""
    from urllib.parse import unquote
    decoded_path = image_path
    for _ in range(2):
        decoded_path = unquote(decoded_path)
    decoded_path = decoded_path.lstrip('/').replace('..', '')
    
    possible_dirs = [
        output_images_root,
        str(data_dir / "images"),
        str(FRONTEND_PUBLIC_IMAGES_DIR),
        str(data_dir / "external" / "f" / "講義圖片"),
        str(data_dir / "external" / "f"),
        str(data_dir / "external" / "c" / "Users"),
    ]
    
    def _resolve_scene_fallback(path: str):
        match = re.match(r"^(.*?/)?scene_(\d{3})\.(jpg|jpeg|png|webp|bmp)$", path, re.IGNORECASE)
        if not match:
            return []
        prefix = match.group(1) or ""
        scene_num = int(match.group(2))
        ext = match.group(3)
        candidates = []
        for delta in (1, -1, 2, -2):
            candidate_num = scene_num + delta
            if candidate_num >= 0:
                candidates.append(f"{prefix}scene_{candidate_num:03d}.{ext}")
        return candidates

    for base_dir in possible_dirs:
        full_path = os.path.join(base_dir, decoded_path)
        if os.path.exists(full_path):
            file_size = os.path.getsize(full_path)
            return Response(headers={
                "Content-Length": str(file_size),
                "Content-Type": "image/jpeg"
            })

        for fallback_path in _resolve_scene_fallback(decoded_path):
            fallback_full_path = os.path.join(base_dir, fallback_path)
            if os.path.exists(fallback_full_path):
                file_size = os.path.getsize(fallback_full_path)
                return Response(headers={
                    "Content-Length": str(file_size),
                    "Content-Type": "image/jpeg"
                })
    
    raise HTTPException(status_code=404)

# 檢查前端dist目录是否存在
if FRONTEND_DIST_DIR.exists():
    # 如果存在, 则挂载静态文件服务
    app.mount("/vue", StaticFiles(directory=str(FRONTEND_DIST_DIR), html=True), name="frontend")
else:
    # 如果不存在, 则提供一个简单的根路径响应
    @app.get("/")
    async def root():
        return {"message": "Frontend dist directory not found. Please build the frontend first."}

# 啟動時嘗試載入保存的路徑配置
try:
    cached_paths = media_path_service.refresh()

    video_path = cached_paths.get("video_path", "")
    if video_path:
        video_resolution = media_path_service.resolve(os.path.expandvars(video_path))
        video_candidate = video_resolution.accessible_path or video_resolution.container_path
        if video_candidate and os.path.exists(video_candidate):
            UPLOAD_FOLDER = video_candidate
            logger.info(f"啟動時載入影片路徑: {video_path} -> {video_candidate}")
        else:
            logger.warning(f"保存的影片路徑無法訪問: {video_candidate or video_path}")

    image_path = cached_paths.get("image_path", "")
    if image_path:
        image_resolution = media_path_service.resolve(os.path.expandvars(image_path))
        image_candidate = image_resolution.accessible_path or image_resolution.container_path
        if image_candidate and os.path.exists(image_candidate):
            image_folder = image_candidate
            logger.info(f"啟動時載入圖片路徑: {image_path} -> {image_candidate}")
        else:
            logger.warning(f"保存的圖片路徑無法訪問: {image_candidate or image_path}")

except Exception as e:
    logger.error(f"載入路徑配置失敗: {e}")
    media_path_service.paths_config.clear()
    media_path_service.paths_config.update({"video_path": "", "image_path": ""})

async def process_folder_images_background(
    image_paths,
    folder_path,
    device,
    task_id,
    status_manager: StatusManager,
    language="zh-TW",
    include_japanese=True,
    language_mode: Optional[str] = None,
    cancel_event: Optional[asyncio.Event] = None,
):

    """背景處理資料夾中的所有圖片"""
    try:
        cancel_event = cancel_event or asyncio.Event()
        logger.info(f"[{task_id}] 開始背景處理 {len(image_paths)} 張圖片")
        
        # 保險：確保 language 與 status_messages 一定存在，避免 NameError
        language = language or "zh-TW"
        try:
            status_messages = get_status_messages(language)
        except Exception:
            status_messages = get_status_messages("zh-TW")
        
        if _is_cancelled_status(task_id, cancel_event) or not status_manager.contains(task_id):
            _mark_task_cancelled(task_id, f"任務 {task_id} 已取消")
            logger.info(f"[{task_id}] 任務已被取消, 停止處理")
            return

        total_images = len(image_paths)
        status_manager.update(task_id, {
            'status': status_messages['processing'],
            'status_code': 'processing',
            'progress': 5,
            'detail': status_messages['start_folder_processing'],
            'total_images': total_images
        })

        # 處理每張圖片
        all_results = []
        
        for i, image_info in enumerate(image_paths):
            try:
                # 檢查任務是否已被取消
                if _is_cancelled_status(task_id, cancel_event) or not status_manager.contains(task_id):
                    _mark_task_cancelled(task_id, f"任務 {task_id} 已取消")
                    logger.info(f"[{task_id}] 任務已被取消, 停止處理第 {i+1} 張圖片")
                    return
                
                # 處理單張圖片
                filename = image_info['filename']
                relative_path = image_info['relative_path']
                full_path = image_info['full_path']
                
                # 階段1: OCR 文字識別
                progress_ocr = 10 + (i * 70 // total_images)
                status_manager.update(task_id, {
                    'progress': progress_ocr,
                    'detail': f'📸 [{i+1}/{total_images}] OCR 識別: {filename}',
                    'current_stage': 'ocr',
                    'current_file': filename
                })
                logger.info(f"[{task_id}] 處理圖片: {filename} (完整路徑: {full_path})")
                
                # 短暫延遲讓前端能夠顯示 OCR 階段
                await asyncio.sleep(0.3)
                
                # 階段2: LLM 多模態分析
                progress_llm = progress_ocr + (70 // total_images // 2)
                status_manager.update(task_id, {
                    'progress': progress_llm,
                    'detail': f'🤖 [{i+1}/{total_images}] LLM 分析: {filename}',
                    'current_stage': 'llm_analysis',
                    'current_file': filename
                })
                
                # 調用圖片處理函數 - 使用完整路徑
                from modules.summarize_image import summarize_image
                config = load_config(force_reload=True)
                llm_config = config.get('llm', {})
                
                # 使用完整路徑進行處理, 跳過OCR直接使用多模態模型
                result, base_name = await summarize_image(
                    full_path, config, llm_config, status_manager, device, skip_ocr=False, language=language, include_japanese=include_japanese
                )
                
                # 階段3: 格式化筆記
                progress_format = progress_llm + (70 // total_images // 2)
                status_manager.update(task_id, {
                    'progress': progress_format,
                    'detail': f'📝 [{i+1}/{total_images}] 格式化: {filename}',
                    'current_stage': 'formatting',
                    'current_file': filename
                })
                
                all_results.append({
                    'filename': filename,
                    'result': result,
                    'base_name': base_name
                })
                
                logger.info(f"[{task_id}] 完成處理: {filename}")
                
            except Exception as e:
                logger.error(f"[{task_id}] 處理圖片 {image_info} 失敗: {e}")
                logger.error(f"[{task_id}] 錯誤詳情: {traceback.format_exc()}")
                all_results.append({
                    'filename': image_info['filename'],
                    'result': f"處理失敗: {str(e)}",
                    'base_name': os.path.splitext(image_info['filename'])[0]
                })
        
        # 合併所有結果
        status_manager.update(task_id, {
            'progress': 85,
            'detail': '🔗 合併所有筆記內容...',
            'current_stage': 'merging'
        })
        
        combined_result = combine_image_results(all_results, folder_path, language, include_japanese)
        
        # 保存合併結果
        status_manager.update(task_id, {
            'progress': 90,
            'detail': '💾 保存筆記文件...',
            'current_stage': 'saving'
        })
        if folder_path and folder_path.strip():
            folder_name = folder_path.strip().replace('/', '_').replace('\\', '_')
        else:
            folder_name = 'root'
        result_filename = f"{folder_name}_combined.md"
        result_path = os.path.join(notes_root_str, result_filename)
        
        # 確保保存目錄存在
        os.makedirs(notes_root_str, exist_ok=True)
        
        # 🔧 清理 Markdown 內容:修復代碼塊、移除 HTML 標籤
        from utils.markdown_cleaner import clean_markdown
        cleaned_combined = clean_markdown(combined_result)
        
        with open(result_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_combined)
        
        logger.info(f"[{task_id}] 合併結果已保存: {result_path}")
        
        # 同步圖片到前端
        status_manager.update(task_id, {
            'progress': 95,
            'detail': '🖼️ 同步圖片到前端...',
            'current_stage': 'syncing_images'
        })
        
        # 完成
        status_manager.update(task_id, {
            'status': status_messages['completed'],
            'status_code': 'completed',
            'progress': 100,
            'detail': f'✅ 完成! 已處理 {len(image_paths)} 張圖片',
            'current_stage': 'completed',
            'result_file': result_filename
        })
        
        logger.info(f"[{task_id}] 資料夾批量處理完成")
        
    except asyncio.CancelledError:
        _mark_task_cancelled(task_id, f"任務 {task_id} 已取消")
        logger.info(f"[{task_id}] 任務已取消")
        raise
    except Exception as e:
        logger.error(f"[{task_id}] 背景處理失敗: {e}")
        status_manager.update(task_id, {
            'status': '錯誤',
            'status_code': 'error',
            'progress': 100,
            'detail': f'處理失敗: {str(e)}'
        })

def combine_image_results(results, folder_path, language="zh-TW", include_japanese=True):
    """合併多個圖片處理結果 - 簡潔版本:圖片+筆記,圖片+筆記"""
    folder_display_name = folder_path or "根目錄"
    
    # 簡化的標題
    bilingual_titles = {
        "zh-TW": "雙語講義筆記",
        "zh-CN": "双语讲义笔记",
        "en": "Bilingual Lecture Notes",
        "ja": "日文＋翻訳講義ノート",
        "ko": "일본어+번역 강의 노트",
        "vi": "Ghi chú song ngữ",
        "my": "နှစ်ဘာသာ မှတ်စု",
        "mn": "Хоёр хэлний тэмдэглэл",
    }
    single_titles = {
        "zh-TW": "講義筆記",
        "zh-CN": "讲义笔记",
        "en": "Lecture Notes",
        "ja": "講義ノート",
        "ko": "강의 노트",
        "vi": "Ghi chú",
        "my": "မှတ်စု",
        "mn": "Тэмдэглэл",
    }
    title_suffix = (
        bilingual_titles.get(language, bilingual_titles["zh-TW"])
        if include_japanese
        else single_titles.get(language, single_titles["zh-TW"])
    )
    title = f"# 📚 {folder_display_name} - {title_suffix}"

    
    combined = f"{title}\n\n"
    
    # 依序處理每張圖片:圖片 → 筆記內容
    for i, result in enumerate(results, 1):
        note_content = (result.get('result') or "").strip()
        if not note_content:
            note_content = "_(尚未產生內容)_"

        combined += f"## 📖 圖片 {i}: {result['base_name']}\n\n"
        combined += f"{note_content}\n\n"

        if i < len(results):
            combined += "---\n\n"

    return combined

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

    uvicorn.run(app, host="0.0.0.0", port=8000)

    uvicorn.run(app, host="0.0.0.0", port=8000)

    uvicorn.run(app, host="0.0.0.0", port=8000)

@app.post("/api/process-image")
async def process_image(
    filename: str = Form(...),
    device: str = Form("gpu"),
    language: str = Form("zh-TW")
):
    """處理圖片並生成筆記"""
    try:
        logger.info(f"[DEBUG] 接收到圖片處理請求 - filename: {filename}")
        
        # 使用與 summarize_image 一致且健壯的路徑處理邏輯（統一輔助，避免 BOM/目錄掛載造成 500）
        if os.path.isabs(filename):
            image_path = filename
        else:
            paths_config = _read_paths_config()
            image_root = paths_config.get("image_path", "")
            if image_root:
                resolved_base_path, resolution = _resolve_media_directory(image_root)
                if resolved_base_path:
                    image_path = os.path.join(resolved_base_path, filename)
                else:
                    logger.warning(
                        "[DEBUG] 圖片根路徑不可用: %s (container: %s, normalized: %s)",
                        image_root,
                        resolution.container_path if resolution else "未知",
                        resolution.normalized_path if resolution else "未知",
                    )
                    image_path = os.path.join(IMAGE_FOLDER, filename)
                # 如果該路徑不存在，嘗試備選與舊有目錄
                if not os.path.exists(image_path):
                    backup_candidates = [
                        os.path.join('/app/images', filename),
                        os.path.join(IMAGE_FOLDER, filename)
                    ]
                    for bp in backup_candidates:
                        if os.path.exists(bp):
                            logger.info(f"[DEBUG] 配置路徑不存在, 使用備選路徑: {bp}")
                            image_path = bp
                            break
            else:
                # 回退到舊的硬編碼路徑
                image_path = os.path.join(IMAGE_FOLDER, filename)
        
        logger.info(f"[DEBUG] 構建的圖片路徑: {image_path}")
        logger.info(f"[DEBUG] 路徑是否存在: {os.path.exists(image_path)}")
        
        if not os.path.exists(image_path):
            raise HTTPException(status_code=404, detail=f"圖片文件不存在: {image_path}")

        # 設置狀態元數據供圖片處理使用
        status_manager.set_meta('logger', logger)
        status_manager.set_meta('current_filename', filename)
        
        # 處理圖片, 跳過OCR直接使用多模態模型
        # 傳遞實際的圖片路徑而不是檔名
        result, tmp_filename = await summarize_image(
            filename=image_path,  # 傳遞完整路徑
            config=config,
            llm_config=llm_config,
            status_manager=status_manager,
            device=device,
            skip_ocr=True,
            language=language
        )
        
        # 保存處理結果到文件系統
        # 使用原始檔名而不是完整路徑來保存結果
        base_filename = os.path.basename(filename) if filename != image_path else filename
        result_filename = os.path.splitext(base_filename)[0] + '.md'
        result_path = os.path.join(notes_root_str, result_filename)
        try:
            # 確保目錄存在
            os.makedirs(os.path.dirname(result_path), exist_ok=True)
            
            # 🔧 清理 Markdown 內容:修復代碼塊、移除 HTML 標籤
            from utils.markdown_cleaner import clean_markdown
            cleaned_result = clean_markdown(result)
            
            with open(result_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_result)
            logger.info(f"圖片處理結果已保存到: {result_path}")
        except Exception as save_error:
            logger.error(f"保存圖片處理結果失敗: {save_error}")
        
        # 處理完成後同步圖片
        try:
            sync_result = perform_image_sync(language)
            logger.info(f"圖片同步結果: {sync_result}")
        except Exception as sync_error:
            logger.warning(f"圖片同步失敗: {sync_error}")
        
        return JSONResponse(content={"result": result, "tmp_filename": tmp_filename})
    except Exception as e:
        import sys
        import traceback as tb
        exc_type, exc_value, exc_tb = sys.exc_info()
        logger.error(f"圖片處理錯誤: {e}\n{tb.format_exc()}")
        raise
    finally:
        # 清理狀態
        status_manager.clear_meta('current_filename')
        status_manager.clear_meta('logger')

# === 圖片處理API結束 ===

# 暫存管理API
@app.get("/api/tmp/list")
def list_tmp_data():
    tmp_root = output_tmp_root
    if not os.path.exists(tmp_root):
        return {"tmp": []}
    result = []
    now = time.time()
    expire_days = 7  # 7天未存檔視為過期
    for d in os.listdir(tmp_root):
        folder = os.path.join(tmp_root, d)
        if os.path.isdir(folder):
            scenes_json = os.path.join(folder, 'scenes.json')
            created = os.path.getctime(folder)
            has_scenes = os.path.exists(scenes_json)
            scene_count = 0
            if has_scenes:
                try:
                    with open(scenes_json, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        scene_count = len(data.get('scenes', []))
                except:
                    pass
            days = (now - created) / 86400
            expired = days > expire_days
            result.append({
                "filename": d,
                "scene_count": scene_count,
                "created": created,
                "has_scenes": has_scenes,
                "expired": expired,
                "expired_days": int(days)
            })
    return {"tmp": result}

@app.get("/api/tmp/check")
def check_tmp_data(filename: str):
    base_name = os.path.splitext(filename)[0]
    tmp_folder = os.path.join(output_tmp_root, base_name)
    img_folder = os.path.join(output_images_root, base_name)
    has_tmp = os.path.exists(tmp_folder) or os.path.exists(img_folder)
    return {"available": has_tmp}

@app.post("/api/tmp/delete")
def delete_tmp_data(filename: str = Form(...)):
    try:
        # 支援完整路徑或僅檔名
        if '/' in filename or '\\' in filename:
            base_name = os.path.splitext(os.path.basename(filename))[0]
        else:
            base_name = os.path.splitext(filename)[0]
        
        tmp_folder = os.path.join(output_tmp_root, base_name)
        img_folder = os.path.join(output_images_root, base_name)
        deleted_folders = []
        
        for folder in [tmp_folder, img_folder]:
            if os.path.exists(folder):
                shutil.rmtree(folder)
                deleted_folders.append(folder)
                logger.info(f"已刪除暫存資料夾: {folder}")
        
        if deleted_folders:
            return {"deleted": filename, "folders": deleted_folders, "status": "success"}
        else:
            return {"deleted": filename, "folders": [], "status": "no_data", "message": "沒有找到暫存資料"}
    except Exception as e:
        logger.error(f"刪除暫存失敗: {e}")
        raise HTTPException(status_code=500, detail=f"刪除暫存失敗: {str(e)}")



@app.post("/api/clear-all-status")
def clear_all_status():
    """清理所有處理狀態"""
    status_manager.clear()
    return JSONResponse(content={"message": "所有狀態已清理", "status": "success"}, media_type="application/json; charset=utf-8")

@app.get("/api/emergency-reset")
def emergency_reset():
    """緊急重置 - 清理所有狀態並返回重置指令"""
    status_manager.clear()
    status_messages = get_status_messages("zh-TW")  # 緊急重置使用默認語言
    return {
        "message": status_messages['emergency_reset_complete'], 
        "status": "success",
        "action": "reload_page"
    }

@app.get("/api/debug/latest-result")
def get_latest_result():
    """測試端點: 獲取最新生成的筆記內容"""
    try:
        # 檢查兩個可能的目錄
        search_dirs = [notes_root_str, OUTPUT_ROOT]
        all_md_files = []
        
        for search_dir in search_dirs:
            if os.path.exists(search_dir):
                for file in os.listdir(search_dir):
                    if file.endswith('.md'):
                        file_path = os.path.join(search_dir, file)
                        all_md_files.append({
                            'name': file,
                            'path': file_path,
                            'mtime': os.path.getmtime(file_path),
                            'dir': search_dir
                        })
        
        if not all_md_files:
            return {"error": "沒有找到筆記文件"}
        
        # 按修改時間排序, 取最新的
        latest_file = sorted(all_md_files, key=lambda x: x['mtime'], reverse=True)[0]
        
        with open(latest_file['path'], 'r', encoding='utf-8') as f:
            content = f.read()
        
        return {
            "filename": latest_file['name'],
            "content": content,
            "length": len(content),
            "modified_time": latest_file['mtime'],
            "source_dir": latest_file['dir']
        }
    except Exception as e:
        logger.error(f"獲取最新結果失敗: {e}")
        return {"error": str(e)}

@app.get("/api/get-note")
def get_note(filename: str):
    """獲取已生成的筆記內容"""
    try:
        from urllib.parse import unquote
        decoded_filename = unquote(filename)
        note_path = os.path.join(notes_root_str, decoded_filename)
        
        if not os.path.exists(note_path):
            raise HTTPException(status_code=404, detail=f"筆記文件不存在: {decoded_filename}")
        
        with open(note_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return {
            "filename": decoded_filename,
            "content": content,
            "file_size": len(content),
            "modified_time": os.path.getmtime(note_path)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"讀取筆記失敗: {e}")
        raise HTTPException(status_code=500, detail=f"讀取筆記失敗: {str(e)}")

@app.get("/api/logs/{filename}")
def get_logs(filename: str):
    log_file = os.path.join(log_dir, 'notegen.log')
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        filtered = [l for l in lines if filename in l]
        return {"logs": filtered}
    except Exception as e:
        logger.error(f"Log read error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 修正結果API, 確保文件路徑正確
@app.get("/api/image-result/{filename}")
def get_image_result(filename: str):
    """獲取圖片處理結果"""
    try:
        # URL 解碼檔名
        from urllib.parse import unquote
        decoded_filename = unquote(filename)
        
        # 檢查多個可能的結果文件位置
        possible_paths = [
            os.path.join(notes_root_str, decoded_filename),  # 完整檔名
            os.path.join(notes_root_str, decoded_filename + '.md'),  # 添加 .md 後綴
            os.path.join(notes_root_str, decoded_filename.replace('.jpg', '.md')),  # 替換擴展名
            os.path.join(notes_root_str, decoded_filename.replace('.png', '.md')),
            os.path.join(notes_root_str, decoded_filename.replace('.jpeg', '.md')),
            os.path.join(notes_root_str, os.path.splitext(decoded_filename)[0] + '.md'),  # 基本名稱 + .md
        ]
        
        # 嘗試從每個可能的路徑讀取結果
        for note_path in possible_paths:
            if os.path.exists(note_path):
                try:
                    with open(note_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    logger.info(f"成功載入圖片結果文件: {note_path}")
                    return {"content": content, "path": note_path}
                except Exception as e:
                    logger.error(f"讀取圖片結果文件失敗 {note_path}: {e}")
                    continue
        
        # 如果所有路徑都沒有找到文件, 返回 404
        logger.warning(f"未找到圖片結果文件, 搜尋路徑: {possible_paths}")
        raise HTTPException(status_code=404, detail=f"Image result not found for: {decoded_filename}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取圖片結果失敗: {e}")
        raise HTTPException(status_code=500, detail=f"獲取圖片結果失敗: {str(e)}")

@app.delete("/api/image-result/{filename}")
def delete_image_result(filename: str):
    """刪除圖片處理結果文件"""
    try:
        # URL 解碼檔名
        from urllib.parse import unquote
        decoded_filename = unquote(filename)
        
        # 檢查多個可能的結果文件位置
        possible_paths = [
            os.path.join(notes_root_str, decoded_filename),  # 完整檔名
            os.path.join(notes_root_str, decoded_filename + '.md'),  # 添加 .md 後綴
            os.path.join(notes_root_str, decoded_filename.replace('.jpg', '.md')),  # 替換擴展名
            os.path.join(notes_root_str, decoded_filename.replace('.png', '.md')),
            os.path.join(notes_root_str, decoded_filename.replace('.jpeg', '.md')),
            os.path.join(notes_root_str, os.path.splitext(decoded_filename)[0] + '.md'),  # 基本名稱 + .md
        ]
        
        deleted_files = []
        
        # 嘗試刪除所有找到的結果文件
        for note_path in possible_paths:
            if os.path.exists(note_path):
                try:
                    os.remove(note_path)
                    deleted_files.append(note_path)
                    logger.info(f"成功刪除圖片結果文件: {note_path}")
                except Exception as e:
                    logger.error(f"刪除圖片結果文件失敗 {note_path}: {e}")
        
        if deleted_files:
            return {
                "status": "success", 
                "message": f"成功刪除 {len(deleted_files)} 個圖片結果文件",
                "deleted_files": deleted_files
            }
        else:
            raise HTTPException(status_code=404, detail=f"未找到要刪除的圖片結果文件: {decoded_filename}")
            
    except Exception as e:
        logger.error(f"刪除圖片結果失敗: {e}")
        raise HTTPException(status_code=500, detail=f"刪除圖片結果失敗: {str(e)}")

@app.get("/api/result/{filename}")
def get_result(filename: str):
    # URL 解碼檔名
    from urllib.parse import unquote
    decoded_filename = unquote(filename)

    def _merge_structured_payload(file_structured, runtime_structured):
        if runtime_structured and not isinstance(runtime_structured, dict):
            return runtime_structured
        if file_structured and not isinstance(file_structured, dict):
            file_structured = {"content": file_structured}
        runtime_structured = dict(runtime_structured or {})
        if not isinstance(file_structured, dict):
            return runtime_structured or file_structured
        merged = dict(runtime_structured)
        # 補上既有 JSON 中缺失但前端需要的欄位
        for key, value in file_structured.items():
            if key == "meta" and isinstance(value, dict):
                existing_meta = merged.get("meta", {})
                if isinstance(existing_meta, dict):
                    merged["meta"] = {**value, **existing_meta}
                else:
                    merged["meta"] = dict(value)
            elif key in {"sceneSummaries", "scene_summaries"}:
                if key not in merged and value:
                    merged[key] = value
            else:
                merged.setdefault(key, value)
        # 確保場景資料兩種命名都存在
        if "sceneSummaries" in merged and "scene_summaries" not in merged:
            merged["scene_summaries"] = merged["sceneSummaries"]
        if "scene_summaries" in merged and "sceneSummaries" not in merged:
            merged["sceneSummaries"] = merged["scene_summaries"]
        return merged
    
    logger.info(f"🔍 [get_result] 請求檔名: {filename}")
    logger.info(f"🔍 [get_result] 解碼後檔名: {decoded_filename}")
    
    # 檢查多個可能的結果文件位置
    possible_paths = [
        os.path.join(notes_root_str, decoded_filename),  # 完整檔名
        os.path.join(notes_root_str, decoded_filename + '.md'),  # 添加 .md 後綴
        os.path.join(notes_root_str, decoded_filename.replace('.mp4', '.md')),  # 替換擴展名
    os.path.join(notes_root_str, os.path.splitext(decoded_filename)[0] + '.md'),  # 基本名稱 + .md
    # 也支援從 output 目錄讀取(影片處理目前將結果寫入此處)
    os.path.join(output_root_str, decoded_filename),
    os.path.join(output_root_str, decoded_filename + '.md'),
    os.path.join(output_root_str, decoded_filename.replace('.mp4', '.md')),
    os.path.join(output_root_str, os.path.splitext(decoded_filename)[0] + '.md'),
    ]
    
    logger.info(f"🔍 [get_result] 搜尋路徑: {possible_paths[:3]}...")
    
    # 嘗試從每個可能的路徑讀取結果
    for note_path in possible_paths:
        if os.path.exists(note_path):
            try:
                with open(note_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                logger.info(f"✅ [get_result] 成功載入結果文件: {note_path} (大小: {len(content)} 字元)")
                # 嘗試載入對應的 JSON 結構(同名 .json)
                structured = None
                try:
                    import json as _json
                    base, _ = os.path.splitext(note_path)
                    json_path = base + '.json'
                    if os.path.exists(json_path):
                        with open(json_path, 'r', encoding='utf-8') as jf:
                            structured = _json.load(jf)
                        logger.info(f"✅ [get_result] 成功載入結構化 JSON: {json_path}")
                    # 合併記憶體中的最新結構化資訊
                    status_key_candidates = [
                        decoded_filename,
                        os.path.basename(decoded_filename),
                        os.path.splitext(decoded_filename)[0] + '.mp4',
                        os.path.splitext(os.path.basename(decoded_filename))[0] + '.mp4',
                    ]
                    runtime_structured = None
                    for key in status_key_candidates:
                        key = key.strip()
                        if not key:
                            continue
                        if status_manager.contains(key):
                            snapshot = status_manager.get(key)
                            runtime_structured = snapshot.get("structured")
                            if runtime_structured:
                                break
                    if runtime_structured:
                        structured = _merge_structured_payload(structured, runtime_structured)
                except Exception as _e:
                    logger.warning(f"⚠️ [get_result] 讀取結構化 JSON 失敗: {note_path}: {_e}")
                return {"content": content, "path": note_path, "structured": structured}
            except Exception as e:
                logger.error(f"❌ [get_result] 讀取結果文件失敗 {note_path}: {e}")
                continue
    
    # 如果所有路徑都沒有找到文件, 返回 404
    logger.warning(f"❌ [get_result] 未找到結果文件, 搜尋路徑: {possible_paths}")
    raise HTTPException(status_code=404, detail=f"Result not found for: {decoded_filename}")

@app.delete("/api/result/{filename}")
def delete_result(filename: str):
    """刪除處理結果文件"""
    try:
        # URL 解碼檔名
        from urllib.parse import unquote
        decoded_filename = unquote(filename)
        
        # 檢查多個可能的結果文件位置（包含 notes 與 output）
        possible_paths = [
            os.path.join(notes_root_str, decoded_filename),  # 完整檔名
            os.path.join(notes_root_str, decoded_filename + '.md'),  # 添加 .md 後綴
            os.path.join(notes_root_str, decoded_filename.replace('.mp4', '.md')),  # 替換擴展名
            os.path.join(notes_root_str, os.path.splitext(decoded_filename)[0] + '.md'),  # 基本名稱 + .md
            os.path.join(output_root_str, decoded_filename),
            os.path.join(output_root_str, decoded_filename + '.md'),
            os.path.join(output_root_str, decoded_filename.replace('.mp4', '.md')),
            os.path.join(output_root_str, os.path.splitext(decoded_filename)[0] + '.md'),
        ]
        
        deleted_files = []
        
        # 嘗試刪除所有找到的結果文件
        for note_path in possible_paths:
            if os.path.exists(note_path):
                try:
                    os.remove(note_path)
                    deleted_files.append(note_path)
                    logger.info(f"成功刪除結果文件: {note_path}")
                except Exception as e:
                    logger.error(f"刪除結果文件失敗 {note_path}: {e}")
        
        if not deleted_files:
            logger.info(f"未找到要刪除的結果文件, 視為成功: {decoded_filename}")

        return {
            "status": "success",
            "message": f"已清理舊結果 (刪除 {len(deleted_files)} 個, 未找到亦視為完成)",
            "deleted_files": deleted_files
        }
            
    except Exception as e:
        logger.error(f"刪除結果失敗: {e}")
        raise HTTPException(status_code=500, detail=f"刪除結果失敗: {str(e)}")

# 重複的models端點已移除，使用上面的async版本

@app.post("/api/notes/save")
async def save_note(
    category: str = Form(...),
    title: str = Form(...),
    content: str = Form(...),
    images: Optional[str] = Form(None),
    tmp_filename: Optional[str] = Form(None)
):
    try:
        # 創建分類資料夾
        cat_path = os.path.join(notes_root_str, *category.split('/'))
        os.makedirs(cat_path, exist_ok=True)
        os.makedirs(os.path.join(cat_path, 'images'), exist_ok=True)
        
        # 生成筆記檔案
        note_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        note_file = os.path.join(cat_path, f"{note_id}_{title.replace('/', '_')}.md")
        
        # 寫入筆記內容
        with open(note_file, 'w', encoding='utf-8') as f:
            f.write(f"# {title}\n\n")
            f.write(f"**建立時間**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**分類**: {category}\n\n")
            f.write("---\n\n")
            f.write(content)
        
        logger.info(f"筆記已保存: {note_file}")
        
        # 處理暫存刪除
        deleted_tmp = False
        if tmp_filename:
            try:
                # 支援完整路徑或僅檔名
                if '/' in tmp_filename or '\\' in tmp_filename:
                    base_name = os.path.splitext(os.path.basename(tmp_filename))[0]
                else:
                    base_name = os.path.splitext(tmp_filename)[0]
                
                tmp_folder = os.path.join(output_tmp_root, base_name)
                img_folder = os.path.join(output_images_root, base_name)
                
                for folder in [tmp_folder, img_folder]:
                    if os.path.exists(folder):
                        shutil.rmtree(folder)
                        logger.info(f"已刪除暫存資料夾: {folder}")
                        deleted_tmp = True
                        
            except Exception as e:
                logger.warning(f"刪除暫存時發生錯誤: {e}")
        
        return {
            "status": "ok", 
            "note": note_file,
            "deleted_tmp": deleted_tmp,
            "message": "筆記保存成功" + (", 暫存已清理" if deleted_tmp else "")
        }
        
    except Exception as e:
        logger.error(f"保存筆記失敗: {e}")
        raise HTTPException(status_code=500, detail=f"保存筆記失敗: {str(e)}")

@app.get("/api/notes/list")
def list_notes(category: Optional[str] = None):
    """List notes from saved_notes and also include output/*.md as unfiled notes.

    - When category is one of ("__output__", "output", "未歸檔", "未分類"), only return output notes.
    - When category is a concrete saved folder, return that folder's notes.
    - When category is empty/None, return union of saved_notes and output notes.
    """
    notes: list[str] = []

    # Helper to collect notes from output directory and prefix path with 'output/'
    def collect_output_notes():
        output_dir = OUTPUT_ROOT
        if os.path.exists(output_dir):
            for root, _, files in os.walk(output_dir):
                for fname in files:
                    if fname.endswith('.md'):
                        rel = os.path.relpath(os.path.join(root, fname), output_dir)
                        rel = rel.replace("\\", "/")
                        notes.append(f"output/{rel}")

    # If category explicitly points to output (未歸檔)
    output_aliases = {"__output__", "output", "未歸檔"}
    if category in output_aliases:
        collect_output_notes()
        return {"notes": sorted(notes)}

    # Special handling for "未分類": files directly under saved_notes root
    if category == "未分類":
        base = NOTES_ROOT
        if os.path.exists(base):
            for fname in os.listdir(base):
                fp = os.path.join(base, fname)
                if os.path.isfile(fp) and fname.endswith('.md'):
                    rel = os.path.relpath(fp, NOTES_ROOT).replace("\\", "/")
                    notes.append(rel)
        return {"notes": sorted(notes)}

    # Otherwise collect from saved_notes (optionally scoped by category)
    base = NOTES_ROOT
    if category:
        base = os.path.join(base, *category.split('/'))
    if os.path.exists(base):
        for root, _, files in os.walk(base):
            for fname in files:
                if fname.endswith('.md'):
                    rel = os.path.relpath(os.path.join(root, fname), NOTES_ROOT).replace("\\", "/")
                    notes.append(rel)

    # If no category filter, also include output notes for convenience
    if not category:
        collect_output_notes()

    return {"notes": sorted(notes)}

@app.get("/api/notes/categories")
def list_categories():
    """List categories under saved_notes and add a pseudo category for output notes."""
    cats: list[str] = []
    for root, dirs, _ in os.walk(NOTES_ROOT):
        for d in dirs:
            if d != 'images':  # 排除圖片資料夾
                rel = os.path.relpath(os.path.join(root, d), NOTES_ROOT).replace("\\", "/")
                cats.append(rel)

    # If there are any .md files under output, expose a friendly pseudo category
    has_output_md = False
    output_dir = OUTPUT_ROOT
    if os.path.exists(output_dir):
        for r, _, files in os.walk(output_dir):
            if any(f.endswith('.md') for f in files):
                has_output_md = True
                break
    if has_output_md:
        cats.append('未歸檔')

    # If there are .md files directly under saved_notes root, expose "未分類"
    try:
        if any(os.path.isfile(os.path.join(notes_root_str, f)) and f.endswith('.md') for f in os.listdir(NOTES_ROOT)):
            cats.append('未分類')
    except Exception:
        pass

    # De-duplicate and sort for stable UI
    cats = sorted(list(dict.fromkeys(cats)))
    return {"categories": cats}

@app.get("/api/notes/content/{note_path:path}")
def get_note_content(note_path: str):
    """Read note content from saved_notes or output.

    Accepts paths relative to saved_notes, or prefixed with 'output/'.
    """
    try:
        candidate_paths = []
        # If path indicates output
        if note_path.startswith('output/'):
            candidate_paths.append(os.path.join(output_root_str, note_path[len('output/'):]))
        # Saved notes path
        candidate_paths.append(os.path.join(notes_root_str, note_path))
        # Fallback: treat the whole as relative to output
        candidate_paths.append(os.path.join(output_root_str, note_path))

        full_path = None
        for p in candidate_paths:
            if os.path.exists(p):
                full_path = p
                break
        if not full_path:
            raise HTTPException(status_code=404, detail="筆記不存在")

        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return {"content": content}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"讀取筆記內容失敗: {e}")
        raise HTTPException(status_code=500, detail=f"讀取筆記失敗: {str(e)}")

@app.delete("/api/notes/delete/{note_path:path}")
def delete_note(note_path: str):
    """Delete note from saved_notes or output."""
    try:
        candidate_paths = []
        if note_path.startswith('output/'):
            candidate_paths.append(os.path.join(output_root_str, note_path[len('output/'):]))
        candidate_paths.append(os.path.join(notes_root_str, note_path))
        candidate_paths.append(os.path.join(output_root_str, note_path))

        full_path = None
        for p in candidate_paths:
            if os.path.exists(p):
                full_path = p
                break
        if not full_path:
            raise HTTPException(status_code=404, detail="筆記不存在")

        os.remove(full_path)
        logger.info(f"筆記已刪除: {full_path}")
        return {"status": "success", "message": "筆記已刪除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"刪除筆記失敗: {e}")
        raise HTTPException(status_code=500, detail=f"刪除筆記失敗: {str(e)}")



OLLAMA_BASE = "http://ollama:11434"  # 使用 Docker Compose 內部網路

@app.post("/api/chat")
async def chat_endpoint(req: RouterChatRequest):
    """統一的聊天端點，委派給 modules.api_routes.chat_completion"""
    return await router_chat_completion(req)


@app.get("/api/prompts/manifest")
async def get_prompt_manifest():
    """提供 Cornell 提示詞清單供前端同步。"""
    return manifest_dict()


@app.get("/api/llm/providers")
async def get_llm_providers():
    """列出可用的 LLM provider 與模型資訊"""
    return list_provider_metadata()


@app.post("/api/llm/providers/{provider}/activate")
async def activate_llm_provider(provider: str):
    """切換當前使用的 LLM provider 並重新載入設定。"""
    provider = (provider or "").lower()
    config = load_config(force_reload=True)
    llm_cfg = config.setdefault("llm", {})
    target_cfg = llm_cfg.get(provider)
    if not isinstance(target_cfg, dict):
        raise HTTPException(status_code=404, detail=f"Provider '{provider}' not found in configuration.")
    if llm_cfg.get("provider") == provider:
        return list_provider_metadata()

    llm_cfg["provider"] = provider
    save_config(config)
    reload_llm_providers()
    return list_provider_metadata()


@app.get("/api/diagnose")
def diagnose():
    """快速診斷後端依賴是否可用"""
    from datetime import datetime
    result = {
        "llm_provider": list_provider_metadata(),
        "timestamp": datetime.utcnow().isoformat(),
        "version": "3.0.7-enhanced",
        "prompt_manifest": {
            "id": manifest_id(),
            "version": manifest_version(),
            "hash": manifest_hash(),
            "definition": manifest_dict(),
        },
    }
    cfg: Dict[str, Any] = {}

    # 檢查 Ollama
    try:
        import httpx as _httpx
        bases = [
            "http://ollama:11434",
            "http://host.docker.internal:11434",
        ]
        ol_status = {"ok": False, "tried": [], "endpoint": None}
        with _httpx.Client(timeout=5.0) as client:
            for base in bases:
                try:
                    r = client.get(f"{base}/api/tags")
                    ol_status["tried"].append({"endpoint": base, "status": r.status_code})
                    if r.status_code == 200:
                        data = r.json()
                        models = data.get("models", []) if isinstance(data, dict) else []
                        model_names = [
                            model.get("name", "unknown")
                            for model in models
                            if isinstance(model, dict)
                        ]
                        ol_status.update({
                            "ok": True,
                            "endpoint": base,
                            "status": 200,
                            "models": len(model_names),
                            "model_names": model_names,
                        })
                        break
                except Exception as e:
                    ol_status["tried"].append({"endpoint": base, "error": str(e)})
        result["ollama"] = ol_status
    except Exception as e:
        result["ollama"] = {"ok": False, "error": str(e)}

    # 檢查 ffmpeg
    try:
        import subprocess as _sp
        p = _sp.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
        result["ffmpeg"] = {
            "ok": p.returncode == 0,
            "version": p.stdout.split("\n")[0] if p.stdout else None
        }
    except Exception as e:
        result["ffmpeg"] = {"ok": False, "error": str(e)}

    # 檢查 NVIDIA
    try:
        import subprocess as _sp
        p = _sp.run(["nvidia-smi"], capture_output=True, text=True, timeout=5)
        result["nvidia_smi"] = {"ok": p.returncode == 0}
    except Exception as e:
        result["nvidia_smi"] = {"ok": False, "error": str(e)}

    # CPU/RAM 信息
    try:
        if psutil:
            result["cpu_percent"] = round(psutil.cpu_percent(interval=0.5), 1)
            result["ram_percent"] = round(psutil.virtual_memory().percent, 1)
    except Exception:
        result["cpu_percent"] = None
        result["ram_percent"] = None

    # PaddleOCR-VL 狀態
    try:
        cfg = load_config()
        result["paddleocr_vl"] = get_paddleocr_vl_status(cfg)
    except Exception as e:
        result["paddleocr_vl"] = {"ok": False, "error": str(e)}

    # Qwen / LLM 狀態
    try:
        llm_cfg = cfg.get("llm", {}) if isinstance(cfg, dict) else {}
        final_model = llm_cfg.get("final_model")
        model_names = result.get("ollama", {}).get("model_names") or []
        present = bool(final_model and final_model in model_names)
        result["qwen"] = {
            "ok": present and bool(result.get("ollama", {}).get("ok")),
            "configured_model": final_model,
            "scene_model": llm_cfg.get("scene_model"),
            "image_model": llm_cfg.get("image_model"),
            "present_in_ollama": present,
            "ollama_endpoint": result.get("ollama", {}).get("endpoint"),
            "checked_at": result["timestamp"],
            "available_models": model_names,
        }
    except Exception as e:
        result["qwen"] = {"ok": False, "error": str(e)}

    return result


@app.get("/api/ollama/health")
async def check_ollama_health():
    """檢查 Ollama 服務健康狀態
    
    Returns:
        dict: {
            status: 'healthy' | 'error',
            message: str,
            models: list[str] (if healthy),
            can_restart: bool
        }
    """
    try:
        # 健康檢查始終針對本地 Ollama 容器（即使使用雲端推理）
        # 因為本地容器仍然需要用於 4b 模型和作為備援
        ollama_base = os.environ.get("OLLAMA_FALLBACK_BASE", "http://ollama_local:11434")
        
        # 直接檢查 Ollama API 是否響應
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{ollama_base}/api/tags")
                
                if response.status_code == 200:
                    data = response.json()
                    raw_models = [model.get("name", "unknown") for model in data.get("models", [])]
                    models = _filter_ui_models(raw_models)
                    
                    return {
                        "status": "healthy",
                        "message": f"Ollama 服務正常運行，已載入 {len(models)} 個模型",
                        "models": models,
                        "can_restart": False
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"Ollama API 返回異常狀態碼: {response.status_code}",
                        "can_restart": True
                    }
                    
            except httpx.TimeoutException:
                return {
                    "status": "error",
                    "message": "Ollama API 響應超時，服務可能卡住或 VRAM 資源耗盡",
                    "can_restart": True
                }
            except httpx.ConnectError:
                return {
                    "status": "error",
                    "message": "無法連接到 Ollama 服務（連接被拒絕）",
                    "can_restart": True
                }
            except Exception as api_error:
                return {
                    "status": "error",
                    "message": f"Ollama API 錯誤: {str(api_error)}",
                    "can_restart": True
                }
                
    except Exception as e:
        logger.error(f"檢查 Ollama 健康狀態時發生錯誤: {e}")
        return {
            "status": "error",
            "message": f"健康檢查失敗: {str(e)}",
            "can_restart": True
        }


@app.post("/api/ollama/restart")
async def restart_ollama():
    """重啟 Ollama 容器
    
    注意:此功能需要在 docker-compose.yml 中掛載 Docker socket:
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    
    Returns:
        dict: {
            success: bool,
            message: str
        }
    """
    try:
        logger.info("嘗試重啟 Ollama 容器...")
        
        # 方法 1: 嘗試使用 Docker socket (如果已掛載)
        import subprocess
        try:
            result = subprocess.run(
                ["docker", "restart", "ollama_local"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False
            )
            
            if result.returncode == 0:
                logger.info("✅ Docker 重啟命令執行成功，等待服務啟動...")
                
                # 等待容器啟動
                await asyncio.sleep(5)
                
                # 驗證服務
                ollama_base = os.environ.get("OLLAMA_BASE", "http://ollama_local:11434")
                try:
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        response = await client.get(f"{ollama_base}/api/tags")
                        
                        if response.status_code == 200:
                            logger.info("✅ Ollama 服務已成功重啟並響應正常")
                            return {
                                "success": True,
                                "message": "Ollama 服務已成功重啟並恢復正常"
                            }
                except Exception as verify_error:
                    logger.warning(f"⚠️ 重啟後驗證失敗: {verify_error}")
                    return {
                        "success": True,
                        "message": "已執行重啟命令。如服務未恢復，請手動重啟 Ollama 容器。"
                    }
                    
            else:
                # Docker 命令失敗,可能沒有掛載 socket
                logger.warning(f"Docker 命令失敗: {result.stderr}")
                raise FileNotFoundError("Docker CLI 不可用")
                
        except (FileNotFoundError, subprocess.SubprocessError) as docker_error:
            # 方法 2: 返回指導信息,讓用戶手動重啟
            logger.warning(f"無法直接重啟容器: {docker_error}")
            return {
                "success": False,
                "message": "自動重啟功能需要配置 Docker socket 掛載。\n\n請手動執行以下命令重啟 Ollama:\n\ndocker restart ollama_local\n\n或在 Docker Desktop 中重啟 ollama_local 容器。"
            }
            
    except Exception as e:
        logger.error(f"❌ 重啟 Ollama 時發生異常: {e}")
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "message": f"重啟失敗: {str(e)}\n\n請手動執行: docker restart ollama_local"
        }
