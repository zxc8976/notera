@echo off
REM 🐳 Docker更新腳本 - 架構重構版本 (Windows)
REM 用於更新Docker容器以支持新的模組化架構

echo 🐳 開始Docker更新 - 架構重構版本
echo ==================================

REM 設置構建時間戳
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "BUILD_TIMESTAMP=%dt:~0,8%_%dt:~8,6%"
echo 📅 構建時間戳: %BUILD_TIMESTAMP%

REM 1. 停止現有容器
echo 🛑 停止現有容器...
docker-compose down

REM 2. 清理舊的鏡像（可選）
echo 🧹 清理舊的Docker鏡像...
docker image prune -f

REM 3. 重新構建前端容器（無緩存）
echo 🔨 重新構建前端容器（架構重構版本）...
docker-compose build --no-cache frontend

REM 4. 重新構建後端容器（如果需要）
echo 🔨 檢查後端容器是否需要更新...
if "%1"=="--rebuild-backend" (
    echo 🔨 重新構建後端容器...
    docker-compose build --no-cache notegen
)

REM 5. 啟動所有服務
echo 🚀 啟動所有服務...
docker-compose up -d

REM 6. 等待服務啟動
echo ⏳ 等待服務啟動...
timeout /t 10 /nobreak > nul

REM 7. 檢查服務狀態
echo 🔍 檢查服務狀態...
docker-compose ps

REM 8. 檢查前端架構文件
echo 🏗️ 驗證前端架構文件...
docker exec notegen-frontend-enhanced test -f /app/src/layouts/DefaultLayout.vue && (
    echo ✅ DefaultLayout.vue 存在
) || (
    echo ❌ DefaultLayout.vue 缺失
)

docker exec notegen-frontend-enhanced test -f /app/src/layouts/ChatbotLayout.vue && (
    echo ✅ ChatbotLayout.vue 存在
) || (
    echo ❌ ChatbotLayout.vue 缺失
)

docker exec notegen-frontend-enhanced test -f /app/src/styles/variables.css && (
    echo ✅ variables.css 存在
) || (
    echo ❌ variables.css 缺失
)

REM 9. 測試前端連接
echo 🌐 測試前端連接...
curl -f http://localhost:5173 > nul 2>&1 && (
    echo ✅ 前端服務正常運行
) || (
    echo ❌ 前端服務連接失敗
)

REM 10. 測試後端連接
echo 🔧 測試後端連接...
curl -f http://localhost:18000/api/models > nul 2>&1 && (
    echo ✅ 後端服務正常運行
) || (
    echo ❌ 後端服務連接失敗
)

REM 11. 顯示容器日誌（最後10行）
echo 📋 前端容器日誌（最後10行）:
docker logs notegen-frontend-enhanced --tail 10

echo.
echo 🎉 Docker更新完成！
echo ==================================
echo 📊 服務狀態:
echo    前端: http://localhost:5173
echo    後端: http://localhost:18000
echo    Ollama: http://localhost:11434
echo.
echo 🏗️ 架構特性:
echo    ✅ 模組化佈局系統
echo    ✅ 統一CSS變量
echo    ✅ 語言統一修復
echo    ✅ 導航組件化
echo.
echo 🛠️ 如果遇到問題，請運行:
echo    docker-compose logs ^<service_name^>
echo    docker-compose restart ^<service_name^>

pause