@echo off
chcp 65001 >nul

REM 自動筆記生成系統 - Docker 構建腳本 v3.0.1-enhanced (Windows版本)
REM 包含UI修復和功能增強

echo 🚀 開始構建自動筆記生成系統 v3.0.1-enhanced
echo 包含以下修復和增強：
echo   ✅ 聊天機器人頁面UI修復
echo   ✅ 語言切換功能完善
echo   ✅ 筆記頁面深色模式修復
echo   ✅ 學習重點總結功能修復
echo.

REM 檢查Docker是否安裝
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker 未安裝，請先安裝 Docker Desktop
    pause
    exit /b 1
)

REM 檢查Docker Compose是否安裝
docker compose version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker Compose 未安裝，請先安裝 Docker Compose
    pause
    exit /b 1
)

REM 停止現有容器
echo 🛑 停止現有容器...
docker compose down

REM 詢問是否清理舊鏡像
set /p cleanup="是否清理舊的Docker鏡像？(y/N): "
if /i "%cleanup%"=="y" (
    echo 🧹 清理舊鏡像...
    docker system prune -f
    docker image prune -f
)

REM 構建鏡像
echo 🔨 構建Docker鏡像...
docker compose build --no-cache

REM 檢查構建是否成功
if errorlevel 1 (
    echo ❌ Docker鏡像構建失敗
    pause
    exit /b 1
)

echo ✅ Docker鏡像構建成功！

REM 啟動服務
echo 🚀 啟動服務...
docker compose up -d

REM 等待服務啟動
echo ⏳ 等待服務啟動...
timeout /t 10 /nobreak >nul

REM 檢查服務狀態
echo 📊 檢查服務狀態...
docker compose ps

REM 檢查健康狀態
echo 🏥 檢查服務健康狀態...
echo 前端服務: http://localhost:5173
echo 後端服務: http://localhost:18000
echo Ollama服務: http://localhost:11434

REM 等待服務完全啟動
echo ⏳ 等待服務完全啟動（30秒）...
timeout /t 30 /nobreak >nul

REM 測試服務連接
echo 🧪 測試服務連接...

REM 測試前端
curl -f http://localhost:5173 >nul 2>&1
if errorlevel 1 (
    echo ⚠️  前端服務可能還在啟動中
) else (
    echo ✅ 前端服務正常運行
)

REM 測試後端
curl -f http://localhost:18000/api/version >nul 2>&1
if errorlevel 1 (
    echo ⚠️  後端服務可能還在啟動中
) else (
    echo ✅ 後端服務正常運行
)

REM 測試Ollama
curl -f http://localhost:11434/api/version >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Ollama服務可能還在啟動中
) else (
    echo ✅ Ollama服務正常運行
)

echo.
echo 🎉 部署完成！
echo.
echo 📱 訪問地址：
echo   前端界面: http://localhost:5173
echo   後端API:  http://localhost:18000
echo   Ollama:   http://localhost:11434
echo.
echo 📋 常用命令：
echo   查看日誌: docker compose logs -f
echo   停止服務: docker compose down
echo   重啟服務: docker compose restart
echo   查看狀態: docker compose ps
echo.
echo 🔧 如果遇到問題：
echo   1. 檢查Docker Desktop是否正確安裝並運行
echo   2. 確保端口5173、18000、11434未被占用
echo   3. 檢查磁盤空間是否充足
echo   4. 查看容器日誌排查問題
echo.
echo ✨ 新功能和修復：
echo   - 聊天機器人頁面完全重新設計，無藍色標題欄干擾
echo   - 語言切換功能在所有頁面正常工作
echo   - 筆記頁面深色模式文字顏色修復
echo   - 學習重點總結功能增強
echo   - 支持HEIC圖片格式轉換
echo   - 改進的錯誤處理和用戶體驗
echo.
pause