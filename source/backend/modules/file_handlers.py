#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
文件處理模組 - 處理視頻和圖片文件的相關操作
"""

import os
import json
import logging
import shutil
import base64
import tempfile
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import pillow_heif  # type: ignore
    pillow_heif.register_heif_opener()
    _HAS_HEIF = True
except Exception:
    pillow_heif = None  # type: ignore
    _HAS_HEIF = False

def get_video_files(video_path: str) -> List[Dict[str, Any]]:
    """獲取視頻文件列表"""
    try:
        if not video_path or not os.path.exists(video_path):
            return []
        
        videos = []
        supported_formats = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'}
        
        for root, dirs, files in os.walk(video_path):
            for file in files:
                if any(file.lower().endswith(ext) for ext in supported_formats):
                    full_path = os.path.join(root, file)
                    relative_path = os.path.relpath(full_path, video_path)
                    
                    try:
                        stat = os.stat(full_path)
                        videos.append({
                            "name": file,
                            "path": relative_path,
                            "size": stat.st_size,
                            "modified": stat.st_mtime
                        })
                    except OSError:
                        continue
        
        return sorted(videos, key=lambda x: x['modified'], reverse=True)
        
    except Exception as e:
        logger.error(f"獲取視頻文件時出錯: {e}")
        return []

def get_image_files(image_path: str) -> List[Dict[str, Any]]:
    """獲取圖片文件列表"""
    try:
        if not image_path or not os.path.exists(image_path):
            return []
        
        images = []
        supported_formats = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.heic', '.heif'}
        
        for root, dirs, files in os.walk(image_path):
            for file in files:
                if any(file.lower().endswith(ext) for ext in supported_formats):
                    full_path = os.path.join(root, file)
                    relative_path = os.path.relpath(full_path, image_path)
                    
                    try:
                        stat = os.stat(full_path)
                        images.append({
                            "name": file,
                            "path": relative_path,
                            "size": stat.st_size,
                            "modified": stat.st_mtime
                        })
                    except OSError:
                        continue
        
        return sorted(images, key=lambda x: x['modified'], reverse=True)
        
    except Exception as e:
        logger.error(f"獲取圖片文件時出錯: {e}")
        return []

def ensure_directory_exists(directory: str) -> bool:
    """確保目錄存在"""
    try:
        os.makedirs(directory, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"創建目錄失敗 {directory}: {e}")
        return False

def get_file_info(file_path: str) -> Dict[str, Any]:
    """獲取文件信息"""
    try:
        if not os.path.exists(file_path):
            return {}
        
        stat = os.stat(file_path)
        return {
            "name": os.path.basename(file_path),
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "exists": True
        }
    except Exception as e:
        logger.error(f"獲取文件信息失敗 {file_path}: {e}")
        return {"exists": False}

def copy_file_safely(src: str, dst: str) -> bool:
    """安全地複製文件"""
    try:
        # 確保目標目錄存在
        dst_dir = os.path.dirname(dst)
        ensure_directory_exists(dst_dir)
        
        # 複製文件
        shutil.copy2(src, dst)
        return True
    except Exception as e:
        logger.error(f"複製文件失敗 {src} -> {dst}: {e}")
        return False

def delete_file_safely(file_path: str) -> bool:
    """安全地刪除文件"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    except Exception as e:
        logger.error(f"刪除文件失敗 {file_path}: {e}")
        return False

class FileProcessor:
    """統一的文件處理器 - 消除重複的路徑和格式處理邏輯"""
    
    @staticmethod
    def normalize_path(path: str) -> str:
        """
        統一的路徑正規化
        處理相對路徑、絕對路徑、Windows/Unix分隔符
        
        Args:
            path: 原始路徑
            
        Returns:
            正規化的路徑
        """
        if not path:
            return ""
        
        # 轉換為絕對路徑，處理相對路徑
        normalized_path = os.path.abspath(os.path.expanduser(path))
        
        # 統一路徑分隔符
        normalized_path = os.path.normpath(normalized_path)
        
        logger.debug(f"[FileProcessor] 路徑正規化: {path} → {normalized_path}")
        return normalized_path
    
    @staticmethod
    def handle_heic_format(image_path: str) -> str:
        """
        處理HEIC格式圖片 - 統一接口
        
        Args:
            image_path: 原始圖片路徑
            
        Returns:
            處理後的圖片路徑
        """
        try:
            if not os.path.exists(image_path):
                logger.error(f"[FileProcessor] 圖片不存在: {image_path}")
                return ""
            
            lowercase_path = image_path.lower()

            # 非 HEIC 直接返回
            if not lowercase_path.endswith(('.heic', '.heif')):
                logger.debug(f"[FileProcessor] 非HEIC格式，直接返回: {image_path}")
                return image_path

            # 轉換 HEIC → JPEG
            temp_dir = tempfile.gettempdir()
            base_name = os.path.splitext(os.path.basename(image_path))[0]
            jpeg_path = os.path.join(temp_dir, f"{base_name}_converted.jpg")

            from PIL import Image

            # 若環境支援 pillow-heif，於此補註冊（避免其他模組未觸發）
            if not _HAS_HEIF:
                try:
                    import pillow_heif  # type: ignore
                    pillow_heif.register_heif_opener()
                except Exception:
                    pass

            with Image.open(image_path) as img:
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                img.save(jpeg_path, 'JPEG', quality=95)

            if os.path.exists(jpeg_path):
                logger.info(f"[FileProcessor] HEIC轉換成功: {image_path} → {jpeg_path}")
                return jpeg_path

            logger.warning(f"[FileProcessor] HEIC轉換結果不存在，返回原始路徑: {image_path}")
            return image_path

        except Exception as e:
            logger.error(f"[FileProcessor] HEIC轉換失敗: {e}")
            return image_path  # 失敗時返回原路徑
    
    @staticmethod
    def ensure_readable_format(file_path: str, target_format: str = "mp4") -> str:
        """
        確保文件為可讀格式 - 統一接口
        
        Args:
            file_path: 原始文件路徑
            target_format: 目標格式 (mp4, jpg等)
            
        Returns:
            處理後的文件路徑
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"[FileProcessor] 文件不存在: {file_path}")
                return ""
            
            if target_format == "mp4":
                # 影片格式處理邏輯
                return FileProcessor._ensure_readable_mp4(file_path)
            elif target_format == "jpg":
                # 圖片格式處理邏輯
                return FileProcessor.handle_heic_format(file_path)
            else:
                logger.warning(f"[FileProcessor] 不支援的目標格式: {target_format}")
                return file_path
                
        except Exception as e:
            logger.error(f"[FileProcessor] 格式處理失敗: {e}")
            return file_path
    
    @staticmethod
    def _ensure_readable_mp4(src_path: str) -> str:
        """內部方法：確保MP4文件可讀"""
        try:
            # 這裡可以加入影片格式驗證和轉換邏輯
            # 暫時直接返回原路徑
            logger.debug(f"[FileProcessor] MP4格式檢查: {src_path}")
            return src_path
        except Exception as e:
            logger.error(f"[FileProcessor] MP4格式處理失敗: {e}")
            return src_path
    
    @staticmethod
    def encode_image_to_base64(image_path: str) -> str:
        """
        將圖片編碼為Base64 - 統一接口
        
        Args:
            image_path: 圖片路徑
            
        Returns:
            Base64編碼的字串
        """
        try:
            if not os.path.exists(image_path):
                logger.error(f"[FileProcessor] 圖片不存在: {image_path}")
                return ""
            
            with open(image_path, "rb") as image_file:
                image_data = image_file.read()
                base64_encoded = base64.b64encode(image_data).decode('utf-8')
            
            logger.debug(f"[FileProcessor] 圖片編碼成功，大小: {len(base64_encoded)}字符")
            return base64_encoded
            
        except Exception as e:
            logger.error(f"[FileProcessor] 圖片編碼失敗: {e}")
            return ""

# 全域文件處理器實例
file_processor = FileProcessor()