# 系統冗餘檔案清理腳本（Windows PowerShell 版本）
# 執行前請先備份重要資料

Write-Host "🧹 開始清理系統冗餘檔案..." -ForegroundColor Cyan
Write-Host "================================================"

# 1. 刪除根目錄 node_modules
if (Test-Path "node_modules") {
    Write-Host "📦 刪除根目錄 node_modules..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force "node_modules"
    Write-Host "✅ 已刪除 node_modules/" -ForegroundColor Green
}

if ((Test-Path "package.json") -and (Test-Path "frontend\package.json")) {
    Write-Host "📦 刪除根目錄 package.json 和 package-lock.json..." -ForegroundColor Yellow
    Remove-Item -Force "package.json", "package-lock.json" -ErrorAction SilentlyContinue
    Write-Host "✅ 已刪除重複的 package.json" -ForegroundColor Green
}

# 2. 清理 Python 快取
Write-Host "`n🐍 清理 Python 快取..." -ForegroundColor Yellow
Get-ChildItem -Path . -Directory -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem -Path . -Directory -Recurse -Filter ".pytest_cache" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
Get-ChildItem -Path . -File -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem -Path . -File -Recurse -Filter "*.pyo" -ErrorAction SilentlyContinue | Remove-Item -Force
Write-Host "✅ 已清理 Python 快取" -ForegroundColor Green

# 3. 清理 IDE 快取
Write-Host "`n💾 清理 IDE 快取..." -ForegroundColor Yellow
if (Test-Path ".cursor") {
    Remove-Item -Recurse -Force ".cursor"
    Write-Host "✅ 已刪除 .cursor/" -ForegroundColor Green
}

if (Test-Path ".pytest_cache") {
    Remove-Item -Recurse -Force ".pytest_cache"
    Write-Host "✅ 已刪除 .pytest_cache/" -ForegroundColor Green
}

# 4. 建立 scripts/maintenance/ 目錄並整理工具
Write-Host "`n📁 整理工具腳本..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "scripts\maintenance" | Out-Null

if (Test-Path "ultimate-fix.js") {
    Move-Item -Force "ultimate-fix.js" "scripts\maintenance\"
    Write-Host "✅ 已移動 ultimate-fix.js → scripts\maintenance\" -ForegroundColor Green
}

if (Test-Path "optimize_system.py") {
    Move-Item -Force "optimize_system.py" "scripts\maintenance\"
    Write-Host "✅ 已移動 optimize_system.py → scripts\maintenance\" -ForegroundColor Green
}

# 5. 建立 scripts/docker/ 目錄並移動批次檔
Write-Host "`n🐳 整理 Docker 腳本..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "scripts\docker" | Out-Null

Get-ChildItem -Path . -Filter "*.bat" | Where-Object { $_.DirectoryName -eq (Get-Location).Path } | ForEach-Object {
    Move-Item -Force $_.FullName "scripts\docker\"
    Write-Host "✅ 已移動 $($_.Name) → scripts\docker\" -ForegroundColor Green
}

Get-ChildItem -Path . -Filter "*.sh" | Where-Object { $_.DirectoryName -eq (Get-Location).Path -and $_.Name -ne "cleanup_redundant.sh" } | ForEach-Object {
    Move-Item -Force $_.FullName "scripts\docker\"
    Write-Host "✅ 已移動 $($_.Name) → scripts\docker\" -ForegroundColor Green
}

# 6. 清理舊日誌（保留最近 7 天）
Write-Host "`n📝 清理舊日誌檔案（保留最近 7 天）..." -ForegroundColor Yellow
if (Test-Path "logs") {
    $cutoffDate = (Get-Date).AddDays(-7)
    Get-ChildItem -Path "logs" -Filter "*.log" -Recurse -ErrorAction SilentlyContinue | 
        Where-Object { $_.LastWriteTime -lt $cutoffDate } | 
        Remove-Item -Force
    Write-Host "✅ 已清理舊日誌" -ForegroundColor Green
}

# 7. 清理暫存輸出（保留最近 14 天）
Write-Host "`n📂 清理暫存輸出（保留最近 14 天）..." -ForegroundColor Yellow
if (Test-Path "output\tmp") {
    $cutoffDate = (Get-Date).AddDays(-14)
    Get-ChildItem -Path "output\tmp" -Recurse -ErrorAction SilentlyContinue | 
        Where-Object { $_.LastWriteTime -lt $cutoffDate } | 
        Remove-Item -Force
    Write-Host "✅ 已清理暫存輸出" -ForegroundColor Green
}

# 8. 完成
Write-Host "`n================================================"
Write-Host "✨ 清理完成！" -ForegroundColor Green
Write-Host "`n📊 建議手動檢查以下項目："
Write-Host "  1. .specstory\history\ - 若不需要歷史快照可刪除"
Write-Host "  2. external_c\, external_f\ - 確認是否為空目錄"
Write-Host "  3. frontend\dist\ - 前端打包產物，可重新建置"
Write-Host "  4. output\images\ - 舊的輸出圖片，可定期清理"
Write-Host "`n🔄 下一步："
Write-Host "  docker-compose down"
Write-Host "  docker-compose up --build -d"
