# 🧹 專案清理腳本
# 用途: 清理測試檔案、臨時資料、舊日誌
# 執行: .\scripts\cleanup.ps1

Write-Host "🧹 開始清理專案..." -ForegroundColor Cyan

# 1. 清理根目錄測試檔案
Write-Host "`n📝 清理測試檔案..." -ForegroundColor Yellow
$testFiles = @(
    "test_ocr.py",
    "test_ocr_simple.py",
    "test_ollama_connection.py",
    "test_video_debug.py",
    "test_download.jpg",
    "test_frontend.jpg",
    "test_new_output_format.md"
)

$removedCount = 0
foreach ($file in $testFiles) {
    if (Test-Path $file) {
        Remove-Item $file -Force
        Write-Host "  ✅ 已刪除: $file" -ForegroundColor Green
        $removedCount++
    }
}
Write-Host "  📊 共刪除 $removedCount 個測試檔案" -ForegroundColor Cyan

# 2. 清理 Python 快取
Write-Host "`n🐍 清理 Python 快取..." -ForegroundColor Yellow
$pycacheCount = 0
Get-ChildItem -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item $_.FullName -Recurse -Force
    $pycacheCount++
}
Write-Host "  📊 共刪除 $pycacheCount 個 __pycache__ 目錄" -ForegroundColor Cyan

# 3. 清理臨時檔案
Write-Host "`n📁 清理臨時檔案..." -ForegroundColor Yellow
$tmpCount = 0
if (Test-Path "var/output/tmp") {
    $tmpFiles = Get-ChildItem "var/output/tmp" -ErrorAction SilentlyContinue
    $tmpCount = $tmpFiles.Count
    Remove-Item "var/output/tmp/*" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  📊 共刪除 $tmpCount 個臨時檔案" -ForegroundColor Cyan
}
$tmpRootCount = 0
if (Test-Path "var/tmp") {
    $tmpRoot = Get-ChildItem "var/tmp" -ErrorAction SilentlyContinue
    $tmpRootCount = $tmpRoot.Count
    Remove-Item "var/tmp/*" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  📊 共刪除 $tmpRootCount 個 var/tmp 內容" -ForegroundColor Cyan
}

# 3.5 清理已棄用的 vLLM / Qwen3 模型資料
Write-Host "`n🗑️ 清理已棄用的模型資源..." -ForegroundColor Yellow
$legacyPaths = @(
    "data/models/vllm",
    "data/models/ollama/qwen3vl-4b",
    "data/models/ollama/qwen3-vl-4b-instruct-fp8",
    "data/models/ollama/qwen3-vl-4b",
    "data/models/ollama/qwen3-vl-8b-awq"
)
$legacyRemoved = 0
foreach ($legacy in $legacyPaths) {
    if (Test-Path $legacy) {
        Remove-Item $legacy -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "  ✅ 已刪除: $legacy" -ForegroundColor Green
        $legacyRemoved++
    }
}
if ($legacyRemoved -eq 0) {
    Write-Host "  ⏭️  沒有找到需清理的舊模型資料" -ForegroundColor Gray
}

# 額外檢查舊容器/卷
Write-Host "`n🔍 檢查是否仍有 vLLM 相關容器或卷..." -ForegroundColor Yellow
try {
    $legacyContainers = docker ps -a --format "{{.Names}}" | Where-Object { $_ -like "*vllm*" }
    if ($legacyContainers) {
        Write-Host "  ⚠️ 發現下列容器：" -ForegroundColor Yellow
        $legacyContainers | ForEach-Object { Write-Host "    - $_" -ForegroundColor White }
        Write-Host "  👉 建議執行: docker rm -f $($legacyContainers -join ' ')" -ForegroundColor Cyan
    } else {
        Write-Host "  ✅ 沒有 vLLM 相關容器" -ForegroundColor Green
    }

    $legacyVolumes = docker volume ls --format "{{.Name}}" | Where-Object { $_ -like "*vllm*" }
    if ($legacyVolumes) {
        Write-Host "  ⚠️ 發現下列卷：" -ForegroundColor Yellow
        $legacyVolumes | ForEach-Object { Write-Host "    - $_" -ForegroundColor White }
        Write-Host "  👉 建議執行: docker volume rm $($legacyVolumes -join ' ')" -ForegroundColor Cyan
    } else {
        Write-Host "  ✅ 沒有 vLLM 相關卷" -ForegroundColor Green
    }
} catch {
    Write-Host "  ⏭️  無法列出 Docker 資源，請確認已安裝 Docker CLI" -ForegroundColor Gray
}

# 4. 清理舊日誌 (保留7天)
Write-Host "`n📜 清理舊日誌 (保留最近7天)..." -ForegroundColor Yellow
$cutoffDate = (Get-Date).AddDays(-7)
$oldLogsCount = 0

if (Test-Path "var/log") {
    Get-ChildItem "var/log" -Filter "*.log" -ErrorAction SilentlyContinue | Where-Object {
        $_.LastWriteTime -lt $cutoffDate
    } | ForEach-Object {
        Remove-Item $_.FullName -Force
        Write-Host "  ✅ 已刪除: $($_.Name)" -ForegroundColor Green
        $oldLogsCount++
    }
}
Write-Host "  📊 共刪除 $oldLogsCount 個舊日誌" -ForegroundColor Cyan

# 5. 清理 Docker 相關 (選擇性)
Write-Host "`n🐳 Docker 資源清理..." -ForegroundColor Yellow
Write-Host "  ⚠️  是否清理未使用的 Docker 資源? (y/N): " -ForegroundColor Yellow -NoNewline
$response = Read-Host

if ($response -eq 'y' -or $response -eq 'Y') {
    Write-Host "  🧹 執行 docker system prune..." -ForegroundColor Cyan
    docker system prune -f
    Write-Host "  ✅ Docker 清理完成" -ForegroundColor Green
} else {
    Write-Host "  ⏭️  跳過 Docker 清理" -ForegroundColor Gray
}

# 6. 統計磁碟空間
Write-Host "`n💾 磁碟空間統計..." -ForegroundColor Yellow

function Get-FolderSize {
    param([string]$Path)
    if (Test-Path $Path) {
        $size = (Get-ChildItem $Path -Recurse -ErrorAction SilentlyContinue | 
                 Measure-Object -Property Length -Sum -ErrorAction SilentlyContinue).Sum
        if ($size) {
            return [math]::Round($size / 1MB, 2)
        }
    }
    return 0
}

$folders = @{
    "var/notes"    = "var/notes"
    "var/output"   = "var/output"
    "var/log"      = "var/log"
    "data/models"  = "data/models"
    "data/external" = "data/external"
}

Write-Host "`n  📊 主要目錄大小:" -ForegroundColor Cyan
foreach ($key in $folders.Keys) {
    $path = $folders[$key]
    $sizeMB = Get-FolderSize $path
    Write-Host "    $key : $sizeMB MB" -ForegroundColor White
}

# 7. 完成報告
Write-Host "`n✅ 清理完成!" -ForegroundColor Green
Write-Host "`n📋 清理摘要:" -ForegroundColor Cyan
Write-Host "  - 測試檔案: $removedCount 個" -ForegroundColor White
Write-Host "  - Python 快取: $pycacheCount 個目錄" -ForegroundColor White
Write-Host "  - 臨時檔案: $($tmpCount + $tmpRootCount) 個" -ForegroundColor White
Write-Host "  - 舊日誌: $oldLogsCount 個" -ForegroundColor White
Write-Host "  - 清除舊模型目錄: $legacyRemoved 個" -ForegroundColor White

Write-Host "`n💡 提示:" -ForegroundColor Yellow
Write-Host "  - 定期執行此腳本可保持專案整潔" -ForegroundColor Gray
Write-Host "  - 重要資料請先備份: var/notes/, source/backend/app/config.yaml" -ForegroundColor Gray
Write-Host "  - 查看專案結構: cat PROJECT_STRUCTURE.md" -ForegroundColor Gray

Write-Host "`n🎉 All done!" -ForegroundColor Green
