#!/bin/bash

# 自動筆記生成系統 - Docker 構建腳本 v3.0.1-enhanced
# 包含UI修復和功能增強

echo "🚀 開始構建自動筆記生成系統 v3.0.1-enhanced"
echo "包含以下修復和增強："
echo "  ✅ 聊天機器人頁面UI修復"
echo "  ✅ 語言切換功能完善"
echo "  ✅ 筆記頁面深色模式修復"
echo "  ✅ 學習重點總結功能修復"
echo ""

# 檢查Docker是否安裝
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安裝，請先安裝 Docker"
    exit 1
fi

# 檢查Docker Compose是否安裝
if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose 未安裝，請先安裝 Docker Compose"
    exit 1
fi

# 檢查NVIDIA Docker是否可用
if ! docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi &> /dev/null; then
    echo "⚠️  警告：NVIDIA Docker 支持可能未正確配置"
    echo "   如果您有NVIDIA GPU，請確保已安裝 nvidia-docker2"
fi

# 停止現有容器
echo "🛑 停止現有容器..."
docker compose down

# 清理舊的鏡像（可選）
read -p "是否清理舊的Docker鏡像？(y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🧹 清理舊鏡像..."
    docker system prune -f
    docker image prune -f
fi

# 構建鏡像
echo "🔨 構建Docker鏡像..."
docker compose build --no-cache

# 檢查構建是否成功
if [ $? -eq 0 ]; then
    echo "✅ Docker鏡像構建成功！"
else
    echo "❌ Docker鏡像構建失敗"
    exit 1
fi

# 啟動服務
echo "🚀 啟動服務..."
docker compose up -d

# 等待服務啟動
echo "⏳ 等待服務啟動..."
sleep 10

# 檢查服務狀態
echo "📊 檢查服務狀態..."
docker compose ps

# 檢查健康狀態
echo "🏥 檢查服務健康狀態..."
echo "前端服務: http://localhost:5173"
echo "後端服務: http://localhost:18000"
echo "Ollama服務: http://localhost:11434"

# 等待服務完全啟動
echo "⏳ 等待服務完全啟動（30秒）..."
sleep 30

# 測試服務連接
echo "🧪 測試服務連接..."

# 測試前端
if curl -f http://localhost:5173 &> /dev/null; then
    echo "✅ 前端服務正常運行"
else
    echo "⚠️  前端服務可能還在啟動中"
fi

# 測試後端
if curl -f http://localhost:18000/api/version &> /dev/null; then
    echo "✅ 後端服務正常運行"
else
    echo "⚠️  後端服務可能還在啟動中"
fi

# 測試Ollama
if curl -f http://localhost:11434/api/version &> /dev/null; then
    echo "✅ Ollama服務正常運行"
else
    echo "⚠️  Ollama服務可能還在啟動中"
fi

echo ""
echo "🎉 部署完成！"
echo ""
echo "📱 訪問地址："
echo "  前端界面: http://localhost:5173"
echo "  後端API:  http://localhost:18000"
echo "  Ollama:   http://localhost:11434"
echo ""
echo "📋 常用命令："
echo "  查看日誌: docker compose logs -f"
echo "  停止服務: docker compose down"
echo "  重啟服務: docker compose restart"
echo "  查看狀態: docker compose ps"
echo ""
echo "🔧 如果遇到問題："
echo "  1. 檢查Docker和NVIDIA Docker是否正確安裝"
echo "  2. 確保端口5173、18000、11434未被占用"
echo "  3. 檢查磁盤空間是否充足"
echo "  4. 查看容器日誌排查問題"
echo ""
echo "✨ 新功能和修復："
echo "  - 聊天機器人頁面完全重新設計，無藍色標題欄干擾"
echo "  - 語言切換功能在所有頁面正常工作"
echo "  - 筆記頁面深色模式文字顏色修復"
echo "  - 學習重點總結功能增強"
echo "  - 支持HEIC圖片格式轉換"
echo "  - 改進的錯誤處理和用戶體驗"