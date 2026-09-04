#!/usr/bin/env python
"""檢查圖片文件格式"""
import os
from PIL import Image

test_folder = "/app/external_f/講義圖片/クライアント/test"

for filename in os.listdir(test_folder):
    filepath = os.path.join(test_folder, filename)
    print(f"\n=== {filename} ===")
    print(f"文件大小: {os.path.getsize(filepath)} bytes")
    
    try:
        with Image.open(filepath) as img:
            print(f"格式: {img.format}")
            print(f"模式: {img.mode}")
            print(f"尺寸: {img.size}")
            print("✅ PIL 可以打開")
    except Exception as e:
        print(f"❌ PIL 無法打開: {e}")
