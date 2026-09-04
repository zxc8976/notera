#!/usr/bin/env python3
"""批量轉換 HEIC 圖片為 JPG 格式（復用 FileProcessor 邏輯）"""
import os
import shutil
from modules.file_handlers import file_processor

def main():
    # 圖片目錄\n    project_root = Path(__file__).resolve().parents[3]\n    local_dir = project_root / "source" / "frontend" / "public" / "images"\n    container_dir = Path("/app/source/frontend/public/images")\n    image_path = container_dir if container_dir.exists() else local_dir\n    if not image_path.exists():\n        print(f"❌ 目錄不存在: {image_path}")\n        return\n    image_dir = str(image_path)\n    
    # 找到所有 HEIC 文件
    heic_files = []
    for file in os.listdir(image_dir):
        if file.lower().endswith('.heic'):
            heic_path = os.path.join(image_dir, file)
            jpg_path = os.path.join(image_dir, file.rsplit('.', 1)[0] + '_converted.jpg')
            
            # 檢查是否已經轉換
            if not os.path.exists(jpg_path):
                heic_files.append((heic_path, jpg_path))
            else:
                print(f"⏭️  已存在: {os.path.basename(jpg_path)}")
    
    if not heic_files:
        print("✅ 所有 HEIC 文件都已轉換")
        return
    
    print(f"🔄 需要轉換 {len(heic_files)} 個文件...")
    
    # 批量轉換
    success_count = 0
    for heic_path, jpg_path in heic_files:
        converted_path = file_processor.handle_heic_format(heic_path)
        if not converted_path or not os.path.exists(converted_path):
            print(f"❌ 轉換失敗 {os.path.basename(heic_path)}: 無法產出可用檔案")
            continue

        try:
            shutil.copy2(converted_path, jpg_path)
            print(f"✅ 轉換成功: {os.path.basename(heic_path)} -> {os.path.basename(jpg_path)}")
            success_count += 1
        except Exception as e:
            print(f"❌ 複製失敗 {os.path.basename(heic_path)}: {e}")
    
    print(f"\n🎉 轉換完成: {success_count}/{len(heic_files)} 個文件成功")

if __name__ == "__main__":
    main()

