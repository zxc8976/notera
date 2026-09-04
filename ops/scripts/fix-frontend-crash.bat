@echo off
REM 前端崩潰修復腳本 - 解決 Bun Segmentation Fault 問題
REM 創建時間: 2026-01-31
REM 用途: 清理並重新建置前端環境

echo ========================================
echo 前端崩潰修復工具
echo ========================================
echo.

cd /d "%~dp0..\..\source\frontend"

echo [1/5] 停止可能正在運行的開發伺服器...
taskkill /F /IM bun.exe 2>NUL
taskkill /F /IM node.exe 2>NUL
timeout /t 2 /nobreak >NUL

echo [2/5] 清理舊的 node_modules 和 lock 檔案...
if exist node_modules (
    echo 正在刪除 node_modules...
    rmdir /s /q node_modules
)
if exist bun.lockb (
    echo 正在刪除 bun.lockb...
    del /f /q bun.lockb
)
if exist package-lock.json (
    echo 正在刪除 package-lock.json...
    del /f /q package-lock.json
)

echo [3/5] 清理 Bun 快取...
bun pm cache rm 2>NUL

echo [4/5] 重新安裝依賴 (這可能需要幾分鐘)...
bun install --force

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ 安裝失敗!嘗試使用 npm 安裝...
    npm install
)

echo [5/5] 清理開發伺服器快取...
if exist .vite (
    rmdir /s /q .vite
)

echo.
echo ========================================
echo ✅ 修復完成!
echo ========================================
echo.
echo 現在你可以嘗試重新啟動開發伺服器:
echo   cd source\frontend
echo   bun run dev
echo.
echo 如果問題仍然存在,請嘗試:
echo   1. 更新 Bun: bun upgrade
echo   2. 使用 npm 代替: npm run dev
echo   3. 檢查系統記憶體是否充足
echo.
pause
