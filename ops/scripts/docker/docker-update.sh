#!/bin/bash

# 🐳 Docker更新腳本 - 架構重構版本
# 用於更新Docker容器以支持新的模組化架構

set -e

echo "🐳 開始Docker更新 - 架構重構版本"
echo "=================================="

# 設置構建時間戳
export BUILD_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
echo "📅 構建時間戳: $BUILD_TIMESTAMP"

# 1. 停止現有容器
echo "🛑 停止現有容器..."
docker-compose down

# 2. 清理舊的鏡像（可選）
echo "🧹 清理舊的Docker鏡像..."
docker image prune -f

# 3. 重新構建前端容器（無緩存）
echo "🔨 重新構建前端容器（架構重構版本）..."
docker-compose build --no-cache frontend

# 4. 重新構建後端容器（如果需要）
echo "🔨 檢查後端容器是否需要更新..."
if [ "$1" = "--rebuild-backend" ]; then
    echo "🔨 重新構建後端容器..."
    docker-compose build --no-cache notegen
fi

# 5. 啟動所有服務
echo "🚀 啟動所有服務..."
docker-compose up -d

# 6. 等待服務啟動
echo "⏳ 等待服務啟動..."
sleep 10

# 7. 檢查服務狀態
echo "🔍 檢查服務狀態..."
docker-compose ps

# 8. 檢查前端架構文件
echo "🏗️ 驗證前端架構文件..."
if docker exec notegen-frontend-enhanced test -f /app/src/layouts/DefaultLayout.vue; then
    echo "✅ DefaultLayout.vue 存在"
else
    echo "❌ DefaultLayout.vue 缺失"
fi

if docker exec notegen-frontend-enhanced test -f /app/src/layouts/ChatbotLayout.vue; then
    echo "✅ ChatbotLayout.vue 存在"
else
    echo "❌ ChatbotLayout.vue 缺失"
fi

if docker exec notegen-frontend-enhanced test -f /app/src/styles/variables.css; then
    echo "✅ variables.css 存在"
else
    echo "❌ variables.css 缺失"
fi

# 9. 測試前端連接
echo "🌐 測試前端連接..."
if curl -f http://localhost:5173 > /dev/null 2>&1; then
    echo "✅ 前端服務正常運行"
else
    echo "❌ 前端服務連接失敗"
fi

# 10. 測試後端連接
echo "🔧 測試後端連接..."
if curl -f http://localhost:18000/api/models > /dev/null 2>&1; then
    echo "✅ 後端服務正常運行"
else
    echo "❌ 後端服務連接失敗"
fi

# 11. 顯示容器日誌（最後10行）
echo "📋 前端容器日誌（最後10行）:"
docker logs notegen-frontend-enhanced --tail 10

echo ""
echo "🎉 Docker更新完成！"
echo "=================================="
echo "📊 服務狀態:"
echo "   前端: http://localhost:5173"
echo "   後端: http://localhost:18000"
echo "   Ollama: http://localhost:11434"
echo ""
echo "🏗️ 架構特性:"
echo "   ✅ 模組化佈局系統"
echo "   ✅ 統一CSS變量"
echo "   ✅ 語言統一修復"
echo "   ✅ 導航組件化"
echo ""
echo "🛠️ 如果遇到問題，請運行:"
echo "   docker-compose logs <service_name>"
echo "   docker-compose restart <service_name>"