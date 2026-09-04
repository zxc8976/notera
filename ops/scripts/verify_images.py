#!/usr/bin/env python3
"""
圖片路徑驗證腳本
檢查筆記中的圖片引用是否都指向實際存在的檔案
"""

import os
import re
from pathlib import Path

# 專案根目錄
PROJECT_ROOT = Path(__file__).parent.parent.parent
NOTES_DIR = PROJECT_ROOT / "var" / "notes"
FRONTEND_PUBLIC = PROJECT_ROOT / "source" / "frontend" / "public"
FRONTEND_DIST = PROJECT_ROOT / "source" / "frontend" / "dist"

def find_markdown_files(directory):
    """遞迴查找所有 Markdown 檔案"""
    md_files = []
    if not directory.exists():
        return md_files
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.md'):
                md_files.append(Path(root) / file)
    return md_files

def extract_image_paths(md_content):
    """從 Markdown 內容中提取圖片路徑"""
    # 匹配 ![...](path) 和 ![...](/images/path)
    pattern = r'!\[.*?\]\((.*?)\)'
    matches = re.findall(pattern, md_content)
    return matches

def check_image_exists(image_path):
    """檢查圖片是否存在"""
    # 移除開頭的 /
    clean_path = image_path.lstrip('/')
    
    # 檢查 public 和 dist 目錄
    public_path = FRONTEND_PUBLIC / clean_path
    dist_path = FRONTEND_DIST / clean_path
    
    return public_path.exists() or dist_path.exists(), public_path, dist_path

def main():
    print("=" * 60)
    print("圖片路徑驗證工具")
    print("=" * 60)
    print()
    
    # 查找所有筆記檔案
    md_files = find_markdown_files(NOTES_DIR)
    print(f"📁 找到 {len(md_files)} 個筆記檔案")
    print()
    
    total_images = 0
    missing_images = []
    found_images = 0
    
    for md_file in md_files:
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            image_paths = extract_image_paths(content)
            if not image_paths:
                continue
                
            print(f"\n📄 {md_file.name}")
            print(f"   圖片數量: {len(image_paths)}")
            
            for img_path in image_paths:
                total_images += 1
                exists, public_path, dist_path = check_image_exists(img_path)
                
                if exists:
                    found_images += 1
                    actual_path = public_path if public_path.exists() else dist_path
                    print(f"   ✅ {img_path}")
                    print(f"      → {actual_path.relative_to(PROJECT_ROOT)}")
                else:
                    missing_images.append((md_file, img_path))
                    print(f"   ❌ {img_path}")
                    print(f"      查找位置:")
                    print(f"      - {public_path.relative_to(PROJECT_ROOT)}")
                    print(f"      - {dist_path.relative_to(PROJECT_ROOT)}")
        
        except Exception as e:
            print(f"   ⚠️  讀取失敗: {e}")
    
    # 總結報告
    print()
    print("=" * 60)
    print("驗證結果摘要")
    print("=" * 60)
    print(f"總圖片數量: {total_images}")
    print(f"✅ 找到圖片: {found_images}")
    print(f"❌ 缺失圖片: {len(missing_images)}")
    print()
    
    if missing_images:
        print("缺失的圖片清單:")
        print("-" * 60)
        for md_file, img_path in missing_images:
            print(f"📄 {md_file.name}")
            print(f"   → {img_path}")
        print()
        print("⚠️  建議:")
        print("   1. 檢查後端筆記生成程式碼 (note_generator.py)")
        print("   2. 確認圖片已正確複製到 public/images/ 目錄")
        print("   3. 重新處理相關的影片或圖片來源")
        return 1
    else:
        print("🎉 所有圖片路徑都正確!")
        return 0

if __name__ == "__main__":
    exit(main())
