# MODULE_VERSION = "v2025-10-12-NO-WHISPER"
import os
import logging
import tempfile
import time
import statistics
import copy
import threading
from collections import deque
import cv2
import numpy as np
from scenedetect import VideoManager, SceneManager
from scenedetect.detectors import ContentDetector
import shutil
import base64
import json
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor
from modules.llm_utils import call_llm
from modules.services.runtime_paths import (
    LOG_ROOT as LOG_ROOT_PATH,
    OUTPUT_ROOT as OUTPUT_ROOT_PATH,
    ensure_runtime_dirs,
)
# Whisper 為可選依賴 - 若未安裝則自動停用音訊處理
try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("⚠️ faster-whisper 未安裝,音訊轉錄功能已停用。系統將僅使用視覺分析 (OCR + 場景檢測)")

import subprocess
import asyncio
import traceback

from modules.services.status_manager import StatusManager
from modules.services.media_paths import get_media_path_service
from modules.note_generator import create_note_generator, convert_web_path_to_fs
from modules.cornell_pipeline import CornellNotePipeline
from modules.services.pipeline_trace import PipelineTrace
from modules.services.gpu_utils import prepare_llm_inference, release_cuda_cache
from modules.services.system_metrics import capture_snapshot
from modules.services.config_manager import is_ocr_enabled

logger = logging.getLogger(__name__)

ensure_runtime_dirs()
OUTPUT_ROOT = str(OUTPUT_ROOT_PATH)
OUTPUT_IMAGES_ROOT = os.path.join(OUTPUT_ROOT, "images")
LOG_ROOT = str(LOG_ROOT_PATH)

# --- Global caches to avoid reloading large models repeatedly ---
_WHISPER_MODEL_CACHE = {}

# --- Thermal guardrails (GPU temperature/load) ---
class ThermalGuard:
    def __init__(self):
        self._lock = threading.Lock()
        self._history = deque(maxlen=120)  # ~10 minutes at 5s interval
        self._last_check = 0.0
        self._overheat_since = None
        self._last_temp = None

    def _read_temp(self) -> Optional[float]:
        snapshot = capture_snapshot()
        gpus = snapshot.get("gpu") or []
        if not gpus:
            return None
        temp = gpus[0].get("temp_c")
        try:
            return float(temp) if temp is not None else None
        except Exception:
            return None

    def sample(self, guard_cfg: Dict[str, Any]) -> Optional[float]:
        interval = float(guard_cfg.get("check_interval_sec", 5))
        now = time.time()
        with self._lock:
            if now - self._last_check < interval and self._last_temp is not None:
                return self._last_temp
            temp = self._read_temp()
            self._last_check = now
            self._last_temp = temp
            if temp is not None:
                self._history.append((now, temp))
            return temp

    def evaluate(self, guard_cfg: Dict[str, Any]) -> Dict[str, Any]:
        warn_temp = float(guard_cfg.get("warn_temp_c", 80))
        force_temp = float(guard_cfg.get("force_temp_c", 85))
        recover_temp = float(guard_cfg.get("recover_temp_c", 75))
        sustain = float(guard_cfg.get("sustain_seconds", 30))

        temp = self.sample(guard_cfg)
        action = "ok"

        now = time.time()
        with self._lock:
            if temp is None:
                self._overheat_since = None
                return {"temp_c": None, "action": "unknown"}

            if temp >= force_temp:
                if self._overheat_since is None:
                    self._overheat_since = now
                elif now - self._overheat_since >= sustain:
                    action = "force_cpu"
                else:
                    action = "throttle"
            elif temp >= warn_temp:
                self._overheat_since = None
                action = "throttle"
            elif temp <= recover_temp:
                self._overheat_since = None
                action = "recover"

        return {"temp_c": temp, "action": action}


_THERMAL_GUARD = ThermalGuard()


def _select_scenes_for_note_style(scenes: List[Any], requested_note_style: str) -> List[Any]:
    """Choose scenes for final note generation by note style.

    Meeting mode keeps all detected scenes so output can map one screenshot
    to one explanation block, matching user expectations for meeting playback.
    """
    style = str(requested_note_style or "").strip().lower()
    if style in {"meeting", "summary", "minutes"}:
        return list(scenes or [])
    return list(scenes or [])

# --- ffmpeg/ffprobe 探測與統一路徑 ---
_FFMPEG_BIN = None
_FFPROBE_BIN = None
try:
    # 允許以環境變數覆寫
    env_ffmpeg = os.environ.get('FFMPEG_BIN')
    env_ffprobe = os.environ.get('FFPROBE_BIN')
    if env_ffmpeg:
        _FFMPEG_BIN = env_ffmpeg
    if env_ffprobe:
        _FFPROBE_BIN = env_ffprobe
    # 優先使用靜態版
    if _FFMPEG_BIN is None and os.path.exists('/usr/local/bin/ffmpeg'):
        _FFMPEG_BIN = '/usr/local/bin/ffmpeg'
    if _FFPROBE_BIN is None and os.path.exists('/usr/local/bin/ffprobe'):
        _FFPROBE_BIN = '/usr/local/bin/ffprobe'
    # 最後回退到 PATH
    _FFMPEG_BIN = _FFMPEG_BIN or 'ffmpeg'
    _FFPROBE_BIN = _FFPROBE_BIN or 'ffprobe'
    logger.info(f"[ffmpeg] using binary: {_FFMPEG_BIN}")
except Exception:
    _FFMPEG_BIN = 'ffmpeg'
    _FFPROBE_BIN = 'ffprobe'

def _ensure_readable_mp4(src_path: str, work_dir: str) -> str:
    """確保 mp4 可被解碼：若缺 moov atom 或 OpenCV 無法開啟，使用 ffmpeg 靜態版快速 remux。
    返回可讀檔案路徑（可能與原檔相同）。
    """
    try:
        if not os.path.exists(src_path):
            return src_path
        # 快速檢查: OpenCV 能否開啟/讀取 fps
        cap = cv2.VideoCapture(src_path)
        ok = cap.isOpened()
        fps = cap.get(cv2.CAP_PROP_FPS) if ok else 0
        cap.release()
        if ok and (fps and fps > 0):
            return src_path

        # 無法讀取 → 嘗試 remux（不轉碼）
        fixed_path = os.path.join(work_dir or tempfile.gettempdir(), 'fixed_input.mp4')
        try:
            if os.path.exists(fixed_path):
                os.remove(fixed_path)
        except Exception:
            pass
        cmd = [
            _FFMPEG_BIN, '-hide_banner', '-loglevel', 'error', '-y',
            '-i', src_path, '-c', 'copy', '-movflags', 'faststart', fixed_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)

        # 再次驗證
        cap2 = cv2.VideoCapture(fixed_path)
        ok2 = cap2.isOpened()
        fps2 = cap2.get(cv2.CAP_PROP_FPS) if ok2 else 0
        cap2.release()
        return fixed_path if (ok2 and fps2 and fps2 > 0) else src_path
    except Exception as e:
        logger.error(f"Remux 檢查/修復失敗: {e}")
        return src_path

def _trace_write(base_filename: str, message: str) -> None:
    """將關鍵流程寫入 logs/traces/<影片名>.log 以便追蹤。"""
    try:
        traces_dir = os.path.join(LOG_ROOT, 'traces')
        os.makedirs(traces_dir, exist_ok=True)
        log_path = os.path.join(traces_dir, f"{os.path.splitext(base_filename)[0]}.log")
        ts = time.strftime('%Y-%m-%d %H:%M:%S')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{ts}] {message}\n")
    except Exception:
        pass

def _merge_cornell_markdown(original_markdown: str, cornell_markdown: str, *, base_name: str) -> str:
    """Prefer Cornell markdown as primary note; keep legacy output as optional appendix."""
    cornell = (cornell_markdown or "").strip()
    primary = (original_markdown or "").strip()
    if not cornell:
        return original_markdown

    section_title = base_name.strip() or "Cornell 筆記摘要"
    parts = [cornell]
    if primary:
        parts.extend(
            [
                "",
                "---",
                "",
                f"## 🗒 系統原始摘要（{section_title} 備份）",
                "",
                primary,
            ]
        )
    merged = "\n".join(parts).rstrip() + "\n"
    return merged


def _build_cornell_structured_payload(
    cornell_payload: Dict[str, Any],
    *,
    base_name: str,
    filename: str,
    manifest: Optional[Dict[str, Any]],
    pipeline_trace: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Construct structured payload using Cornell synthesis output."""
    synthesis = cornell_payload.get("synthesis") or {}
    verification = cornell_payload.get("verification") or {}
    cues = synthesis.get("cue") or []
    notes = synthesis.get("notes") or []
    extends = synthesis.get("extend") or []
    formulas = synthesis.get("formulas") or []
    code_blocks = synthesis.get("code_blocks") or []

    structured_notes: List[Dict[str, Any]] = []
    max_count = max(len(cues), len(notes), len(extends), 1)
    for idx in range(max_count):
        cue_item = cues[idx] if idx < len(cues) else ""
        note_item = notes[idx] if idx < len(notes) else ""
        extend_item = extends[idx] if idx < len(extends) else ""
        supplements = [str(extend_item).strip()] if str(extend_item).strip() else []
        structured_notes.append(
            {
                "original": str(cue_item).strip(),
                "explanation": str(note_item).strip(),
                "supplements": supplements,
                "groundingValid": bool(str(cue_item).strip() or str(note_item).strip()),
            }
        )

    structured_code = None
    if code_blocks:
        block = code_blocks[0]
        if isinstance(block, dict):
            structured_code = {
                "lang": block.get("language") or "text",
                "code": block.get("code") or "",
                "title": block.get("title") or "",
            }

    payload: Dict[str, Any] = {
        "courseName": synthesis.get("title") or base_name,
        "title": synthesis.get("title") or base_name,
        "date": synthesis.get("date") or time.strftime("%Y/%m/%d"),
        "subject": synthesis.get("subject") or "待確認科目",
        "sourceVideo": filename,
        "quality": "good",
        "message": "Cornell 多模態筆記已生成",
        "ocrConfidence": verification.get("confidence") or 0.9,
        "notes": structured_notes,
        "summary": [str(item).strip() for item in cues if str(item).strip()],
        "extend": [str(item).strip() for item in extends if str(item).strip()],
        "formulas": [str(f).strip() for f in formulas if str(f).strip()],
        "code": structured_code,
        "verification": verification,
        "synthesis": synthesis,
        "noteStyle": "cornell",
        "useMarkdown": True,
    }
    if manifest:
        payload["promptManifest"] = manifest
    if pipeline_trace:
        payload["pipelineTrace"] = pipeline_trace
    return payload



def _build_vlm_only_structured_payload(
    *,
    base_name: str,
    filename: str,
    scene_summaries: List[Dict[str, Any]],
    final_note: str,
    language: str,
    manifest: Optional[Dict[str, Any]] = None,
    pipeline_trace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    """Generate structured payload purely from VLM scene summaries."""
    notes = []
    summary_points = []
    for scene in scene_summaries or []:
        summary_text = str(scene.get("summary") or "").strip()
        if not summary_text:
            continue
        title = scene.get("title") or f"場景 {int(scene.get('index', 0)) + 1}"
        notes.append(
            {
                "original": title,
                "explanation": summary_text,
                "supplements": [],
                "groundingValid": True,
            }
        )
        first_line = summary_text.splitlines()[0].strip()
        if first_line:
            summary_points.append(first_line)

    payload = {
        "courseName": base_name,
        "date": time.strftime("%Y/%m/%d"),
        "sourceVideo": filename,
        "ocrConfidence": 0.0,
        "ocrText": "",
        "notes": notes,
        "terms": [],
        "code": None,
        "qa": [],
        "summary": summary_points[:6],
        "tips": [
            "本次輸出使用 Qwen3-VL 多模態模型，自動略過 OCR。",
            "若需逐字稿或精確引用，可在設定中重新啟用 OCR。",
        ],
        "quality": "vlm-only" if notes else "vlm-summary",
        "message": "VLM 模式已生成講義重點（OCR 已停用）。",
    }
    if final_note:
        payload["final_note_excerpt"] = final_note[:800]
    if manifest:
        payload["promptManifest"] = manifest
    if pipeline_trace:
        payload["pipelineTrace"] = pipeline_trace
    return payload


def _get_video_duration_and_size(video_path):
    """Get video duration (seconds) and file size (bytes)."""
    duration = 0.0
    try:
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if fps and fps > 0:
            duration = frame_count / fps
        cap.release()
    except Exception:
        pass
    try:
        size_bytes = os.path.getsize(video_path) if os.path.exists(video_path) else 0
    except Exception:
        size_bytes = 0
    return duration, size_bytes

def _is_long_video(duration_sec, size_bytes):
    """Long video if duration >= 3600s or size >= 1.5GB."""
    return (duration_sec >= 3600) or (size_bytes >= 1_500_000_000)

def _pick_interval_for_duration(duration):
    """Pick fixed slicing interval by duration (seconds)."""
    if duration <= 300:
        return 120
    if duration <= 1200:
        return 180
    if duration <= 3600:
        return 240
    return 300

def _get_max_concurrency(config, long_mode=False):
    """Limit concurrency; stricter for long videos."""
    system_cfg = config.get('system', {}) if isinstance(config, dict) else {}
    num_workers = int(system_cfg.get('num_workers', 4))
    if long_mode:
        return max(1, min(2, num_workers // 2))
    return max(1, min(4, num_workers))


def _apply_thermal_guard(
    config: Dict[str, Any],
    max_concurrency: int,
    device: str,
    *,
    status_manager: Optional[StatusManager] = None,
    task_id: Optional[str] = None,
) -> tuple[Dict[str, Any], int, str, Dict[str, Any]]:
    runtime_cfg = config.get("runtime", {}) if isinstance(config, dict) else {}
    guard_cfg = runtime_cfg.get("thermal_guard", {}) if isinstance(runtime_cfg, dict) else {}
    guard_state = _THERMAL_GUARD.evaluate(guard_cfg)
    action = guard_state.get("action")

    updated = copy.deepcopy(config)
    ocr_cfg = updated.setdefault("ocr", {})
    batch_size = int(ocr_cfg.get("batch_size", 8) or 8)

    reduction_ratio = float(guard_cfg.get("ocr_batch_reduction_ratio", 0.5))
    min_batch = int(guard_cfg.get("min_ocr_batch_size", 2))
    max_cap = int(guard_cfg.get("max_concurrency_cap", max_concurrency))
    max_concurrency = min(max_concurrency, max_cap)

    if action == "throttle":
        new_batch = max(min_batch, int(max(1, batch_size * reduction_ratio)))
        ocr_cfg["batch_size"] = new_batch
        max_concurrency = max(1, min(max_concurrency, max_concurrency - 1))
    elif action == "force_cpu":
        ocr_cfg["use_gpu"] = False
        ocr_cfg["device_id"] = None
        device = "cpu"

    guard_state.update(
        {
            "ocr_batch_size": ocr_cfg.get("batch_size", batch_size),
            "max_concurrency": max_concurrency,
            "device": device,
        }
    )
    if status_manager and task_id:
        status_manager.update(task_id, {"thermal_guard": guard_state})
    return updated, max_concurrency, device, guard_state


def _resolve_scene_timeout(llm_config: Dict[str, Any], *, base_timeout: int = 150) -> int:
    """Derive a per-scene wait timeout that aligns with the active LLM budget."""
    min_timeout = 180
    max_timeout = 900
    candidates: List[int] = [base_timeout]

    def _coerce(value: Any) -> Optional[int]:
        try:
            if value is None:
                return None
            coerced = int(float(value))
            return coerced if coerced > 0 else None
        except (TypeError, ValueError):
            return None

    if isinstance(llm_config, dict):
        direct_timeout = _coerce(llm_config.get("timeout"))
        if direct_timeout:
            candidates.append(direct_timeout)

        provider_name = llm_config.get("provider") if isinstance(llm_config.get("provider"), str) else None
        provider_cfg = llm_config.get(provider_name or "ollama")
        if isinstance(provider_cfg, dict):
            provider_timeout = _coerce(provider_cfg.get("timeout"))
            if provider_timeout:
                candidates.append(provider_timeout)

    resolved = max(candidates)
    resolved = max(min_timeout, resolved)
    resolved = min(max_timeout, resolved)
    return resolved


def _get_whisper_model(config, prefer_fast=False, force_cpu=False):
    """Get/cache Whisper model with GPU->CPU fallback. Returns None if Whisper not available."""
    if not WHISPER_AVAILABLE:
        logger.warning("⚠️ Whisper 不可用,跳過音訊處理")
        return None
    
    from faster_whisper import WhisperModel
    whisper_cfg = (config or {}).get('whisper', {})
    
    # 檢查配置中是否明確停用
    if not whisper_cfg.get('enabled', True):
        logger.info("ℹ️ Whisper 在配置中已停用")
        return None
    
    base_model_size = whisper_cfg.get('model_size', 'large')
    device = whisper_cfg.get('device', 'cuda')
    compute_type = whisper_cfg.get('compute_type', 'float16')

    model_size = base_model_size
    if prefer_fast:
        model_size = 'medium' if (device in ['cuda', 'gpu'] and not force_cpu) else 'small'

    use_device = 'cuda' if (device in ['cuda', 'gpu'] and not force_cpu) else 'cpu'
    use_compute = compute_type if use_device == 'cuda' else 'int8'

    cache_key = (model_size, use_device, use_compute)
    if cache_key in _WHISPER_MODEL_CACHE:
        return _WHISPER_MODEL_CACHE[cache_key]

    try:
        model = WhisperModel(
            model_size,
            device=use_device,
            compute_type=use_compute,
            download_root="/app/models/whisper",
            local_files_only=False
        )
        _WHISPER_MODEL_CACHE[cache_key] = model
        return model
    except Exception as e:
        logger.error(f"Whisper load failed, fallback to CPU small/int8: {e}")
        try:
            fallback_key = ('small', 'cpu', 'int8')
            if fallback_key in _WHISPER_MODEL_CACHE:
                return _WHISPER_MODEL_CACHE[fallback_key]
            model = WhisperModel(
                'small', device='cpu', compute_type='int8',
                download_root="/app/models/whisper", local_files_only=False
            )
            _WHISPER_MODEL_CACHE[fallback_key] = model
            return model
        except Exception as e2:
            logger.error(f"Whisper CPU small load failed: {e2}")
            return None  # 失敗時返回 None 而非拋出異常

async def summarize(
    filename,
    video_path,
    config,
    llm_config,
    status_manager: StatusManager,
    with_images=True,
    device="gpu",
    reuse_images=False,
    parse_audio=True,
    language="zh-TW",
    include_japanese=True,
    force_fixed_segments=True,
    segment_minutes=15,
):
    """
    影片摘要主函數（V2 - 兩階段摘要）
    filename: 用作狀態鍵的完整路徑
    video_path: 影片檔案的實際路徑
    """
    config = copy.deepcopy(config) if isinstance(config, dict) else {}
    runtime_state = config.get("_runtime", {}) if isinstance(config, dict) else {}
    if isinstance(runtime_state, dict):
        active_runtime = runtime_state.get("active_device") or device or "cpu"
        ocr_runtime = runtime_state.get("ocr", {})
        ocr_device = ocr_runtime.get("device", device or "cpu") or "cpu"
        device = ocr_device
    else:
        active_runtime = device or "cpu"
        device = device or "cpu"

    logger.info(f"[summarize] ⚡⚡⚡ MODULE VERSION v2025-10-03-15:30-DEBUG ⚡⚡⚡")
    logger.info(f"[summarize] 函數被調用 - filename: {filename}")
    logger.info(f"[summarize] 開始處理影片: {filename}")
    _trace_write(os.path.basename(filename), f"start with_images={with_images}, device={device}, parse_audio={parse_audio}, lang={language}, jp={include_japanese}")
    logger.info(
        "[summarize] 處理參數 - with_images: %s, device: %s, parse_audio: %s, runtime_device: %s",
        with_images,
        device,
        parse_audio,
        active_runtime,
    )
    ocr_enabled = is_ocr_enabled(config)
    if not ocr_enabled:
        logger.info("[summarize] OCR 已全域停用，流程將以 Qwen3-VL 多模態輸出為主")

    timings: Dict[str, Any] = {}
    overall_start = time.perf_counter()
    
    # 提取基本檔案名用於處理
    base_filename = os.path.basename(filename)
    
    if not os.path.exists(video_path):
        resolved_video_path = _resolve_video_path(video_path)
        logger.info(f"[summarize] 重新解析影片路徑: {video_path} -> {resolved_video_path}")
        video_path = resolved_video_path

    if not os.path.exists(video_path):
        error_msg = f'影片檔案不存在: {video_path}'
        logger.error(f"[summarize] {error_msg}")
        raise FileNotFoundError(error_msg)

    temp_dir = None # 初始化为 None
    try:
        temp_dir = tempfile.mkdtemp()
        logger.info(f"[summarize] 創建臨時目錄: {temp_dir}")
        update_status(filename, "處理中", 5, "初始化完成，準備偵測場景...", status_manager, stage="ingest")

        # 前置：修復不可讀 mp4（moov 缺失等）
        safe_video_path = _ensure_readable_mp4(video_path, temp_dir)
        _trace_write(base_filename, f"ensure_readable -> {os.path.basename(safe_video_path)}")

        # Inspect video properties and decide long-mode strategy
        duration_sec, size_bytes = _get_video_duration_and_size(safe_video_path)
        long_mode = _is_long_video(duration_sec, size_bytes)
        short_clip_limit = 120.0  # 兩分鐘以下視為短片，保留單段流程以避免過度切片
        short_clip = duration_sec > 0 and duration_sec <= short_clip_limit
        # 🔧 修復: 允許中長片(≤120分鐘且≤1.5GB)保留截圖與圖片解析，以兼顧品質
        # 原本: 5400秒(90分鐘) → 修改為: 7200秒(120分鐘)
        # 原本: 1.2GB → 修改為: 1.5GB
        allow_images_in_long = (duration_sec <= 7200) and (size_bytes <= 1_500_000_000)
        if with_images and not WHISPER_AVAILABLE:
            # Whisper 不可用時，強制保留圖片流程，避免長片只有空白摘要
            allow_images_in_long = True
        effective_with_images = with_images and (not long_mode or allow_images_in_long)
        if with_images and long_mode and not allow_images_in_long and not effective_with_images:
            update_status(filename, "處理中", 6, "偵測到超長影片，為穩定性自動關閉截圖處理", status_manager, stage="scene-detection")

        # --- 第一階段：切片策略（支援固定 15 分鐘切片） ---
        t_scene_detect = time.perf_counter()
        logger.info("[summarize] 準備切片策略")
        scenes = []
        if force_fixed_segments:
            if short_clip:
                scenes = [(0.0, duration_sec, 0)]
                update_status(
                    filename,
                    "處理中",
                    8,
                    "偵測到短片段，整段直接分析",
                    status_manager,
                    stage="scene-detection",
                )
                logger.info(
                    "[summarize] 短片模式啟用：影片長度 %.1f 秒，使用單段流程",
                    duration_sec,
                )
            else:
                # 使用固定長度切片（預設 15 分鐘；避免系統崩潰、便於後續合併）
                interval = max(60, int(segment_minutes) * 60)
                scenes = get_fixed_interval_scenes(safe_video_path, interval=interval)
                update_status(
                    filename,
                    "處理中",
                    8,
                    f"固定切片：每 {interval} 秒一段",
                    status_manager,
                    stage="scene-detection",
                )
                logger.info(f"[summarize] 使用固定切片，共 {len(scenes)} 段 (每段 {interval}s)")
        else:
            logger.info("[summarize] 開始場景偵測")
            if short_clip and duration_sec > 0:
                scenes = [(0.0, duration_sec, 0)]
                update_status(
                    filename,
                    "處理中",
                    8,
                    "偵測到短片段，整段直接分析",
                    status_manager,
                    stage="scene-detection",
                )
                logger.info(
                    "[summarize] 短片模式啟用：影片長度 %.1f 秒，使用單段流程",
                    duration_sec,
                )
            elif long_mode:
                interval = _pick_interval_for_duration(duration_sec)
                scenes = get_fixed_interval_scenes(safe_video_path, interval=interval)
                update_status(
                    filename,
                    "處理中",
                    8,
                    f"長片優化：以每 {interval} 秒自動切片",
                    status_manager,
                    stage="scene-detection",
                )
            else:
                scenes = detect_scenes(safe_video_path, config)
        if not scenes:
            error_msg = "無法偵測到任何場景"
            logger.error(f"[summarize] {error_msg}")
            update_status(filename, "錯誤", 100, error_msg, status_manager, stage="error")
            raise ValueError(error_msg)

        output_cfg = (config or {}).get("output", {}) if isinstance(config, dict) else {}
        requested_note_style = str(output_cfg.get("note_style", "")).strip().lower()
        selected_scenes = _select_scenes_for_note_style(scenes, requested_note_style)
        if len(selected_scenes) != len(scenes):
            logger.info(
                "[summarize] 依筆記風格調整場景數：%s -> %s (style=%s)",
                len(scenes),
                len(selected_scenes),
                requested_note_style,
            )
        scenes = selected_scenes

        timings["scene_detection_sec"] = round(time.perf_counter() - t_scene_detect, 2)
        total_scenes = len(scenes)
        logger.info(f"[summarize] 偵測到 {total_scenes} 個場景")
        _trace_write(base_filename, f"scenes_detected={total_scenes}")
        update_status(filename, "處理中", 10, f"偵測到 {total_scenes} 個場景，開始並行處理...", status_manager, stage="scene-detection")

        # 提前通報即將進入 OCR/VLM 流程，便於前端呈現
        update_status(
            filename,
            "處理中",
            20 if total_scenes else 15,
            "開始執行場景截圖的 OCR 與多模態分析...",
            status_manager,
            stage="ocr",
        )

        scene_summaries = []
        # Concurrency guard to avoid GPU/Memory spike, stricter in long-mode
        # 強化：長片強制單工，避免高溫/資源吃滿
        max_concurrency = 1 if long_mode else _get_max_concurrency(config, long_mode=long_mode)
        config, max_concurrency, device, guard_state = _apply_thermal_guard(
            config,
            max_concurrency,
            device,
            status_manager=status_manager,
            task_id=filename,
        )
        if guard_state.get("action") not in {"ok", "recover"}:
            logger.warning(
                "[summarize] Thermal guard action=%s temp=%s",
                guard_state.get("action"),
                guard_state.get("temp_c"),
            )
        semaphore = asyncio.Semaphore(max_concurrency)

        # 簡易的圖片近重判斷：使用感知雜湊（pHash）與清晰度判斷（Laplacian variance）
        # 為了避免在各協程內跨場景混用狀態，這裡採用共享字典 + 互斥鎖控制
        import threading
        phash_lock = threading.Lock()
        recent_hashes = []  # [(phash_int, sharpness, img_abs_path)]

        def _compute_phash(image_path):
            try:
                import cv2
                import numpy as np
                img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
                if img is None:
                    return None
                img = cv2.resize(img, (32, 32))
                dct = cv2.dct(np.float32(img))
                dct_low = dct[:8, :8]
                median = np.median(dct_low)
                bits = (dct_low > median).flatten()
                ph = 0
                for b in bits:
                    ph = (ph << 1) | int(bool(b))
                return ph
            except Exception:
                return None

        def _hamming_distance(x, y):
            v = (x ^ y) if (x is not None and y is not None) else 64
            return int(bin(v).count("1"))

        def _variance_of_laplacian(image_path):
            try:
                import cv2
                img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
                if img is None:
                    return 0.0
                return float(cv2.Laplacian(img, cv2.CV_64F).var())
            except Exception:
                return 0.0

        def _scene_to_structured(scene: Dict[str, Any]) -> Dict[str, Any]:
            """Convert a scene summary into a lightweight structured payload."""
            if not isinstance(scene, dict):
                return {}
            start = float(scene.get("start") or 0.0)
            end = float(scene.get("end") or 0.0)
            duration = float(scene.get("duration") or max(0.0, end - start))
            image_path = (
                scene.get("image_path_final")
                or scene.get("image_path")
                or ""
            )
            return {
                "index": int(scene.get("index", 0)),
                "start": start,
                "end": end,
                "duration": duration,
                "summary": (scene.get("summary") or "").strip(),
                "asr": scene.get("asr_text") or "",
                "ocr": scene.get("ocr_text") or "",
                "jpTopLines": scene.get("jp_top_lines") or [],
                "image": image_path,
                "weight": scene.get("scene_weight"),
                "focus": scene.get("visual_focus") or scene.get("structured_summary") or "",
            }

        def _deduplicate_scene_texts(summaries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            """強化去重邏輯 - 使用語義相似度過濾重複場景"""
            if not summaries:
                return []
            
            def _normalize_text(text: str) -> str:
                """標準化文本用於比較"""
                import re
                # 移除空白字符、標點、數字
                normalized = re.sub(r'[\s\d\W]+', '', text.lower())
                return normalized
            
            def _text_similarity(text1: str, text2: str) -> float:
                """簡單的文本相似度計算（字符級別）"""
                if not text1 or not text2:
                    return 0.0
                norm1 = _normalize_text(text1)
                norm2 = _normalize_text(text2)
                if not norm1 or not norm2:
                    return 0.0
                # 計算最長公共子序列比例
                shorter = min(len(norm1), len(norm2))
                longer = max(len(norm1), len(norm2))
                if longer == 0:
                    return 0.0
                # 簡化：檢查較短文本是否大部分包含在較長文本中
                if shorter / longer < 0.3:  # 長度差異太大
                    return 0.0
                common_chars = sum(1 for c in norm1 if c in norm2)
                return common_chars / longer
            
            seen_scenes = []
            cleaned = []
            summary_threshold = 0.92
            ocr_threshold = 0.95
            summary_only_threshold = 0.96
            ocr_only_threshold = 0.97
            
            for scene in summaries:
                if not isinstance(scene, dict):
                    continue
                
                summary_text = str(scene.get("summary") or "").strip()
                ocr_text = str(scene.get("ocr_text") or "").strip()
                
                if not (summary_text or ocr_text):
                    continue
                
                # 檢查是否與已有場景相似
                is_duplicate = False
                for prev_scene in seen_scenes:
                    prev_summary = str(prev_scene.get("summary") or "").strip()
                    prev_ocr = str(prev_scene.get("ocr_text") or "").strip()
                    
                    summary_sim = _text_similarity(summary_text, prev_summary) if summary_text and prev_summary else 0.0
                    ocr_sim = _text_similarity(ocr_text, prev_ocr) if ocr_text and prev_ocr else 0.0
                    summary_hit = summary_sim >= summary_threshold
                    ocr_hit = ocr_sim >= ocr_threshold

                    # 同時滿足摘要與 OCR，才視為高度重複
                    if summary_hit and ocr_hit:
                        logger.info(
                            "[去重] 場景 %s 摘要+OCR 與場景 %s 重複 (summary=%.2f, ocr=%.2f)",
                            scene.get("index"),
                            prev_scene.get("index"),
                            summary_sim,
                            ocr_sim,
                        )
                        is_duplicate = True
                        break

                    # 僅有摘要或僅有 OCR 時，提高門檻
                    if summary_text and prev_summary and not (ocr_text or prev_ocr):
                        if summary_sim >= summary_only_threshold:
                            logger.info(
                                "[去重] 場景 %s 摘要與場景 %s 重複 (summary=%.2f)",
                                scene.get("index"),
                                prev_scene.get("index"),
                                summary_sim,
                            )
                            is_duplicate = True
                            break
                    if ocr_text and prev_ocr and not (summary_text or prev_summary):
                        if ocr_sim >= ocr_only_threshold:
                            logger.info(
                                "[去重] 場景 %s OCR 與場景 %s 重複 (ocr=%.2f)",
                                scene.get("index"),
                                prev_scene.get("index"),
                                ocr_sim,
                            )
                            is_duplicate = True
                            break
                
                if not is_duplicate:
                    seen_scenes.append(scene)
                    cleaned.append(scene)
            
            logger.info(f"[去重] 原始場景: {len(summaries)}, 去重後: {len(cleaned)}, 移除: {len(summaries) - len(cleaned)}")
            return cleaned

        def _annotate_scene_weights(summaries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            if not summaries:
                return []
            for scene in summaries:
                if not isinstance(scene, dict):
                    continue
                summary_text = str(scene.get("summary") or "")
                ocr_text = str(scene.get("ocr_text") or "")
                asr_text = str(scene.get("asr_text") or "")
                weight = 0.0
                if summary_text.strip() or ocr_text.strip() or asr_text.strip():
                    weight = 1.0
                if scene.get("image_path_final") or scene.get("image_path"):
                    weight += 0.2
                if len(summary_text.strip()) >= 200:
                    weight += 0.2
                scene["scene_weight"] = round(weight, 2)
            return summaries

        def _filter_low_value_scenes(summaries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            if not summaries:
                return []
            filtered = []
            for scene in summaries:
                if not isinstance(scene, dict):
                    continue
                summary_text = str(scene.get("summary") or "").strip()
                ocr_text = str(scene.get("ocr_text") or "").strip()
                asr_text = str(scene.get("asr_text") or "").strip()
                if not (summary_text or ocr_text or asr_text):
                    continue
                weight = float(scene.get("scene_weight") or 0.0)
                if weight <= 0:
                    continue
                filtered.append(scene)
            return filtered

        # 【修改】取消 fast_mode 限制,永遠啟用圖片分析來提取講義內容

        # 即使是短片也需要 OCR 來提取講義截圖上的文字
        fast_mode = False  # ✅ 強制關閉快速模式,確保提取講義內容

        scene_timeout_sec = _resolve_scene_timeout(llm_config)
        provider_timeout_hint = None
        llm_timeout_hint = None
        if isinstance(llm_config, dict):
            llm_timeout_hint = llm_config.get("timeout")
            provider_name = llm_config.get("provider") if isinstance(llm_config.get("provider"), str) else None
            provider_cfg = llm_config.get(provider_name or "ollama")
            if isinstance(provider_cfg, dict):
                provider_timeout_hint = provider_cfg.get("timeout")
        logger.info(
            "[summarize] 場景分析超時限制: %ss (llm.timeout=%s, provider timeout=%s)",
            scene_timeout_sec,
            llm_timeout_hint,
            provider_timeout_hint,
        )

        async def _sem_task(scene_data):
            async with semaphore:
                try:
                    scene_config = config
                    scene_device = device
                    guard_cfg = (config.get("runtime", {}) or {}).get("thermal_guard", {})
                    guard_state = _THERMAL_GUARD.evaluate(guard_cfg)
                    if guard_state.get("action") == "force_cpu":
                        scene_config = copy.deepcopy(config)
                        scene_config.setdefault("ocr", {})["use_gpu"] = False
                        scene_config.setdefault("ocr", {})["device_id"] = None
                        scene_device = "cpu"
                        status_manager.update(filename, {"thermal_guard": guard_state})
                    elif guard_state.get("action") == "throttle":
                        scene_config = copy.deepcopy(config)
                        ocr_cfg = scene_config.setdefault("ocr", {})
                        batch_size = int(ocr_cfg.get("batch_size", 8) or 8)
                        reduction_ratio = float(guard_cfg.get("ocr_batch_reduction_ratio", 0.5))
                        min_batch = int(guard_cfg.get("min_ocr_batch_size", 2))
                        ocr_cfg["batch_size"] = max(min_batch, int(max(1, batch_size * reduction_ratio)))
                        status_manager.update(filename, {"thermal_guard": guard_state})

                    # 啟用完整 OCR + VLM 分析
                    task_coro = process_scene(
                        base_filename,
                        safe_video_path,
                        scene_data,
                        temp_dir,
                        scene_device,
                        effective_with_images,
                        scene_config,
                        llm_config,
                        parse_audio,
                        skip_ocr=False,
                        language=language,
                        include_japanese=include_japanese,
                        long_mode=long_mode,
                        ocr_enabled=ocr_enabled,
                    )
                    # 【優化】依據 LLM 設定調整每個場景的耐心時間
                    timeout_sec = scene_timeout_sec
                    result = await asyncio.wait_for(task_coro, timeout=timeout_sec)
                except asyncio.TimeoutError:
                    # 【降級方案】超時時使用輕量 OCR 提取文字,而不是完全放棄
                    logger.warning(
                        f"⏰ 場景處理超時 ({timeout_sec}秒),啟用輕量 OCR 降級方案: {scene_data}"
                    )
                    
                    idx = scene_data[2] if len(scene_data) == 3 else 0
                    start = scene_data[0]
                    end = scene_data[1]
                    
                    # 嘗試快速提取 OCR
                    fallback_ocr = ""
                    fallback_img_path = ""
                    final_fallback_image = ""
                    if ocr_enabled:
                        try:
                            from modules.core.ocr_utils import ocr_manager
                            mid_time = (start + end) / 2
                            img_path = extract_scene_image(safe_video_path, start, end, temp_dir, idx) if effective_with_images else None

                            if img_path and os.path.exists(img_path):
                                structured = ocr_manager.extract_with_meta(img_path, config, device)
                                if isinstance(structured, dict):
                                    fallback_ocr = structured.get("text", "")
                                else:
                                    fallback_ocr = str(structured or "")
                                fallback_img_path = img_path
                                try:
                                    base_name = os.path.splitext(base_filename)[0]
                                    output_dir = os.path.join(OUTPUT_IMAGES_ROOT, base_name)
                                    os.makedirs(output_dir, exist_ok=True)
                                    img_name = f"scene_{idx:03d}.jpg"
                                    final_abs_path = os.path.join(output_dir, img_name)
                                    shutil.copy(fallback_img_path, final_abs_path)
                                    from urllib.parse import quote
                                    final_fallback_image = f"/images/{quote(base_name)}/{img_name}"
                                    logger.info("✅ 降級 OCR 圖片已保存: %s", final_abs_path)
                                except Exception as copy_exc:
                                    logger.error("❌ 降級 OCR 圖片保存失敗: %s", copy_exc)
                                    final_fallback_image = ""
                                logger.info(f"✅ 降級 OCR 成功,提取 {len(fallback_ocr)} 字元,圖片: {img_path}")
                        except Exception as ocr_err:
                            logger.error(f"❌ 降級 OCR 失敗: {ocr_err}")
                    
                    result = {
                        'index': idx,
                        'start': float(start),
                        'end': float(end),
                        'duration': float(max(0.0, (end or 0) - (start or 0))),
                        'summary': f'**場景摘要** (降級模式):\n\n從投影片提取的內容:\n{fallback_ocr[:500] if fallback_ocr else "(無法提取)"}',
                        'image_path_final': final_fallback_image,  # 🔧 降級模式仍使用最終輸出路徑
                        'asr_text': '',
                        'ocr_text': fallback_ocr,  # ✅ 使用降級 OCR 而不是空字串
                        'jp_top_lines': []
                    }

                # 圖片近重過濾：
                try:
                    img_rel = (result or {}).get('image_path_final') or ""
                    if img_rel:
                        # 轉回本機輸出路徑
                        from urllib.parse import unquote
                        decoded = unquote(img_rel)
                        abs_img = os.path.join(OUTPUT_ROOT, decoded.lstrip('/'))
                        if os.path.exists(abs_img):
                            ph = _compute_phash(abs_img)
                            sharp = _variance_of_laplacian(abs_img)
                            is_duplicate = False
                            replace_index = None
                            with phash_lock:
                                for idx_h, (old_ph, old_sharp, old_path) in enumerate(recent_hashes[-8:]):
                                    # 近鄰窗口 8 張
                                    if old_ph is None or ph is None:
                                        continue
                                    if _hamming_distance(ph, old_ph) <= 5:
                                        # 視為近重，保留更清晰者
                                        is_duplicate = True
                                        # 找到舊記錄在 recent_hashes 的實際索引
                                        replace_index = len(recent_hashes) - 8 + idx_h
                                        break

                                if is_duplicate and replace_index is not None:
                                    old_ph, old_sharp, old_path = recent_hashes[replace_index]
                                    if sharp > old_sharp:
                                        recent_hashes[replace_index] = (ph, sharp, abs_img)
                                    logger.info(
                                        "[summarize] 偵測到近重圖片（distance<=5），保留原始檔避免章節圖片引用失效: old=%s current=%s",
                                        old_path,
                                        abs_img,
                                    )
                                else:
                                    # 非近重，記錄
                                    recent_hashes.append((ph, sharp, abs_img))
                                    # 控制窗口大小
                                    if len(recent_hashes) > 32:
                                        recent_hashes[:] = recent_hashes[-32:]
                except Exception:
                    # 近重判斷失敗不阻斷主流程
                    pass

                return result

        t_scene_process = time.perf_counter()
        tasks = [_sem_task(scene_data) for scene_data in scenes]

        results = []
        for i in range(0, len(tasks)):
            batch_results = await asyncio.gather(tasks[i], return_exceptions=True)
            results.extend(batch_results)
            # 節流：處理每段之間小睡，降低熱點
            await asyncio.sleep(0.2 if long_mode else 0.05)

            scene_index = i
            for result in batch_results:
                if isinstance(result, Exception):
                    error_msg = f"場景 {scene_index} 處理失敗: {result}"
                    logger.error(f"[summarize] {error_msg}")
                    logger.error(f"[summarize] 詳細錯誤跟踪: {traceback.format_exc()}")
                    update_status(
                        filename,
                        "警告",
                        int(50 + 40 * scene_index/total_scenes),
                        f"場景 {scene_index} 處理失敗，跳過...",
                        status_manager,
                        stage="vlm",
                    )
                else:
                    if result:
                        scene_summaries.append(result)
                progress = 10 + int(80 * (scene_index + 1) / max(total_scenes,1))
                update_status(
                    filename,
                    "處理中",
                    progress,
                    f"處理場景 {scene_index+1}/{total_scenes}...",
                    status_manager,
                    stage="vlm",
                )
        timings["scene_processing_sec"] = round(time.perf_counter() - t_scene_process, 2)

        scene_summaries.sort(key=lambda x: x['index'])
        logger.info(f"[summarize] 成功處理 {len(scene_summaries)} 個場景，開始內容去重")
        logger.info(f"[summarize] 🔍 去重前 scene_summaries 內容: {scene_summaries[:1] if scene_summaries else '空'}")

        # 內容去重（文字層級）：基於 ASR 與摘要文本的簡易相似度
        scene_summaries = _deduplicate_scene_texts(scene_summaries)
        scene_summaries = _annotate_scene_weights(scene_summaries)
        logger.info(f"[summarize] 去重後剩餘 {len(scene_summaries)} 個有效場景")
        if scene_summaries:
            logger.info(
                "[summarize] 🔍 第 1 段權重: %.2f",
                scene_summaries[0].get('scene_weight', 0.0),
            )

        if not short_clip:
            original_map = {sc.get('index'): sc for sc in scene_summaries}
            filtered = _filter_low_value_scenes(scene_summaries)
            removed_indices = sorted(set(original_map) - {sc.get('index') for sc in filtered})
            if removed_indices:
                logger.info(f"[summarize] 移除 {len(removed_indices)} 個低權重場景以提升內容純度")
                for ridx in removed_indices:
                    weight = original_map[ridx].get('scene_weight', 0.0)
                    _trace_write(base_filename, f"scene#{ridx} filtered_low_weight={weight:.2f}")
            scene_summaries = filtered
        else:
            logger.info("[summarize] 短片段模式：保留所有場景供筆記生成 (共 %s 段)", len(scene_summaries))
        
        # 主動釋放資源（簡單GC提示）
        try:
            import gc
            gc.collect()
        except Exception:
            pass
        
        # --- 第二階段：最終筆記整合 ---
        update_status(filename, "處理中", 90, "所有場景處理完畢，正在整合筆記...", status_manager, stage="formatting")
        logger.info("[summarize] 開始最終筆記整合")
        _trace_write(base_filename, f"merging {len(scene_summaries)} scene results")

        base_name = os.path.splitext(base_filename)[0]

        # 關閉 fallback：一律走 NoteGenerator 產生完整長文
        note_generator = create_note_generator(llm_config)
        if isinstance(config, dict):
            try:
                note_generator.set_runtime_config(config)
            except Exception as cfg_exc:
                logger.debug("[summarize] 注入 runtime config 失敗，改用預設設定: %s", cfg_exc)
        
        logger.info(f"[summarize] 🚀 準備進入 generate_final_summary 流程")
        # 生成最終總結
        logger.info(f"[summarize] 📢 準備調用 generate_final_summary, scene_summaries 數量: {len(scene_summaries)}")
        logger.info(f"[summarize] 📢 scene_summaries 類型: {type(scene_summaries)}")
        if scene_summaries:
            logger.info(f"[summarize] 📢 第一個場景: {scene_summaries[0]}")
        t_merge = time.perf_counter()
        final_note, structured_summaries = await note_generator.generate_final_summary(
            scene_summaries, language, include_japanese
        )
        timings["merge_sec"] = round(time.perf_counter() - t_merge, 2)
        logger.info(f"[summarize] 📢 generate_final_summary 返回完成")
        
        # 後處理：插入實際的圖片路徑
        logger.info("[summarize] 開始後處理圖片路徑")
        note_metadata = getattr(note_generator, "last_note_metadata", {}) or {}
        if note_metadata.get("note_style") in {"transcript", "meeting"}:
            final_note_with_images = final_note
        else:
            final_note_with_images = note_generator.format_video_note(
                final_note, structured_summaries, base_name, language, include_japanese
            )
        _trace_write(base_filename, f"final_note_length={len(final_note_with_images) if isinstance(final_note_with_images, str) else 'NA'}")

        # ⚠️ 注意: 不要在這裡設置 '完成',因為文件還沒寫入
        # main.py 會在寫入文件後設置 status_code='completed' 和 result_path
        update_status(filename, "處理中", 95, "正在保存結果...", status_manager, stage="saving")
        logger.info(f"[summarize] 筆記生成成功,等待文件寫入: {filename}")
        
        # 構建結構化 JSON（使用新的 Grounding 驗證系統）
        def _clean_ocr_noise(text: str) -> str:
            try:
                import re
                return (
                    re.sub(r"https?://\S+", "", text or "")
                    .replace("Start Recording", "")
                    .replace("stop recording", "")
                )
            except Exception:
                return text or ""

        # 收集所有 OCR 文本用於 Grounding 驗證
        all_ocr_text = ""
        logger.info(f"[DEBUG] 🔍 scene_summaries 數量: {len(scene_summaries) if scene_summaries else 0}")
        
        for i, scene in enumerate(scene_summaries or []):
            scene_ocr = scene.get('ocr_text', '')
            if scene_ocr:
                # 過濾個人資訊
                scene_ocr = _filter_personal_info(scene_ocr)
                all_ocr_text += scene_ocr + "\n"
                logger.info(f"[DEBUG] Scene {i} 有 OCR: 長度={len(scene_ocr)}, 前50字='{scene_ocr[:50]}'")
            else:
                if ocr_enabled:
                    logger.warning(f"[DEBUG] Scene {i} 無 OCR 文本!")
        
        # 調試：記錄實際的 OCR 內容
        logger.info(f"[DEBUG] ✅ 實際 OCR 內容長度: {len(all_ocr_text)}")
        logger.info(f"[DEBUG] 📝 實際 OCR 內容前 500 字符: {all_ocr_text[:500]}")

        pipeline_trace_payload = None
        cornell_manifest = None
        cornell_result_payload: Optional[Dict[str, Any]] = None
        cornell_bundle: Optional[Dict[str, Any]] = None
        cornell_structured_payload: Optional[Dict[str, Any]] = None
        cornell_progress_set = False
        try:
            cornell_skip_reason = None
            if not ocr_enabled:
                cornell_skip_reason = "OCR 已停用"
            else:
                primary_scene = next(
                    (scene for scene in (scene_summaries or []) if scene.get("image_path_final")), None
                )
                if not primary_scene:
                    cornell_skip_reason = "找不到帶圖片的場景"
                else:
                    image_web_path = str(primary_scene.get("image_path_final") or "").strip()
                    image_fs_path = convert_web_path_to_fs(image_web_path)
                    primary_ocr_text = (primary_scene.get("ocr_text") or "").strip()
                    if not image_fs_path or not os.path.exists(image_fs_path):
                        cornell_skip_reason = "主要場景圖片不存在"
                    elif not primary_ocr_text:
                        cornell_skip_reason = "主要場景缺少 OCR 文字"
                    else:
                        trace = PipelineTrace()
                        trace.mark_started(
                            "ocr",
                            detail=f"scene_index={primary_scene.get('index', 0)}",
                        )
                        trace.mark_completed(
                            "ocr",
                            detail=f"text_len={len(primary_ocr_text)}",
                        )
                        release_cuda_cache(reason="before_cornell_pipeline")
                        pipeline = CornellNotePipeline(llm_config)
                        status_manager.update(
                            filename,
                            {
                                "progress": 92,
                                "detail": "🤖 Cornell 管線：校對 OCR 與生成筆記...",
                                "current_stage": "cornell_pipeline",
                            },
                        )
                        context_snippet = (final_note_with_images or "")[:4000]
                        structured_hint = (
                            primary_scene.get("structured_summary")
                            or primary_scene.get("visual_focus")
                            or ""
                        )
                        cornell_result = await asyncio.wait_for(
                            pipeline.run(
                                image_path=image_fs_path,
                                ocr_text=primary_ocr_text,
                                structured_hint=structured_hint,
                                context=context_snippet,
                                image_summary=context_snippet,
                                suggested_title=base_name,
                                subject_hint="",
                                pipeline_trace=trace,
                            ),
                            timeout=240,
                        )
                        cornell_result_payload = dict(cornell_result)
                        cornell_markdown = cornell_result_payload.get("markdown") or ""
                        final_note_with_images = _merge_cornell_markdown(
                            final_note_with_images,
                            cornell_markdown,
                            base_name=base_name,
                        )
                        pipeline_trace_payload = cornell_result_payload.get("pipeline_trace")
                        cornell_manifest = {
                            "id": cornell_result_payload.get("manifest_id"),
                            "version": cornell_result_payload.get("manifest_version"),
                            "hash": cornell_result_payload.get("manifest_hash"),
                        }
                        cornell_manifest = {k: v for k, v in cornell_manifest.items() if v}
                        if cornell_manifest:
                            note_metadata.setdefault("prompt_manifest", cornell_manifest)
                        note_metadata.setdefault("pipeline_trace", pipeline_trace_payload)
                        note_metadata["note_style"] = "cornell"
                        cornell_bundle = {
                            "markdown": cornell_markdown or "",
                            "manifest": cornell_manifest or None,
                            "verification": cornell_result_payload.get("verification"),
                            "synthesis": cornell_result_payload.get("synthesis"),
                            "pipeline_trace": pipeline_trace_payload,
                            "scene_index": primary_scene.get("index"),
                            "scene_image": image_web_path,
                        }
                        note_metadata.setdefault("cornell", cornell_bundle)
                        cornell_structured_payload = _build_cornell_structured_payload(
                            cornell_result_payload,
                            base_name=base_name,
                            filename=filename,
                            manifest=cornell_manifest,
                            pipeline_trace=pipeline_trace_payload,
                        )
                        if cornell_bundle:
                            cornell_structured_payload["cornell"] = cornell_bundle
                        structured_data = cornell_structured_payload
                        release_cuda_cache(reason="after_cornell_pipeline")
                        status_manager.update(
                            filename,
                            {
                                "progress": 94,
                                "detail": "✅ Cornell 管線完成，準備保存筆記...",
                                "current_stage": "cornell_pipeline_completed",
                            },
                        )
                        cornell_progress_set = True
            if cornell_skip_reason:
                logger.info(f"[summarize] Cornell 管線略過：{cornell_skip_reason}")
                status_manager.update(
                    filename,
                    {
                        "progress": 94,
                        "detail": f"ℹ️ Cornell 管線略過：{cornell_skip_reason}",
                        "current_stage": "cornell_pipeline_skipped",
                    },
                )
                cornell_progress_set = True
        except asyncio.TimeoutError:
            logger.error("[summarize] Cornell 管線逾時，改用原始筆記")
            status_manager.update(
                filename,
                {
                    "progress": 94,
                    "detail": "⚠️ Cornell 管線逾時，改用主筆記",
                    "current_stage": "cornell_pipeline_timeout",
                },
            )
            cornell_progress_set = True
        except Exception as cornell_exc:
            logger.error(f"[summarize] Cornell 管線執行失敗: {cornell_exc}")
            status_manager.update(
                filename,
                {
                    "progress": 94,
                    "detail": "⚠️ Cornell 管線失敗，改用主筆記",
                    "current_stage": "cornell_pipeline_failed",
                },
            )
            cornell_progress_set = True
        finally:
            if not cornell_progress_set:
                status_manager.update(
                    filename,
                    {
                        "progress": 94,
                        "detail": "ℹ️ Cornell 管線略過，使用主筆記",
                        "current_stage": "cornell_pipeline_skipped",
                    },
                )

        # 使用新的 Grounding 驗證系統生成結構化內容
        from modules.llm_utils import get_grounded_analysis_prompt
        
        # 檢查 OCR 文本品質
        ocr_quality = "good"
        ocr_confidence = 0.8
        if not all_ocr_text.strip() or len(all_ocr_text.strip()) < 50:
            ocr_quality = "poor"
            ocr_confidence = 0.3
        elif len(all_ocr_text.strip()) < 100:
            ocr_quality = "fair"
            ocr_confidence = 0.6
        
        # 嘗試使用 LLM 生成結構化內容（即使 OCR 品質較差也嘗試）
        if all_ocr_text.strip():
            # 使用 LLM 生成結構化內容
            try:
                prompt = get_grounded_analysis_prompt()
                user_prompt = f"""{prompt}

<OCR>
{all_ocr_text}
</OCR>

請根據以上 OCR 內容生成結構化筆記。課程名稱：{base_name}
"""
                
                # 調試：記錄發送給 LLM 的內容
                logger.info(f"[DEBUG] 🚀 準備調用 LLM")
                logger.info(f"[DEBUG] 📤 發送給 LLM 的 OCR 內容: {all_ocr_text[:200]}...")
                logger.info(f"[DEBUG] 📤 Prompt 長度: {len(user_prompt)}")
                logger.info(f"[DEBUG] 🎯 使用模型: {llm_config.get('final_model', 'qwen3-vl:4b')}")
                
                prepare_llm_inference("summarize_video:structured-summary")
                response = await call_llm(
                    prompt=user_prompt, 
                    model=llm_config.get('final_model', 'qwen3-vl:4b'),
                    language=language
                )
                
                # 調試：記錄 LLM 響應
                logger.info(f"[DEBUG] 📥 LLM 響應長度: {len(response) if response else 0}")
                logger.info(f"[DEBUG] 📥 LLM 響應類型: {type(response)}")
                logger.info(f"[DEBUG] 📥 LLM 響應前 500 字符: {response[:500] if response else 'None'}")
                
                if response and response.strip():
                    # 嘗試解析 JSON 響應
                    import json
                    logger.info(f"[DEBUG] 🔄 嘗試解析 JSON...")
                    
                    # 清理響應內容，移除可能的 markdown 代碼塊
                    cleaned_response = response.strip()
                    if cleaned_response.startswith('```json'):
                        cleaned_response = cleaned_response[7:]
                    if cleaned_response.endswith('```'):
                        cleaned_response = cleaned_response[:-3]
                    cleaned_response = cleaned_response.strip()
                    
                    try:
                        structured_data = json.loads(cleaned_response)
                        logger.info(f"[DEBUG] ✅ JSON 解析成功!")
                        structured_data.update({
                            "courseName": base_name,
                            "date": time.strftime("%Y/%m/%d"),
                            "sourceVideo": filename,
                            "ocrConfidence": ocr_confidence,
                            "ocrText": all_ocr_text,
                            "quality": ocr_quality,
                            "scene_summaries": scene_summaries  # 添加場景數據
                        })
                    except json.JSONDecodeError as json_err:
                        logger.warning(f"[DEBUG] ❌ JSON 解析失敗: {json_err}")
                        logger.warning(f"[DEBUG] ❌ 原始響應: {response[:500]}")
                        raise Exception(f"JSON 解析失敗: {json_err}")
                else:
                    logger.warning(f"[DEBUG] ⚠️ LLM 返回空響應!")
                    raise Exception("LLM 響應為空")
                    
            except Exception as e:
                logger.warning(f"[summarize] LLM 結構化生成失敗: {e}")
                # 降級到簡單結構
                structured_data = {
                    "courseName": base_name,
                    "date": time.strftime("%Y/%m/%d"),
                    "sourceVideo": filename,
                    "ocrConfidence": ocr_confidence,
                    "ocrText": all_ocr_text,
                    "notes": [{"original": "OCR 內容", "explanation": "請檢查資料品質", "supplements": [], "groundingValid": False}],
                    "terms": [],
                    "code": None,
                    "qa": [],
                    "summary": ["資料品質需要改善"],
                    "tips": ["請上傳更清晰的講義"],
                    "quality": "fair",
                    "message": "資料品質有限，建議上傳更清晰的講義"
                }
        else:
            structured_data = _build_vlm_only_structured_payload(
                base_name=base_name,
                filename=filename,
                scene_summaries=scene_summaries,
                final_note=final_note_with_images,
                language=language,
                manifest=cornell_manifest,
                pipeline_trace=pipeline_trace_payload,
            )


        if cornell_structured_payload:
            structured_data = cornell_structured_payload

        # 從最終筆記擷取第一個程式碼區塊
        code_lang, code_block = None, None
        try:
            import re
            m = re.search(r"```(\w+)?\n([\s\S]*?)```", final_note_with_images)
            if m:
                code_lang = (m.group(1) or 'text').lower()
                code_block = m.group(2)
        except Exception:
            pass

        structured_scene_summaries = [_scene_to_structured(scene) for scene in scene_summaries if scene]
        if cornell_structured_payload is not None:
            cornell_structured_payload["sceneSummaries"] = structured_scene_summaries
            cornell_structured_payload["scene_summaries"] = structured_scene_summaries
        primary_scene_struct = next((scene for scene in structured_scene_summaries if scene.get("image")), None)

        # 如果 structured_data 已經生成，使用它；否則使用降級結構
        if 'structured_data' in locals():
            structured_payload = structured_data
        else:
            # 降級結構（當 LLM 生成失敗時）
            structured_payload = {
                "notes": [],
                "terms": [],
                "code": code_block or "",
                "language": code_lang or "",
                "codeExplain": [],
                "qa": [],
                "sceneSummaries": structured_scene_summaries,
                "tips": [
                    "每日複習關鍵詞，並用自己的例子造句",
                    "把程式碼改寫成另一種寫法以加深理解"
                ]
            }

        if isinstance(structured_payload, dict):
            if structured_scene_summaries:
                structured_payload["sceneSummaries"] = structured_scene_summaries
                structured_payload.setdefault("scene_summaries", structured_scene_summaries)
            else:
                structured_payload.setdefault(
                    "sceneSummaries",
                    structured_payload.get("scene_summaries", []),
                )
            meta_info = structured_payload.setdefault("meta", {})
            meta_info.setdefault("video", base_name)
            meta_info.setdefault("sceneCount", len(structured_scene_summaries))
            if duration_sec is not None:
                meta_info.setdefault("duration_sec", float(duration_sec))
            meta_info.setdefault("language", language)
            meta_info.setdefault("includeJapanese", include_japanese)
            meta_info.setdefault(
                "languageMode",
                note_metadata.get("language_mode")
                or (
                    "ja-only"
                    if str(language).lower().startswith("ja") and not include_japanese
                    else "bilingual" if include_japanese else "target-only"
                ),
            )
            if primary_scene_struct and primary_scene_struct.get("image"):

                meta_info.setdefault("coverImage", primary_scene_struct["image"])
            structured_payload.setdefault("noteStyle", note_metadata.get("note_style", "blueprint"))
            if cornell_manifest:
                structured_payload.setdefault("promptManifest", cornell_manifest)
            if pipeline_trace_payload:
                structured_payload.setdefault("pipelineTrace", pipeline_trace_payload)
            if cornell_bundle:
                structured_payload.setdefault("cornell", cornell_bundle)

        # 直接回傳最終筆記內容、影片基本名稱與結構化 JSON
        timings["total_sec"] = round(time.perf_counter() - overall_start, 2)
        if status_manager:
            status_manager.update(filename, {"timings": timings})
        return final_note_with_images, base_name, structured_payload, note_metadata

    except Exception as e:
        error_msg = f"Summarize 函數發生嚴重錯誤: {e}"
        logger.error(f"[summarize] {error_msg}")
        _trace_write(os.path.basename(filename), f"ERROR: {e}")
        logger.error(f"[summarize] 詳細錯誤跟踪: {traceback.format_exc()}")
        update_status(filename, "錯誤", 100, f"處理失敗: {e}", status_manager, stage="error")
        raise
    finally:
        if temp_dir and os.path.exists(temp_dir):
            logger.info(f"[summarize] 清理臨時目錄: {temp_dir}")
            shutil.rmtree(temp_dir)

async def process_scene(
    filename,
    video_path,
    scene_data,
    temp_dir,
    device,
    with_images,
    config,
    llm_config,
    parse_audio=True,
    skip_ocr=False,
    language="zh-TW",
    include_japanese=True,
    long_mode=False,
    ocr_enabled=True,
):
    """
    處理單一場景：擷取、辨識、生成初步摘要
    """
    import time
    start_time = time.time()
    
    # 如果 Whisper 不可用,自動停用音訊處理
    if parse_audio and not WHISPER_AVAILABLE:
        logger.info("⚠️ Whisper 不可用,自動停用音訊處理")
        parse_audio = False
    
    # 修正解包邏輯，支援 (start, end) 或 (start, end, idx)
    idx = -1 # 確保 idx 始終被賦值
    if len(scene_data) == 3:
        start, end, idx = scene_data
    elif len(scene_data) == 2:
        start, end = scene_data
    else:
        raise ValueError(f"scene_data 格式錯誤: {scene_data}")
    
    logger.info(f"🎬 開始處理場景 {idx}: {start:.1f}s - {end:.1f}s (長度: {end-start:.1f}s)")
    _trace_write(filename, f"scene#{idx} start {start:.1f}-{end:.1f}")
    try:
        # 1. 擷取圖片
        img_start_time = time.time()
        img_path = extract_scene_image(video_path, start, end, temp_dir, idx) if with_images else None
        img_time = time.time() - img_start_time
        logger.info(f"場景 {idx} 圖片擷取完成: {img_path} (耗時: {img_time:.2f}秒)")
        _trace_write(filename, f"scene#{idx} image -> {bool(img_path)}")
        
        # 2. 擷取音訊並進行語音辨識
        asr_text = ""
        if parse_audio:
            asr_start_time = time.time()
            audio_path = extract_audio(video_path, start, end, temp_dir, idx)
            asr_text, _ = speech_to_text(audio_path, config, device, long_mode=long_mode)
            asr_time = time.time() - asr_start_time
            logger.info(f"場景 {idx} ASR 完成，文字長度: {len(asr_text)} (耗時: {asr_time:.2f}秒)")
            _trace_write(filename, f"scene#{idx} asr_len={len(asr_text)}")
            
            # 記錄 ASR 輸出
            with open(os.path.join(temp_dir, f'asr_output_{idx}.log'), 'w', encoding='utf-8') as f:
                f.write(asr_text)
        
        # 啟用 ImageAnalyzer 進行 OCR + 多模態分析
        logger.info(
            "場景 %s 🎯 使用 ImageAnalyzer 進行多模態分析 (OCR=%s)",
            idx,
            "ON" if ocr_enabled and not skip_ocr else "OFF",
        )
            
        # 3. 使用共享的圖片分析器進行多模態分析 (完全比照圖片處理流程)
        scene_summary = ""
        ocr_text = ""  # ✅ 從 ImageAnalyzer 返回的 OCR 文字
        
        if img_path and os.path.exists(img_path):
            try:
                # 導入圖片分析器
                print(f"🔴 [Scene {idx}] 開始導入 ImageAnalyzer")
                logger.warning(f"🔴 [Scene {idx}] 開始導入 ImageAnalyzer")
                from modules.image_analyzer import create_image_analyzer
                
                print(f"🔴 [Scene {idx}] 創建 ImageAnalyzer")
                logger.warning(f"🔴 [Scene {idx}] 創建 ImageAnalyzer")
                # 創建圖片分析器
                analyzer = create_image_analyzer(config, llm_config, device)
                
                print(f"🔴 [Scene {idx}] ImageAnalyzer 創建成功")
                logger.warning(f"🔴 [Scene {idx}] ImageAnalyzer 創建成功")
                
                # 智能過濾不重要信息（語音僅作輔助）
                important_asr_text = filter_important_info(asr_text)
                
                # 準備上下文 (語音摘錄)
                def _excerpt(t):
                    t = (t or '').strip()
                    return t[:400]
                
                context_text = ""
                if important_asr_text and len(important_asr_text) >= 80:
                    context_text = f"語音內容：{_excerpt(important_asr_text)}"
                
                # 使用 ImageAnalyzer 執行 OCR 與多模態摘要
                logger.info(
                    "場景 %s 📸 調用 ImageAnalyzer (skip_ocr=%s)",
                    idx,
                    skip_ocr or not ocr_enabled,
                )
                analysis_result = await analyzer.analyze_image(
                    image_path=img_path,
                    context=context_text,
                    skip_ocr=skip_ocr or not ocr_enabled,
                    language=language,
                    include_japanese=include_japanese
                )
                release_cuda_cache(reason="scene_ocr_complete")

                # 【診斷】記錄完整的 ImageAnalyzer 返回值
                logger.info(f"場景 {idx} 📋 ImageAnalyzer 完整返回: {analysis_result}")

                if analysis_result['success'] and str(analysis_result.get('analysis', '')).strip():
                    scene_summary = analysis_result['analysis']
                    # 【關鍵】從 VLM 分析結果中提取 OCR 文字
                    ocr_text = analysis_result.get('ocr_text', '')
                    logger.info(
                        "場景 %s ✅ VLM 摘要長度=%s 字: %.120s",
                        idx,
                        len(scene_summary or ""),
                        (scene_summary or "").replace("\n", " ")[:120],
                    )
                    
                    # 🔍 診斷: 檢查 analysis_result 完整結構
                    logger.info(f"場景 {idx} 🔍 分析結果鍵: {list(analysis_result.keys())}")
                    logger.info(f"場景 {idx} 🔍 ocr_text 類型: {type(ocr_text)}, 長度: {len(ocr_text) if ocr_text else 0}")
                    
                    # 🔧 如果 OCR 為空但分析成功,嘗試從分析內容中提取
                    if ocr_enabled and (not ocr_text or len(ocr_text.strip()) < 10):
                        logger.warning(f"場景 {idx} ⚠️ ImageAnalyzer 未返回有效 OCR,嘗試降級提取")
                        try:
                            from modules.core.ocr_utils import ocr_manager
                            structured = ocr_manager.extract_with_meta(img_path, config, device)
                            if isinstance(structured, dict):
                                ocr_text = structured.get("text", "")
                            else:
                                ocr_text = str(structured or "")
                            logger.info(f"場景 {idx} ✅ 降級 OCR 提取: {len(ocr_text)} 字元")
                        except Exception as fallback_err:
                            logger.error(f"場景 {idx} ❌ 降級 OCR 失敗: {fallback_err}")
                    
                    logger.info(f"場景 {idx} ✅ 圖片分析完成, 摘要長度: {len(scene_summary)}, OCR 長度: {len(ocr_text)}")
                    logger.info(f"場景 {idx} 📝 OCR 前100字: {ocr_text[:100] if ocr_text else '(無)'}")
                    _trace_write(filename, f"scene#{idx} mm_success len={len(scene_summary)} ocr_len={len(ocr_text)}")
                else:
                    logger.error(f"場景 {idx} ❌ 圖片分析失敗: {analysis_result.get('error', 'Unknown')}")
                    scene_summary = f"**場景摘要**（圖片分析失敗）:\n\n**語音內容**: {important_asr_text}"
                    _trace_write(filename, f"scene#{idx} mm_fail: {analysis_result.get('error')}")
                    
            except Exception as analysis_error:
                logger.error(f"場景 {idx} ❌ 圖片分析器調用失敗: {analysis_error}")
                import traceback
                logger.error(f"場景 {idx} 詳細錯誤:\n{traceback.format_exc()}")
                # 使用備用摘要
                important_asr_text = filter_important_info(asr_text)
                scene_summary = f"**場景摘要**（分析失敗，使用語音內容）:\n\n**語音內容**: {important_asr_text}"
        else:
            # 沒有圖片時，只使用語音內容
            important_asr_text = filter_important_info(asr_text)
            scene_summary = f"**場景摘要**（僅語音）:\n\n**語音內容**: {important_asr_text}"
        # 记录场景摘要结果
        with open(os.path.join(temp_dir, f'scene_summary_{idx}.log'), 'w', encoding='utf-8') as f:
            f.write(f"Scene {idx} Summary:\n{scene_summary}\n\nASR Text:\n{asr_text}")
        
        # 5. 储存图片并取得最终路径 (優化: 壓縮截圖節省空間)
        final_image_path = ""
        if img_path:
            # 🔧 診斷: 記錄圖片路徑和存在狀態
            logger.info(f"場景 {idx} 📸 準備複製圖片:")
            logger.info(f"  - 原始路徑: {img_path}")
            logger.info(f"  - 文件存在: {os.path.exists(img_path) if img_path else False}")
            
            # 创建基于影片名称的子资料夹
            base_name = os.path.splitext(filename)[0]  # filename 在这里是基本档案名
            output_dir = os.path.join(OUTPUT_IMAGES_ROOT, base_name)
            os.makedirs(output_dir, exist_ok=True)
            logger.info(f"  - 輸出目錄: {output_dir}")
            
            # 生成更有意义的图片名称
            img_name = f'scene_{idx:03d}.jpg'
            final_image_path_abs = os.path.join(output_dir, img_name)
            logger.info(f"  - 目標路徑: {final_image_path_abs}")
            
            # 🔧 優化: 壓縮截圖 (1920x1080 → 1280x720, 減少 75% 大小)
            try:
                # 🔧 修復: 檢查原始文件是否存在
                if not os.path.exists(img_path):
                    logger.error(f"場景 {idx} ❌ 原始圖片不存在: {img_path}")
                    raise FileNotFoundError(f"圖片文件不存在: {img_path}")
                
                frame = cv2.imread(img_path)
                if frame is not None:
                    logger.info(f"場景 {idx} ✅ 圖片讀取成功,尺寸: {frame.shape}")
                    # 1. 縮小解析度 (保持寬高比)
                    height, width = frame.shape[:2]
                    if width > 1280:
                        scale = 1280 / width
                        new_width = 1280
                        new_height = int(height * scale)
                        frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
                    
                    # 2. 保存為優化的 JPEG (質量 85, 啟用優化)
                    cv2.imwrite(final_image_path_abs, frame, [
                        cv2.IMWRITE_JPEG_QUALITY, 85,
                        cv2.IMWRITE_JPEG_OPTIMIZE, 1
                    ])
                    
                    # 記錄壓縮效果
                    original_size = os.path.getsize(img_path) / 1024  # KB
                    compressed_size = os.path.getsize(final_image_path_abs) / 1024  # KB
                    reduction = ((original_size - compressed_size) / original_size * 100) if original_size > 0 else 0
                    logger.info(f"場景 {idx} ✅ 截圖壓縮成功: {original_size:.1f}KB → {compressed_size:.1f}KB (減少 {reduction:.1f}%)")
                else:
                    # 壓縮失敗,回退到直接複製
                    logger.warning(f"場景 {idx} ⚠️ cv2.imread 返回 None,嘗試直接複製")
                    shutil.copy(img_path, final_image_path_abs)
                    logger.info(f"場景 {idx} ✅ 直接複製成功: {os.path.getsize(final_image_path_abs)/1024:.1f}KB")
            except Exception as e:
                # 壓縮失敗,回退到直接複製
                logger.error(f"場景 {idx} ❌ 圖片處理失敗: {e}")
                try:
                    if os.path.exists(img_path):
                        shutil.copy(img_path, final_image_path_abs)
                        logger.info(f"場景 {idx} ✅ 降級複製成功: {os.path.getsize(final_image_path_abs)/1024:.1f}KB")
                    else:
                        logger.error(f"場景 {idx} ❌ 無法複製,原始文件不存在: {img_path}")
                        # 🔧 即使複製失敗,也不要留空路徑,設置一個標記
                        final_image_path = ""
                except Exception as copy_err:
                    logger.error(f"場景 {idx} ❌ 降級複製也失敗: {copy_err}")
                    final_image_path = ""
            
            # 🔧 修復: 確認文件確實被保存了
            if os.path.exists(final_image_path_abs):
                # Web 服务可访问的相对路径 - 进行 URL 编码
                from urllib.parse import quote
                encoded_base_name = quote(base_name)
                final_image_path = f'/images/{encoded_base_name}/{img_name}'
                logger.info(f"場景 {idx} ✅ 圖片保存完成: {final_image_path}")
            else:
                logger.error(f"場景 {idx} ❌ 圖片保存失敗,文件不存在: {final_image_path_abs}")
                final_image_path = ""
        else:
            logger.warning(f"場景 {idx} ⚠️ 沒有圖片路徑 (img_path 為空或 None)")
        
        # ⏱️ 計算各階段耗時
        end_time = time.time()
        processing_time = end_time - start_time
        logger.info(f"✅ 場景 {idx} 處理完成")
        logger.info(f"⏱️  總耗時: {processing_time:.2f}秒")
        logger.info(f"📊 詳細統計: 圖片={img_time:.2f}s, ASR={asr_time if parse_audio else 0:.2f}s")
        
        if processing_time > 30:
            logger.warning(f"⚠️ 場景 {idx} 處理較慢 ({processing_time:.2f}秒),建議檢查 VLM 性能")
        
        # 從 OCR 萃取 Top-N 日文原文行，供無 LLM 時的備援輸出
        def _extract_jp_top_lines(text, max_lines=5):
            try:
                import re as _re
                lines = [ln.strip() for ln in (text or '').replace('\r', '\n').split('\n') if ln.strip()]
                jp_pat = _re.compile(r'[\u3040-\u30ff\u3400-\u9fff]')
                candidates = [ln for ln in lines if jp_pat.search(ln)]
                def _score(ln):
                    jp_count = len(_re.findall(r'[\u3040-\u30ff\u3400-\u9fff]', ln))
                    return (jp_count, len(ln))
                # 去重並依分數排序
                seen = set()
                uniq = []
                for ln in candidates:
                    if ln not in seen:
                        seen.add(ln)
                        uniq.append(ln)
                uniq.sort(key=_score, reverse=True)
                return uniq[:max_lines]
            except Exception:
                return []

        jp_top_lines = _extract_jp_top_lines(ocr_text, max_lines=5)
        _trace_write(filename, f"scene#{idx} jp_top_lines={len(jp_top_lines)}")
        
        return {
            'index': idx,
            'start': float(start),
            'end': float(end),
            'duration': float(max(0.0, end - start)),
            'summary': scene_summary.strip(),
            'image_path_final': final_image_path,
            'asr_text': important_asr_text,  # 返回过滤后的文本
            'ocr_text': ocr_text or "",
            'jp_top_lines': jp_top_lines
        }
    except Exception as e:
        # 确保 idx 一定有值
        with open(os.path.join(temp_dir, f'process_scene_error.log'), 'a', encoding='utf-8') as f:
            f.write(f'場景 {idx} 處理失敗: {str(e)}\n')
        log_error(f"Process scene error: {traceback.format_exc()}")
        _trace_write(filename, f"scene#{idx} ERROR: {e}")
        raise

# --- 輔助函數 ---

def detect_scenes(video_path, config):
    try:
        video_manager = VideoManager([video_path])
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=config.get('scene_detect', {}).get('threshold', 30.0)))
        video_manager.set_downscale_factor()
        video_manager.start()
        scene_manager.detect_scenes(frame_source=video_manager)
        scene_list = scene_manager.get_scene_list()
        scenes = [(start.get_seconds(), end.get_seconds(), idx) for idx, (start, end) in enumerate(scene_list)]
        video_manager.release()
        
        if not scenes: # 如果內容偵測失敗，退回固定間隔
            return get_fixed_interval_scenes(video_path)
        return scenes
    except Exception as e:
        log_error(f"Scenedetect 失敗，退回固定間隔模式: {e}")
        return get_fixed_interval_scenes(video_path)

def get_fixed_interval_scenes(video_path, interval=120):  # 改為2分鐘間隔
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = frame_count / fps if fps > 0 else 0
    cap.release()
    
    scenes = []
    t = 0
    idx = 0
    
    # 對於短影片，使用更簡化的處理
    if duration <= 30:  # 30秒以下，使用極簡處理
        scenes.append((0, duration, 0))
        logger.info(f"極短影片處理: 影片長度 {duration:.1f}秒, 使用極簡模式")
        return scenes
    elif duration <= 120:  # 2分鐘以下，整個影片作為一個場景
        scenes.append((0, duration, 0))
        logger.info(f"短影片處理: 影片長度 {duration:.1f}秒, 作為單一場景處理")
        return scenes
    elif duration < 300:  # 5分鐘以下
        interval = 90    # 1.5分鐘間隔
    elif duration < 600:  # 10分鐘以下
        interval = 120   # 2分鐘間隔
    elif duration < 1800:  # 30分鐘以下(教學影片常見長度)
        interval = 120   # 2分鐘間隔,避免漏掉重要內容
    else:  # 30分鐘以上的長影片
        interval = 180   # 3分鐘間隔
    
    while t < duration:
        end_time = min(t + interval, duration)
        scenes.append((t, end_time, idx))
        t += interval
        idx += 1
    
    logger.info(f"固定間隔場景檢測: 影片長度 {duration:.1f}秒, 間隔 {interval}秒, 生成 {len(scenes)} 個場景")
    return scenes

def _deduplicate_scene_texts(scene_summaries, sim_threshold=0.95):
    """基於簡單相似度的文字去重。
    - 優先比較 asr_text,其次比較 summary。
    - 保留較早且含資訊較多者。
    - 🔧 修復: 閾值從0.80提高到0.95,避免不同場景被誤判為重複(如「高可用性」vs「Scalability」vs「Elasticity」)
    """
    try:
        from difflib import SequenceMatcher
    except Exception:
        # 無法導入則不去重
        return scene_summaries

    def _norm(s: str) -> str:
        s = (s or '').strip().lower()
        # 移除多餘空白
        import re
        s = re.sub(r"\s+", " ", s)
        return s

    filtered = []
    for cur in scene_summaries:
        cur_asr = _norm(cur.get('asr_text', ''))
        cur_sum = _norm(cur.get('summary', ''))
        cur_ocr = _norm(cur.get('ocr_text', ''))  # 🔧 新增OCR比較
        is_dup = False
        for kept in filtered:
            kept_asr = _norm(kept.get('asr_text', ''))
            kept_sum = _norm(kept.get('summary', ''))
            kept_ocr = _norm(kept.get('ocr_text', ''))  # 🔧 新增OCR比較
            
            # 計算相似度分數
            score_asr = SequenceMatcher(None, cur_asr, kept_asr).ratio() if (cur_asr and kept_asr) else 0.0
            score_sum = SequenceMatcher(None, cur_sum, kept_sum).ratio() if (cur_sum and kept_sum) else 0.0
            score_ocr = SequenceMatcher(None, cur_ocr, kept_ocr).ratio() if (cur_ocr and kept_ocr) else 0.0
            
            # 🔧 優先使用OCR文字判斷(因為課程講義OCR最能代表內容)
            max_score = max(score_ocr, score_asr, score_sum)
            
            if max_score >= sim_threshold:
                # 判定為重複：保留資訊量較多者
                len_cur = len(cur_ocr) + len(cur_asr) + len(cur_sum)
                len_kept = len(kept_ocr) + len(kept_asr) + len(kept_sum)
                if len_cur > len_kept:
                    kept.update(cur)
                is_dup = True
                logger.info(f"[_deduplicate] 發現重複場景 (相似度: {max_score:.2f})")
                break
        if not is_dup:
            filtered.append(cur)
    
    logger.info(f"[_deduplicate] 去重: {len(scene_summaries)} → {len(filtered)} 個場景")
    return filtered


def _compute_scene_weight(scene: dict) -> float:
    """Estimate scene importance using heuristic signals."""

    def _length_score(text: str, scale: int, cap: float) -> float:
        length = len((text or "").strip())
        if length <= 0:
            return 0.0
        return min(length / scale, cap)

    asr_score = _length_score(scene.get('asr_text', ''), 80, 4.0)
    ocr_score = _length_score(scene.get('ocr_text', ''), 120, 3.0)
    summary_score = _length_score(scene.get('summary', ''), 80, 3.0)

    duration = scene.get('duration')
    if duration is None:
        start = scene.get('start')
        end = scene.get('end')
        duration = (end - start) if (start is not None and end is not None) else 0
    duration_score = 0.0
    if duration and duration > 0:
        duration_score = min(duration / 90.0, 2.0)

    jp_bonus = min(len(scene.get('jp_top_lines') or []) * 0.3, 1.0)
    image_bonus = 1.0 if scene.get('image_path_final') else 0.0

    total = asr_score + ocr_score + summary_score + duration_score + jp_bonus + image_bonus
    return round(total, 2)


def _annotate_scene_weights(scene_summaries):
    for scene in scene_summaries or []:
        scene['scene_weight'] = _compute_scene_weight(scene)
    return scene_summaries


def _has_substantial_content(scene: dict) -> bool:
    thresholds = (
        ('asr_text', 120),
        ('ocr_text', 80),
        ('summary', 80),
    )
    for field, threshold in thresholds:
        if len((scene.get(field) or "").strip()) >= threshold:
            return True
    return False


def _filter_low_value_scenes(scene_summaries):
    if not scene_summaries or len(scene_summaries) <= 5:
        return scene_summaries

    weights = [scene.get('scene_weight', 0.0) for scene in scene_summaries]
    try:
        median_weight = statistics.median(weights)
    except statistics.StatisticsError:
        median_weight = weights[0] if weights else 0.0

    # Keep all scenes for complete lecture notes
    threshold = 0.0
    baseline_keep = len(scene_summaries)

    filtered = [
        scene
        for scene in scene_summaries
        if scene.get('scene_weight', 0.0) >= threshold or _has_substantial_content(scene)
    ]

    if len(filtered) < baseline_keep:
        sorted_by_weight = sorted(
            scene_summaries, key=lambda sc: sc.get('scene_weight', 0.0), reverse=True
        )
        filtered = sorted_by_weight[:baseline_keep]

    seen_indices = set()
    ordered_filtered = []
    for scene in filtered:
        idx = scene.get('index')
        if idx in seen_indices:
            continue
        seen_indices.add(idx)
        ordered_filtered.append(scene)

    ordered_filtered.sort(key=lambda sc: sc.get('index', 0))
    return ordered_filtered

def extract_scene_image(video_path, start, end, temp_dir, idx):
    def _ffmpeg_capture(ts):
        try:
            target = os.path.join(temp_dir, f"scene_{idx:03d}_ff.jpg")
            cmd = [
                _FFMPEG_BIN,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                str(max(ts, 0.0)),
                "-i",
                video_path,
                "-frames:v",
                "1",
                "-q:v",
                "2",
                target,
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            if os.path.exists(target):
                return target
        except Exception as exc:
            logger.warning("[extract_scene_image] ffmpeg capture failed: %s", exc)
        return None

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.warning("[extract_scene_image] VideoCapture failed: %s", video_path)
        return _ffmpeg_capture((start + end) / 2)
    try:
        # 從場景中取 5 幀（首/25%/中/75%/尾），選擇拉普拉斯方差最大的幀（最清晰）
        times = [start, start + (end - start) * 0.25, (start + end) / 2, start + (end - start) * 0.75, end - 0.01]
        best = (None, -1.0)
        for i, t in enumerate(times):
            if t < start: t = start
            if t > end: t = end
            cap.set(cv2.CAP_PROP_POS_MSEC, max(t, 0) * 1000)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            if score > best[1]:
                best = (frame, score)
        if best[0] is not None:
            img_path = os.path.join(temp_dir, f'scene_{idx:03d}.jpg')
            cv2.imwrite(img_path, best[0])
            return img_path
        return _ffmpeg_capture((start + end) / 2)
    finally:
        cap.release()

def extract_audio(video_path, start, end, temp_dir, idx):
    audio_path = os.path.join(temp_dir, f'scene_{idx}.wav')
    duration = max(0.01, float(end) - float(start))
    cmd = [
        _FFMPEG_BIN, "-hide_banner", "-loglevel", "error", "-y",
        "-ss", str(start), "-t", str(duration),
        "-i", video_path,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        audio_path
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        log_error(f"FFmpeg 音訊提取失敗: {e.stderr.decode()}")
        return None
    return audio_path if os.path.exists(audio_path) else None


def _enhance_audio_for_asr(audio_path, config):
    """Apply lightweight ffmpeg denoise/normalization pipeline for ASR robustness.

    Returns an enhanced audio path on success; otherwise returns original audio_path.
    """
    if not audio_path or not os.path.exists(audio_path):
        return audio_path

    whisper_cfg = (config or {}).get("whisper", {}) if isinstance(config, dict) else {}
    enhancement_cfg = whisper_cfg.get("audio_enhancement", {}) if isinstance(whisper_cfg, dict) else {}
    enabled = enhancement_cfg.get("enabled", True)
    if not enabled:
        return audio_path

    highpass_hz = int(enhancement_cfg.get("highpass_hz", 80) or 80)
    lowpass_hz = int(enhancement_cfg.get("lowpass_hz", 7600) or 7600)
    use_denoise = bool(enhancement_cfg.get("denoise", True))
    use_loudnorm = bool(enhancement_cfg.get("loudnorm", True))
    use_silence_trim = bool(enhancement_cfg.get("silence_trim", True))

    filters = [f"highpass=f={max(20, highpass_hz)}", f"lowpass=f={max(highpass_hz + 200, lowpass_hz)}"]
    if use_denoise:
        filters.append("afftdn=nf=-20")
    if use_loudnorm:
        filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    if use_silence_trim:
        filters.append("silenceremove=start_periods=1:start_duration=0.15:start_threshold=-40dB")

    enhanced_path = os.path.splitext(audio_path)[0] + "_enhanced.wav"
    cmd = [
        _FFMPEG_BIN,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        audio_path,
        "-af",
        ",".join(filters),
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        enhanced_path,
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        if os.path.exists(enhanced_path) and os.path.getsize(enhanced_path) > 0:
            logger.info("[ASR] audio enhancement applied: %s", enhanced_path)
            return enhanced_path
    except Exception as exc:
        logger.warning("[ASR] audio enhancement failed, fallback to original audio: %s", exc)
    return audio_path

def speech_to_text(audio_path, config, device="gpu", long_mode=False):
    """語音轉文字。若 Whisper 不可用則返回空字串。"""
    # Whisper 不可用時直接返回
    if not WHISPER_AVAILABLE:
        return "", 0.0
    
    if not audio_path:
        return "", 0.0
    
    try:
        whisper_config = config.get('whisper', {})

        # Optional audio enhancement (denoise/normalization) before transcription
        prepared_audio_path = _enhance_audio_for_asr(audio_path, config)

        # Use cached model. Long videos prefer smaller/faster models.
        try:
            model = _get_whisper_model(config, prefer_fast=long_mode, force_cpu=False)
        except Exception:
            model = _get_whisper_model(config, prefer_fast=True, force_cpu=True)

        # 如果模型獲取失敗(返回 None),跳過音訊處理
        if model is None:
            logger.info("ℹ️ Whisper 模型不可用,跳過音訊轉錄")
            return "", 0.0

        segments, _ = model.transcribe(
            prepared_audio_path,
            language=whisper_config.get('language', 'ja'),
            vad_filter=bool(whisper_config.get('vad_filter', True if long_mode else False))
        )
        return " ".join([s.text for s in segments]), 1.0
    except Exception as e:
        log_error(f"Whisper 辨識失敗: {e}")
        return "", 0.0

def smart_crop_meet_viewport(img_path):
    """智能裁切 Google Meet 視窗，移除工具列和邊框"""
    try:
        import cv2
        img = cv2.imread(img_path)
        if img is None:
            return img_path
            
        h, w = img.shape[:2]
        # 裁切掉上下工具列和左右邊框（保留更多內容區域）
        x = int(w * 0.05)  # 減少左邊裁切
        y = int(h * 0.08)  # 減少上邊裁切
        cw = int(w * 0.90) # 增加寬度保留
        ch = int(h * 0.84) # 增加高度保留
        
        cropped = img[y:y+ch, x:x+cw]
        
        # 保存裁切後的圖片
        cropped_path = img_path.replace('.jpg', '_cropped.jpg').replace('.png', '_cropped.png')
        cv2.imwrite(cropped_path, cropped)
        return cropped_path
    except Exception as e:
        logger.warning(f"智能裁切失敗: {e}")
        return img_path

def denoise_and_desaturate(img_path):
    """去色塊、灰階化、增強邊緣"""
    try:
        import cv2
        img = cv2.imread(img_path)
        if img is None:
            return img_path
            
        # 轉灰階
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 中值濾波去噪
        denoised = cv2.medianBlur(gray, 3)
        
        # 自適應閾值增強對比（多種方法嘗試）
        enhanced = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
        )
        
        # 額外增強：形態學操作
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        enhanced = cv2.morphologyEx(enhanced, cv2.MORPH_CLOSE, kernel)
        
        # 保存處理後的圖片
        processed_path = img_path.replace('.jpg', '_processed.jpg').replace('.png', '_processed.png')
        cv2.imwrite(processed_path, enhanced)
        return processed_path
    except Exception as e:
        logger.warning(f"圖片預處理失敗: {e}")
        return img_path

def post_clean_ocr_text(text):
    """強化版OCR文本清理 - 徹底移除噪音與錯誤"""
    if not text:
        return ""
    
    import re
    
    # 黑名單詞：系統UI噪音徹底清理
    blacklist_patterns = [
        r'youtu(?:be|ee)?',
        r'goo(?:g|ge)?[le]?',
        r'phone(?:wndohs)?',
        r'wi(?:ndows?|ndohs)',
        r'ocah(?:os)?\+?\d+',
        r'chalbod',
        r'te\s*youtu?ee',
        r'(?:subscribe|訂閱)',
        r'(?:1080p?|hd|full.*screen)',
        r'meet\.google\.com',
        r'classroom\.google\.com',
        r'PhoneWndohs',
        r'3Utロシ中文',
        r'GOOGe食号',
        r'OcahOs\+5173',
        r'TE YOUTUEE',
        r'自動立記生成手町'
    ]
    
    # 移除黑名單內容
    for pattern in blacklist_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # 移除 URL
    text = re.sub(r'https?://\S+', '', text)
    # 移除時間戳
    text = re.sub(r'\b\d{1,2}:\d{2}(?::\d{2})?\b', '', text)
    # 移除日期
    text = re.sub(r'\b\d{1,2}/\d{1,2}/\d{4}\b', '', text)
    
    # 清理亂碼和無效字符
    # 移除非中日英文字符
    text = re.sub(r'[^\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\u3000-\u303f\u0020-\u007f\u2000-\u206f]', '', text)
    
    # 修正常見OCR錯誤
    text = re.sub(r'[Ss]せing', 'String', text)
    text = re.sub(r'[Ss]山1昭日山11', 'StringBuilder', text)
    text = re.sub(r'[Ss]山1', 'String', text)
    text = re.sub(r'[Bb]山1', 'Boolean', text)
    text = re.sub(r'[Nn]山1', 'Number', text)
    text = re.sub(r'[Oo]山1', 'Object', text)
    text = re.sub(r'尊換', '轉換', text)
    text = re.sub(r'比封', '比對', text)
    text = re.sub(r'勤象', '對象', text)
    text = re.sub(r'鹿用', '應用', text)
    text = re.sub(r'區別', '區別', text)
    text = re.sub(r'他門', '它們', text)
    text = re.sub(r'程式鶴', '程式碼', text)
    text = re.sub(r'字行串', '字符串', text)
    text = re.sub(r'字符史', '字符串', text)
    text = re.sub(r'輔換', '轉換', text)
    text = re.sub(r'方注', '方法', text)
    text = re.sub(r'高比', '比較', text)
    text = re.sub(r'数字符史', '字符串', text)
    text = re.sub(r'одual0', 'equals', text)
    text = re.sub(r'追個', '這個', text)
    text = re.sub(r'用放', '用於', text)
    text = re.sub(r'sł1', 'String', text)
    text = re.sub(r'b001ean', 'boolean', text)
    text = re.sub(r'Bildingbxt', 'Builder', text)
    
    # 新增更多OCR錯誤修正
    text = re.sub(r'PhoneWndohs', '', text)
    text = re.sub(r'3Utロシ中文', '', text)
    text = re.sub(r'GOOGe食号', '', text)
    text = re.sub(r'OcahOs\+5173', '', text)
    text = re.sub(r'Chalbod', '', text)
    text = re.sub(r'TE YOUTUEE', '', text)
    text = re.sub(r'自動立記生成手町', '', text)
    
    # 加強的程式碼相關錯誤修正
    text = re.sub(r'S山1昭日山11勤象', 'StringBuilder對象', text)
    text = re.sub(r'String.*ing', 'String', text)
    text = re.sub(r'等於.*比較', 'equals比較', text)
    text = re.sub(r'兩.*物件', '兩個物件', text)
    text = re.sub(r'高.*相等', '比較相等', text)
    text = re.sub(r'回.*是', '返回的是', text)
    text = re.sub(r'值.*b001ean', '值是boolean', text)
    text = re.sub(r'StringBuilder.*equals.*StringBuilder', 'StringBuilder.equals(StringBuilder)', text)
    text = re.sub(r'比.*5.*ユ.*1.*d.*異号', '比較StringBuilder對象與', text)
    text = re.sub(r'字串.*類', '字串類型', text)
    text = re.sub(r'型轉換後.*相等', '型別轉換後是否相等', text)
    text = re.sub(r'異号', '與', text)
    text = re.sub(r'型尊換', '型轉換', text)
    text = re.sub(r'Sngea50', 'String', text)
    text = re.sub(r'StringBuildereguals', 'StringBuilder.equals', text)
    text = re.sub(r'止方法', '此方法', text)
    text = re.sub(r'追個', '這個', text)
    text = re.sub(r'用放', '用於', text)
    text = re.sub(r'Bildingbxけ', 'Builder', text)
    text = re.sub(r'5+ユ川B山11d', 'StringBuilder', text)
    text = re.sub(r'異号', '與', text)
    text = re.sub(r'型尊換', '型轉換', text)
    text = re.sub(r'Sngea50', 'String', text)
    text = re.sub(r'StringBuildereguals', 'StringBuilder.equals', text)
    text = re.sub(r'止方法', '此方法', text)
    text = re.sub(r'5十ユ川B山11d', 'StringBuilder', text)
    
    # 清理多餘空白和換行
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    
    # 保留日文和程式碼相關內容
    # 移除純英文的系統詞，但保留日文
    text = re.sub(r'\b(提出|ファイル|アノテーション|畫面を共有)\b', '', text)
    
    return text.strip()

def image_to_text(img_path, device="gpu", config=None):
    if not img_path: return ""
    
    try:
        # 1. 智能裁切 Meet 視窗
        cropped_path = smart_crop_meet_viewport(img_path)
        
        # 2. 圖片預處理（去色塊、增強對比）
        processed_path = denoise_and_desaturate(cropped_path)
        
        ocr_config = config.get('ocr', {}) if config else {}
        if not ocr_config.get("enabled", True):
            logger.info("[image_to_text] OCR 已關閉，跳過提取")
            return ""
        prefer_gpu = ocr_config.get('use_gpu', True) and device == "gpu"
        min_confidence = float(ocr_config.get('min_confidence', 0.35))

        from modules.core.ocr_utils import ocr_manager

        def _extract_with_device(device_mode: str):
            return ocr_manager.extract_with_meta(processed_path, config or {}, device_mode)

        structured = None
        try:
            structured = _extract_with_device("gpu" if prefer_gpu else "cpu")
        except Exception as primary_error:
            logger.warning(f"OCR ({'GPU' if prefer_gpu else 'CPU'}) 初始化失敗，改用 CPU：{primary_error}")

        if (not structured or not isinstance(structured, dict)) and prefer_gpu:
            try:
                structured = _extract_with_device("cpu")
            except Exception as cpu_error:
                logger.error(f"OCR CPU 初始化失敗: {cpu_error}")
                structured = None

        if not structured or not isinstance(structured, dict):
            logger.warning("OCR 未返回結構化結果")
            return ""

        text_blocks = []
        seen_lines = set()
        seen_normalized = set()
        low_confidence_count = 0
        duplicate_count = 0
        lines = structured.get("lines") or []

        for payload in lines:
            if not isinstance(payload, dict):
                continue
            text = (payload.get("text") or "").strip()
            confidence = float(payload.get("confidence", 0.0))
            if not text:
                continue
            if confidence < min_confidence:
                low_confidence_count += 1
                continue

            normalized = " ".join(text.split()).lower()
            if text in seen_lines or normalized in seen_normalized:
                duplicate_count += 1
                if duplicate_count <= 5:
                    logger.info(f"[OCR] 🔄 檢測到重複行(#{duplicate_count}),已跳過: {text[:50]}...")
                continue

            seen_lines.add(text)
            seen_normalized.add(normalized)
            text_blocks.append(text)

        ocr_text = "\n".join(text_blocks).strip()

        if not ocr_text:
            fallback_text = structured.get("text") or ""
            if fallback_text.strip():
                logger.info("[OCR] 主要行文本為空，回退使用整體文字")
                ocr_text = fallback_text.strip()

        if not ocr_text:
            logger.warning("OCR 未擷取到有效文字")
            return ""

        MAX_OCR_LENGTH = 1500
        if len(ocr_text) > MAX_OCR_LENGTH:
            original_length = len(ocr_text)
            truncated = ocr_text[:MAX_OCR_LENGTH]
            last_newline = truncated.rfind('\n')
            if last_newline > MAX_OCR_LENGTH * 0.8:
                truncated = truncated[:last_newline]
            ocr_text = (
                truncated
                + f"\n\n...(原文共{original_length}字,為避免超出處理限制,已截取前{len(truncated)}字)"
            )
            logger.warning(f"[OCR] ⚠️ 文字過長({original_length}字),已截斷至{len(truncated)}字")

        if duplicate_count > 0:
            logger.info(f"[ImageAnalyzer] 🔄 OCR 去重: 移除了 {duplicate_count} 行重複文字")
        if low_confidence_count > len(text_blocks):
            logger.warning(
                f"[ImageAnalyzer] ⚠️ OCR 低信心度文字過多({low_confidence_count}/{max(len(lines),1)}),圖片品質可能不佳"
            )
        else:
            logger.info(
                f"[ImageAnalyzer] ✅ OCR 識別成功,共 {len(text_blocks)} 行文字 (原始: {len(lines)} 行)"
            )

        return ocr_text

    except Exception as e:
        logger.error(f"OCR 處理失敗: {e}")
        return ""

def _tesseract_fallback(img_path: str, lang: str = 'jpn') -> str:
    """使用 Tesseract CLI 作為 OCR 回退，避免 Python 套件依賴問題。"""
    import subprocess
    try:
        # --psm 6 適合單欄塊文字；可視需求調整
        cmd = [
            'tesseract', img_path, 'stdout',
            '-l', lang,
            '--psm', '6',
            '--oem', '1'
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=60)
        text = out.decode('utf-8', errors='ignore')
        return text.strip()
    except Exception as e:
        raise RuntimeError(f"Tesseract CLI 失敗: {e}")

def update_status(filename, status, progress, detail, status_manager: StatusManager, **kwargs):
    """更新處理狀態"""
    current_time = time.time()
    task_snapshot = status_manager.ensure(filename)
    start_time = task_snapshot.get('start_time', current_time)
    elapsed_time = current_time - start_time

    estimated_remaining = None
    if 0 < progress < 100:
        estimated_total = elapsed_time * (100 / progress)
        estimated_remaining = max(0.0, estimated_total - elapsed_time)

    payload = {
        "status": status,
        "progress": progress,
        "detail": detail,
        "timestamp": current_time,
        "start_time": start_time,
        "elapsed_time": elapsed_time,
        "estimated_remaining": estimated_remaining,
    }

    normalized_status = str(status).lower()
    if any(keyword in normalized_status for keyword in ("錯誤", "失敗", "error", "fail")):
        if "error_code" not in kwargs:
            payload["error_code"] = "VIDEO_PIPELINE_FAILURE"
        if "recommended_action" not in kwargs:
            payload["recommended_action"] = "請檢查 logs/notegen.log 取得詳細錯誤資訊。"
    elif any(keyword in normalized_status for keyword in ("警告", "warning")):
        payload.setdefault("recommended_action", "請檢查輸出內容，必要時重新執行該場景。")

    payload.update(kwargs)
    status_manager.update(filename, payload)
    logger.info(f'[{filename}] {status} ({progress}%) - {detail}')

def log_error(message):
    """記錄錯誤日誌"""
    logger.error(message, exc_info=True)

def get_multimodal_scene_prompt(asr_text):
    """
    獲取純多模態的場景分析提示詞 - 針對日文程式設計課程優化
    """
    return f"""你是一位專業的日文程式設計教師和技術分析專家。請對這個影片場景進行深度分析，結合語音內容生成詳細的場景摘要。

**語音內容：** {asr_text}

**輸出格式規則（強制，否則視為嚴重錯誤）：**
1. 只輸出 Markdown（可含少量 HTML，例如 `<table>`），不要加「以下是…」等前綴或結語。
2. 標題格式：`###` 後面必須有空格，且標題後要空一行再開始正文。
3. 數學公式：
   - 行內用 `$...$`，獨立公式用 `$$...$$`。
   - 絕對禁止把公式放在反引號（`...`）或程式碼區塊（```...```）內。
4. 程式碼：
   - 多行程式碼一律使用 fenced code block（例如 ```java），保留換行/縮排，並確保有對應的 ``` 結尾。
   - 嚴禁把多行程式碼壓成單行「文字牆」，也不要把整段正文放進代碼框。
5. 表格：請用可解析的 Markdown 表格或 HTML `<table>`；不要輸出殘缺的 `|---|---|` 片段。
6. 忽略 OCR 雜訊（頁碼、行號、邊角連號，例如 `274 275 276`），不要輸出這類純數字行。

**深度分析要求：**
1. **視覺內容全面解析**：仔細觀察截圖中的每個細節，包括程式碼、文字、圖表、界面元素、按鈕、選單等
2. **程式碼逐行分析**：如果有程式碼，請逐行解釋其功能和作用
3. **技術概念深入講解**：不僅說明是什麼，還要解釋為什麼這樣做，以及背後的原理
4. **操作步驟詳細記錄**：如果是操作演示，請記錄每個步驟的具體動作和目的
5. **日文內容完整翻譯**：提供準確的翻譯和詳細的語言學習價值
6. **關聯知識擴展**：連結相關的程式設計概念和最佳實踐

**詳細輸出格式：**
### 📋 場景深度分析

**🎯 教學核心重點：** 
[詳細說明這個場景的主要教學目標，包括要學習的概念、技能或知識點]

**💻 技術內容詳解：** 
[對截圖中的技術內容進行逐項分析：]
- **程式碼分析**：[如有程式碼，請逐行或逐段解釋]
- **界面元素**：[說明各個界面元素的作用和意義]
- **操作流程**：[如果是操作演示，詳細記錄每個步驟]
- **技術原理**：[解釋背後的技術原理和設計思路]

**🇯🇵 日文學習寶庫：** 
[針對語音或截圖中的每個日文技術詞彙，提供完整學習資料：]
- **原文**：[日文原文（包括漢字和假名）]
- **標準讀音**：[完整的假名讀音，包括音調]
- **精確翻譯**：[準確的繁體中文翻譯]
- **技術語境**：[在程式設計領域的專業含義]
- **實用例句**：[提供實際使用的例句]
- **相關詞彙**：[列出相關的技術詞彙]
- **記憶技巧**：[提供記憶這個詞彙的方法]

**🔍 重點概念深度解析：**
[針對截圖中的重點內容（特別是標記或強調的部分），提供深入分析：]
- **概念解釋**：[詳細解釋這個概念是什麼]
- **應用場景**：[說明在什麼情況下會使用]
- **優缺點分析**：[分析這種方法的優點和限制]
- **最佳實踐**：[提供相關的最佳實踐建議]
- **常見錯誤**：[指出學習者容易犯的錯誤]

**🔗 知識關聯網絡：**
[將當前內容與其他相關知識點連結：]
- **前置知識**：[需要先掌握哪些概念]
- **後續學習**：[學會這個後可以學習什麼]
- **實際應用**：[在實際項目中如何應用]
- **進階話題**：[相關的進階主題]

**💡 學習建議與實踐：**
[提供具體的學習建議：]
- **練習建議**：[建議的練習方法]
- **參考資源**：[推薦的學習資源]
- **實作項目**：[可以嘗試的小項目]

請用繁體中文回答，內容要極其詳細、準確且具有教育價值。每個技術點都要深入解釋，每個日文詞彙都要提供完整的學習資料。目標是讓學習者不僅理解當前內容，還能建立完整的知識體系。"""

def log_info(message):
    """記錄一般日誌"""
    logger.info(message)

def process_image_paths(final_note, structured_summaries, base_name):
    """
    處理最終筆記中的圖片路徑，將模板中的佔位符替換為實際的圖片路徑
    """
    import re
    import shutil
    
    try:
        logger.info(f"[process_image_paths] 開始處理 {base_name}")
        logger.debug(f"[process_image_paths] structured_summaries 數量: {len(structured_summaries)}")
        
        # 收集所有圖片路徑並複製到輸出目錄
        all_image_paths = []
        output_image_dir = os.path.join(OUTPUT_ROOT, 'images', base_name)
        os.makedirs(output_image_dir, exist_ok=True)
        
        for i, group in enumerate(structured_summaries):
            logger.debug(f"[process_image_paths] 處理組 {i}: {group.keys()}")
            image_paths = group.get('image_paths', [])
            logger.debug(f"[process_image_paths] 組 {i} 的圖片路徑: {image_paths}")
            
            for img_path in image_paths:
                if img_path:
                    logger.debug(f"[process_image_paths] 處理圖片路徑: {img_path}")
                    # 檢查是否是相對路徑（以 /images/ 開頭）
                    if img_path.startswith('/images/'):
                        # 轉換為絕對路徑進行檢查，需要URL解碼
                        from urllib.parse import unquote
                        decoded_path = unquote(img_path)
                        abs_img_path = os.path.join(OUTPUT_ROOT, decoded_path.lstrip('/'))
                        logger.debug(f"[process_image_paths] 檢查絕對路徑: {abs_img_path}")
                        if os.path.exists(abs_img_path):
                            all_image_paths.append(img_path)
                            logger.debug(f"[process_image_paths] 找到圖片: {img_path}")
                        else:
                            logger.warning(f"[process_image_paths] 圖片不存在: {abs_img_path}")
                    elif os.path.exists(img_path):
                        # 生成新的圖片檔名
                        img_filename = f"scene_{len(all_image_paths)+1}.jpg"
                        new_img_path = os.path.join(output_image_dir, img_filename)
                        
                        # 複製圖片到輸出目錄
                        shutil.copy2(img_path, new_img_path)
                        
                        # 生成相對路徑用於 Markdown
                        relative_path = f"/images/{base_name}/{img_filename}"
                        all_image_paths.append(relative_path)
                        logger.debug(f"[process_image_paths] 複製圖片: {img_path} -> {relative_path}")
                    else:
                        logger.warning(f"[process_image_paths] 圖片路徑不存在: {img_path}")
        
        # 如果沒有圖片，但筆記中沒有圖片佔位符，直接添加現有圖片
        if not all_image_paths:
            logger.debug(f"[process_image_paths] 沒有從structured_summaries找到圖片，檢查輸出目錄")
            # 檢查輸出目錄是否有圖片
            if os.path.exists(output_image_dir):
                existing_images = [f for f in os.listdir(output_image_dir) if f.endswith(('.jpg', '.png', '.jpeg'))]
                logger.debug(f"[process_image_paths] 輸出目錄現有圖片: {existing_images}")
                for img_file in existing_images:
                    relative_path = f"/images/{base_name}/{img_file}"
                    all_image_paths.append(relative_path)
                    logger.debug(f"[process_image_paths] 添加現有圖片: {relative_path}")
        
        # 如果還是沒有圖片，返回移除圖片佔位符的筆記
        if not all_image_paths:
            logger.warning(f"[process_image_paths] 沒有找到任何圖片用於 {base_name}")
            # 移除所有圖片佔位符，避免顯示損壞的圖片連結
            processed_note = re.sub(r'!\[([^\]]*)\]\([^)]*\)', '<!-- 圖片不可用 -->', final_note)
            processed_note = re.sub(r'\{\{image_placeholder\}\}', '<!-- 圖片不可用 -->', processed_note)
            return processed_note
        
        logger.info(f"[process_image_paths] 找到 {len(all_image_paths)} 張圖片用於 {base_name}")
        
        # 替換模板中的圖片佔位符
        processed_note = final_note
        used_images = set()
        
        # 方法1: 替換 {{image_placeholder}} 佔位符
        placeholder_count = processed_note.count('{{image_placeholder}}')
        if placeholder_count > 0:
            logger.debug(f"[process_image_paths] 找到 {placeholder_count} 個 {{image_placeholder}} 佔位符")
            for i in range(min(placeholder_count, len(all_image_paths))):
                processed_note = processed_note.replace('{{image_placeholder}}', f'![課程截圖]({all_image_paths[i]})', 1)
                used_images.add(i)
                logger.debug(f"[process_image_paths] 替換 {{image_placeholder}} -> ![課程截圖]({all_image_paths[i]})")
        
        # 方法2: 替換 "實際圖片路徑" 佔位符
        placeholder_pattern = r'!\[([^\]]*)\]\(實際圖片路徑\)'
        matches = re.findall(placeholder_pattern, processed_note)
        
        if matches and all_image_paths:
            logger.debug(f"[process_image_paths] 找到 {len(matches)} 個圖片佔位符")
            for i, alt_text in enumerate(matches):
                if i < len(all_image_paths):
                    img_index = i % len(all_image_paths)
                    while img_index in used_images and len(used_images) < len(all_image_paths):
                        img_index = (img_index + 1) % len(all_image_paths)
                    
                    used_images.add(img_index)
                    old_pattern = f'![{alt_text}](實際圖片路徑)'
                    new_pattern = f'![{alt_text}]({all_image_paths[img_index]})'
                    processed_note = processed_note.replace(old_pattern, new_pattern, 1)
                    logger.debug(f"[process_image_paths] 替換圖片佔位符: {old_pattern} -> {new_pattern}")
        
        # 方法3: 如果筆記中沒有任何圖片標記，在開頭添加圖片
        if not re.search(r'!\[.*?\]\(.*?\)', processed_note) and all_image_paths:
            logger.debug("[process_image_paths] 筆記中沒有圖片標記，在開頭添加圖片")
            # 在第一個## 標題後立即添加圖片
            if '## ' in processed_note:
                first_h2_pos = processed_note.find('## ')
                next_line_pos = processed_note.find('\n', first_h2_pos)
                if next_line_pos != -1:
                    insert_pos = next_line_pos + 1
                    img_markdown = f"\n![課程截圖]({all_image_paths[0]})\n\n"
                    processed_note = processed_note[:insert_pos] + img_markdown + processed_note[insert_pos:]
                    used_images.add(0)
                    logger.debug(f"[process_image_paths] 在課程主題後添加圖片: {all_image_paths[0]}")
            else:
                # 如果沒有## 標題，就在開頭添加
                img_markdown = f"![課程截圖]({all_image_paths[0]})\n\n"
                processed_note = img_markdown + processed_note
                used_images.add(0)
                logger.debug(f"[process_image_paths] 在筆記開頭添加圖片: {all_image_paths[0]}")
        
        # 方法4: 在筆記末尾添加剩餘的圖片（只有在沒有其他圖片插入時才執行）
        unused_images = [all_image_paths[i] for i in range(len(all_image_paths)) if i not in used_images]
        if unused_images and not re.search(r'!\[.*?\]\(.*?\)', processed_note):
            logger.debug(f"[process_image_paths] 在筆記末尾添加 {len(unused_images)} 張未使用的圖片")
            processed_note += "\n\n### 📷 課程截圖\n\n"
            for i, img_path in enumerate(unused_images, 1):
                processed_note += f"![課程截圖 {i}]({img_path})\n\n"
        elif unused_images:
            logger.debug(f"[process_image_paths] 跳過末尾圖片添加，因為筆記中已有 {len(used_images)} 張圖片")
        
        logger.info(f"[process_image_paths] 圖片路徑處理完成，使用了 {len(used_images)} 張圖片")
        return processed_note
        
    except Exception as e:
        logger.error(f"[process_image_paths] 處理圖片路徑時發生錯誤: {e}")
        logger.error(f"[process_image_paths] 詳細錯誤跟踪: {traceback.format_exc()}")
        # 返回原始筆記，移除圖片佔位符
        processed_note = re.sub(r'!\[([^\]]*)\]\([^)]*\)', '<!-- 圖片處理失敗 -->', final_note)
        processed_note = re.sub(r'\{\{image_placeholder\}\}', '<!-- 圖片處理失敗 -->', processed_note)
        return processed_note

def group_related_scenes(scene_summaries):
    """
    智能分組相關場景
    根據內容相似性和時間連續性將場景分組
    """
    if not scene_summaries:
        return []
    
    # 按索引排序確保順序正確
    scene_summaries.sort(key=lambda x: x['index'])
    
    groups = []
    current_group = []
    group_index = 0
    
    for i, scene in enumerate(scene_summaries):
        if not current_group:
            # 開始新組
            current_group = [scene]
        else:
            # 檢查是否應該加入當前組
            should_group = should_scenes_be_grouped(current_group[-1], scene)
            
            if should_group and len(current_group) < 5:  # 限制每組最多5個場景
                current_group.append(scene)
            else:
                # 完成當前組，開始新組
                groups.append({
                    'group_index': group_index,
                    'scenes': current_group.copy()
                })
                current_group = [scene]
                group_index += 1
    
    # 添加最後一組
    if current_group:
        groups.append({
            'group_index': group_index,
            'scenes': current_group
        })
    
    return groups

def should_scenes_be_grouped(scene1, scene2):
    """
    判斷兩個場景是否應該分組
    基於內容相似性和場景連續性
    """
    # 檢查場景索引是否連續（相鄰或間隔很小）
    if abs(scene1['index'] - scene2['index']) > 3:
        return False
    
    # 檢查內容相似性
    summary1 = scene1['summary'].lower()
    summary2 = scene2['summary'].lower()
    
    # 關鍵詞匹配 - 更全面的技術詞彙列表
    common_keywords = [
        'python', 'java', 'javascript', 'code', 'function', 'class', 'method',
        'variable', 'loop', 'if', 'else', 'for', 'while', 'import', 'def',
        'public', 'private', 'static', 'void', 'int', 'string', 'array',
        'list', 'dict', 'object', 'model', 'data', 'train', 'test', 'validation',
        'api', 'json', 'html', 'css', 'sql', 'database', 'server', 'client',
        'network', 'algorithm', 'structure', 'framework', 'library', 'package',
        'module', 'interface', 'implementation', 'inheritance', 'polymorphism',
        'encapsulation', 'abstraction', 'debug', 'error', 'exception', 'try',
        'catch', 'finally', 'thread', 'process', 'memory', 'file', 'input',
        'output', 'stream', 'buffer', 'cache', 'performance', 'optimization',
        'security', 'authentication', 'authorization', 'encryption', 'decryption'
    ]
    
    # 計算共同關鍵詞數量
    keywords1 = set(word for word in summary1.split() if word in common_keywords)
    keywords2 = set(word for word in summary2.split() if word in common_keywords)
    common_count = len(keywords1.intersection(keywords2))
    
    # 如果有共同關鍵詞，則分組
    if common_count > 0:
        return True
    
    # 檢查是否包含相似的程式碼結構
    code_patterns = ['```', 'def ', 'class ', 'function', 'import', 'from', '=', '()', '[]', '{}']
    code_count1 = sum(1 for pattern in code_patterns if pattern in summary1)
    code_count2 = sum(1 for pattern in code_patterns if pattern in summary2)
    
    # 如果都包含程式碼，則分組
    if code_count1 > 2 and code_count2 > 2:
        return True
    
    # 檢查是否包含相似的主題詞
    topic_patterns = [
        '介紹', '說明', '概念', '原理', '方法', '技術', '實作', '範例', 
        '練習', '測試', '除錯', '優化', '應用', '總結', '重點', '注意',
        'example', 'demo', 'sample', 'tutorial', 'guide', 'introduction'
    ]
    
    topic_match1 = any(pattern in summary1 for pattern in topic_patterns)
    topic_match2 = any(pattern in summary2 for pattern in topic_patterns)
    
    if topic_match1 and topic_match2:
        return True
    
    return False

def _filter_personal_info(text: str) -> str:
    """過濾 OCR 文字中的個人資訊"""
    if not text:
        return text
    
    # 過濾學號和姓名
    import re
    # 過濾老師的畫面分享提示
    text = re.sub(r'宇山亮\(画面を共有してアノテ一ションを付加しています\)', '[老師畫面分享]', text)
    text = re.sub(r'宇山亮\(画面を共有してアノテーションを付加しています\)', '[老師畫面分享]', text)
    # 過濾學號格式 (數字+中文姓名)
    text = re.sub(r'\d+[a-zA-Z]*\d*[林家誠王小明李四張三陳五劉六黃七吳八林九陳十]+', '[個人資訊]', text)
    # 過濾純學號
    text = re.sub(r'\b\d{8,12}[a-zA-Z]*\d*\b', '[學號]', text)
    # 過濾常見姓名
    text = re.sub(r'\b[林家誠王小明李四張三陳五劉六黃七吳八林九陳十]+\b', '[姓名]', text)
    
    return text

def filter_important_info(text):
    """ 过滤不重要信息的函数 """
    # 示例逻辑：移除常见填充词、重复信息等
    unimportant_words = ["这是一场", "通过选择", "了解两种类型"]
    words = text.split()
    filtered_words = [word for word in words if word not in unimportant_words]
    return ' '.join(filtered_words)

def combine_scene_summaries(scene_summaries):
    """ 合并场景摘要，保留关键信息 """
    combined_summary = ""
    for summary in scene_summaries:
        # 只保留每个场景的关键部分
        key_parts = [
            part for part in summary['summary'].split('\n')
            if any(keyword in part for keyword in ['主题', '重点', '程式码'])
        ]
        combined_summary += '\n'.join(key_parts) + '\n\n'
    return combined_summary

def generate_fallback_note(structured_summaries):
    """
    生成備用筆記格式（當 LLM 調用失敗時使用）
    """
    note_parts = []
    note_parts.append("# 📝 課程筆記（備用格式）")
    note_parts.append("")
    
    for i, group in enumerate(structured_summaries):
        note_parts.append(f"## 📊 場景組 {i + 1}")
        note_parts.append("")
        
        # 添加場景摘要
        for scene in group.get('scenes', []):
            note_parts.append(f"### 場景 {scene['index'] + 1}")
            # 若沒有有效摘要，回退到 ASR 文本摘錄，避免只有圖片
            _summary = (scene.get('summary') or '').strip()
            if not _summary:
                asr_text = (scene.get('asr_text') or '').strip()
                if asr_text:
                    # 擷取前 600 字，避免過長
                    excerpt = asr_text[:600]
                    _summary = f"**語音內容（摘錄）**\n\n{excerpt}"
                else:
                    _summary = "（暫無文字內容）"
            note_parts.append(_summary)
            note_parts.append("")
            
            # 添加圖片（如果有）
            if scene.get('image_path_final'):
                note_parts.append(f"![場景截圖]({scene['image_path_final']})")
                note_parts.append("")
        
        note_parts.append("---")
        note_parts.append("")
    
    return "\n".join(note_parts)
def _resolve_video_path(video_path: str) -> str:
    """Ensure the provided video path exists, falling back to configured roots."""
    if os.path.isabs(video_path) and os.path.exists(video_path):
        return video_path

    service = get_media_path_service()
    base_path = service.get("video_path", "")
    if not base_path:
        return video_path

    resolution = service.resolve(os.path.expandvars(base_path))
    candidate_roots = [
        resolution.accessible_path,
        resolution.container_path,
        resolution.normalized_path,
    ]
    normalized_relative = video_path.replace("\\", "/").lstrip("/")
    for root in candidate_roots:
        if not root:
            continue
        candidate = os.path.join(root, normalized_relative)
        if os.path.exists(candidate):
            return candidate
    return video_path



