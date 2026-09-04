#!/bin/bash
# 系統冗餘檔案清理腳本
# 執行前請先備份重要資料

set -e

echo "🧹 開始清理系統冗餘檔案..."
echo "================================================"

# 1. 刪除根目錄 node_modules（前端依賴應在 frontend/ 內）
if [ -d "node_modules" ]; then
    echo "📦 刪除根目錄 node_modules..."
    rm -rf node_modules
    echo "✅ 已刪除 node_modules/"
fi

if [ -f "package.json" ] && [ ! -f "frontend/package.json" ]; then
    echo "⚠️  警告：根目錄有 package.json 但 frontend/ 沒有，跳過刪除"
elif [ -f "package.json" ]; then
    echo "📦 刪除根目錄 package.json 和 package-lock.json..."
    rm -f package.json package-lock.json
    echo "✅ 已刪除重複的 package.json"
fi

# 2. 清理 Python 快取
echo ""
echo "🐍 清理 Python 快取..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
echo "✅ 已清理 Python 快取"

# 3. 清理 IDE 快取
echo ""
echo "💾 清理 IDE 快取..."
if [ -d ".cursor" ]; then
    rm -rf .cursor
    echo "✅ 已刪除 .cursor/"
fi

if [ -d ".pytest_cache" ]; then
    rm -rf .pytest_cache
    echo "✅ 已刪除 .pytest_cache/"
fi

# 4. 建立 scripts/maintenance/ 目錄
echo ""
echo "📁 整理工具腳本..."
mkdir -p scripts/maintenance

# 移動 ultimate-fix.js
if [ -f "ultimate-fix.js" ]; then
    mv ultimate-fix.js scripts/maintenance/
    echo "✅ 已移動 ultimate-fix.js → scripts/maintenance/"
fi

# 移動 optimize_system.py
if [ -f "optimize_system.py" ]; then
    mv optimize_system.py scripts/maintenance/
    echo "✅ 已移動 optimize_system.py → scripts/maintenance/"
fi

# 5. 建立 scripts/docker/ 目錄並移動批次檔
echo ""
echo "🐳 整理 Docker 腳本..."
mkdir -p scripts/docker

for bat_file in *.bat *.sh; do
    if [ -f "$bat_file" ] && [[ "$bat_file" != "scripts/"* ]]; then
        mv "$bat_file" scripts/docker/
        echo "✅ 已移動 $bat_file → scripts/docker/"
    fi
done

# 6. 清理日誌檔案（保留最近 7 天）
echo ""
echo "📝 清理舊日誌檔案（保留最近 7 天）..."
if [ -d "logs" ]; then
    find logs -type f -name "*.log" -mtime +7 -delete 2>/dev/null || true
    echo "✅ 已清理舊日誌"
fi

# 7. 清理暫存輸出（保留最近 14 天）
echo ""
echo "📂 清理暫存輸出（保留最近 14 天）..."
if [ -d "output/tmp" ]; then
    find output/tmp -type f -mtime +14 -delete 2>/dev/null || true
    echo "✅ 已清理暫存輸出"
fi

# 8. 顯示空間釋放情況
echo ""
echo "================================================"
echo "✨ 清理完成！"
echo ""
echo "📊 建議手動檢查以下項目："
echo "  1. .specstory/history/ - 若不需要歷史快照可刪除"
echo "  2. external_c/, external_f/ - 確認是否為空目錄"
echo "  3. frontend/dist/ - 前端打包產物，可重新建置"
echo "  4. output/images/ - 舊的輸出圖片，可定期清理"
echo ""
echo "🔄 下一步："
echo "  docker-compose down && docker-compose up --build -d"
