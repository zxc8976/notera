#!/usr/bin/env pwsh
# =========================================
# 🗂️ 自動整理專案根目錄腳本
# =========================================
# 功能: 移除測試檔案、整理文檔、清理暫存

Write-Host "🧹 開始整理專案根目錄..." -ForegroundColor Cyan
Write-Host ""

$RootPath = "F:\日本電子\自動筆記駐守2"
$ArchivePath = Join-Path $RootPath "archive"
$BackupPath = Join-Path $RootPath "backup"
$DocsPath = Join-Path $RootPath "docs"

# 統計變數
$DeletedFiles = @()
$MovedFiles = @()
$TotalSpaceSaved = 0

# =========================================
# 1️⃣ 識別並刪除測試檔案
# =========================================
Write-Host "📋 步驟 1: 清理測試檔案..." -ForegroundColor Yellow

$TestFiles = @(
    "test_ocr.py",
    "test_ocr_simple.py", 
    "test_ollama_connection.py",
    "test_video_debug.py",
    "test_download.jpg",
    "test_frontend.jpg",
    "test_new_output_format.md",
    "backend_ocr_cleanup.py",  # 臨時清理腳本
    "check_images.py"          # 臨時檢查腳本
)

foreach ($file in $TestFiles) {
    $FilePath = Join-Path $RootPath $file
    if (Test-Path $FilePath) {
        $FileSize = (Get-Item $FilePath).Length
        $TotalSpaceSaved += $FileSize
        Remove-Item $FilePath -Force
        $DeletedFiles += $file
        Write-Host "  ❌ 已刪除: $file ($(([math]::Round($FileSize/1KB,2))) KB)" -ForegroundColor Red
    }
}

# =========================================
# 2️⃣ 整理文檔到 docs 目錄
# =========================================
Write-Host ""
Write-Host "📋 步驟 2: 整理文檔..." -ForegroundColor Yellow

$DocsToMove = @{
    "ARCHITECTURE.md" = "ARCHITECTURE.md"
    "CONFIGURATION.md" = "CONFIGURATION.md"
    "FILE_INVENTORY.md" = "FILE_INVENTORY.md"
    "MAINTENANCE_REPORT.md" = "MAINTENANCE_REPORT.md"
    "PRESENTATION.md" = "PRESENTATION.md"
    "PROJECT_STRUCTURE.md" = "PROJECT_STRUCTURE.md"
}

foreach ($doc in $DocsToMove.Keys) {
    $SourcePath = Join-Path $RootPath $doc
    $DestPath = Join-Path $DocsPath $DocsToMove[$doc]
    
    if (Test-Path $SourcePath) {
        # 如果目標已存在,先備份
        if (Test-Path $DestPath) {
            $BackupFile = Join-Path $BackupPath "old_$(Get-Date -Format 'yyyyMMdd')_$doc"
            Move-Item $DestPath $BackupFile -Force
            Write-Host "  💾 備份舊檔: $doc" -ForegroundColor DarkYellow
        }
        
        Move-Item $SourcePath $DestPath -Force
        $MovedFiles += "$doc → docs/$doc"
        Write-Host "  📁 已移動: $doc → docs/" -ForegroundColor Green
    }
}

# =========================================
# 3️⃣ 清理 Python 快取
# =========================================
Write-Host ""
Write-Host "📋 步驟 3: 清理 Python 快取..." -ForegroundColor Yellow

$PycacheCount = 0
Get-ChildItem -Path $RootPath -Recurse -Directory -Filter "__pycache__" | ForEach-Object {
    $CacheSize = (Get-ChildItem $_.FullName -Recurse | Measure-Object -Property Length -Sum).Sum
    $TotalSpaceSaved += $CacheSize
    Remove-Item $_.FullName -Recurse -Force
    $PycacheCount++
}
Write-Host "  🗑️ 已清理 $PycacheCount 個 __pycache__ 目錄" -ForegroundColor Green

# =========================================
# 4️⃣ 清理臨時輸出
# =========================================
Write-Host ""
Write-Host "📋 步驟 4: 清理臨時輸出..." -ForegroundColor Yellow

$TmpPath = Join-Path $RootPath "output\tmp"
if (Test-Path $TmpPath) {
    $TmpFiles = Get-ChildItem $TmpPath -File
    $TmpSize = ($TmpFiles | Measure-Object -Property Length -Sum).Sum
    $TotalSpaceSaved += $TmpSize
    $TmpFiles | Remove-Item -Force
    Write-Host "  🗑️ 已清理 $($TmpFiles.Count) 個臨時檔案 ($(([math]::Round($TmpSize/1MB,2))) MB)" -ForegroundColor Green
}

# =========================================
# 5️⃣ 清理舊日誌
# =========================================
Write-Host ""
Write-Host "📋 步驟 5: 清理舊日誌 (>7天)..." -ForegroundColor Yellow

$LogPath = Join-Path $RootPath "logs"
$OldLogs = Get-ChildItem $LogPath -File -Recurse | Where-Object { 
    $_.LastWriteTime -lt (Get-Date).AddDays(-7) -and $_.Name -ne "notegen.log"
}

$LogSize = 0
foreach ($log in $OldLogs) {
    $LogSize += $log.Length
    Remove-Item $log.FullName -Force
}
$TotalSpaceSaved += $LogSize
Write-Host "  🗑️ 已清理 $($OldLogs.Count) 個舊日誌檔 ($(([math]::Round($LogSize/1MB,2))) MB)" -ForegroundColor Green

# =========================================
# 6️⃣ 創建目錄說明
# =========================================
Write-Host ""
Write-Host "📋 步驟 6: 創建目錄說明..." -ForegroundColor Yellow

$DirectoryDescriptions = @{
    "archive" = "歷史檔案與舊版本備份"
    "backup" = "重要資料備份"
    "docker" = "Docker 容器配置"
    "docs" = "專案文檔與說明"
    "external_c" = "C 槽外部資料掛載點"
    "external_f" = "F 槽外部資料掛載點 (講義圖片、影片)"
    "frontend" = "Vue 3 前端應用程式"
    "images" = "處理用的圖片檔案"
    "logs" = "系統日誌與追蹤資料"
    "models" = "AI 模型檔案 (Whisper 等)"
    "modules" = "後端核心模組 (OCR、LLM、筆記生成)"
    "ollama_models" = "Ollama LLM 模型儲存"
    "output" = "筆記輸出目錄 (notes/, images/, docs/, tmp/)"
    "saved_notes" = "使用者儲存的筆記"
    "scripts" = "維運與開發腳本"
    "tests" = "單元測試與整合測試"
    "videos" = "影片來源檔案"
    "筆記分析" = "筆記分析工具與文檔"
}

foreach ($dir in $DirectoryDescriptions.Keys) {
    $DirPath = Join-Path $RootPath $dir
    if (Test-Path $DirPath) {
        $ReadmePath = Join-Path $DirPath "README.txt"
        $DirectoryDescriptions[$dir] | Out-File -FilePath $ReadmePath -Encoding UTF8 -Force
    }
}
Write-Host "  📝 已創建 $($DirectoryDescriptions.Count) 個目錄說明" -ForegroundColor Green

# =========================================
# 7️⃣ 創建根目錄 README
# =========================================
Write-Host ""
Write-Host "📋 步驟 7: 更新根目錄結構說明..." -ForegroundColor Yellow

$RootReadme = @"
# 📁 專案根目錄結構

## 🎯 核心檔案
- **config.yaml**: 系統主配置檔 (LLM、OCR、GPU 設定)
- **main.py**: 後端主程式入口
- **docker-compose.yml**: Docker 容器編排
- **requirements.txt**: Python 依賴套件

## 📂 重要目錄
| 目錄 | 說明 | 大小 |
|------|------|------|
| **frontend/** | Vue 3 前端應用 | ~270 MB |
| **modules/** | 後端核心模組 | ~500 KB |
| **models/** | AI 模型 (Whisper) | ~4.3 GB |
| **ollama_models/** | Ollama LLM 模型 | ~10 GB |
| **saved_notes/** | 生成的筆記輸出 | 動態 |
| **docs/** | 完整文檔 | ~500 KB |
| **scripts/** | 維運腳本 | ~100 KB |

## 📚 文檔指南
- **QUICK_REFERENCE.md**: 快速參考手冊 (命令速查)
- **README.md**: 專案介紹
- **docs/PROJECT_STRUCTURE.md**: 完整結構說明
- **docs/TROUBLESHOOTING.md**: 故障排除

## 🚀 快速啟動
``````powershell
# 啟動所有服務
docker-compose up -d

# 查看狀態
docker ps

# 查看日誌
docker-compose logs -f
``````

## 🧹 維護命令
``````powershell
# 清理測試檔案
.\scripts\cleanup.ps1

# 整理根目錄
.\scripts\organize_root.ps1

# 備份筆記
Copy-Item -Recurse saved_notes "backup/notes_`$(Get-Date -Format 'yyyyMMdd')"
``````

## 🔗 訪問地址
- 前端: http://localhost:5173
- 後端 API: http://localhost:18000
- API 文檔: http://localhost:18000/docs
- Ollama: http://localhost:11434

---
最後更新: $(Get-Date -Format 'yyyy-MM-dd')
"@

$RootReadme | Out-File -FilePath (Join-Path $RootPath "DIRECTORY_GUIDE.md") -Encoding UTF8 -Force
Write-Host "  📝 已創建 DIRECTORY_GUIDE.md" -ForegroundColor Green

# =========================================
# 📊 總結報告
# =========================================
Write-Host ""
Write-Host "=" * 50 -ForegroundColor Cyan
Write-Host "✅ 整理完成!" -ForegroundColor Green
Write-Host "=" * 50 -ForegroundColor Cyan
Write-Host ""

Write-Host "📊 統計資訊:" -ForegroundColor Yellow
Write-Host "  🗑️ 已刪除檔案: $($DeletedFiles.Count) 個"
Write-Host "  📁 已移動檔案: $($MovedFiles.Count) 個"
Write-Host "  💾 節省空間: $(([math]::Round($TotalSpaceSaved/1MB,2))) MB"
Write-Host ""

if ($DeletedFiles.Count -gt 0) {
    Write-Host "已刪除的檔案:" -ForegroundColor Red
    $DeletedFiles | ForEach-Object { Write-Host "  - $_" }
    Write-Host ""
}

if ($MovedFiles.Count -gt 0) {
    Write-Host "已移動的檔案:" -ForegroundColor Green
    $MovedFiles | ForEach-Object { Write-Host "  - $_" }
    Write-Host ""
}

Write-Host "🎉 根目錄現在更整潔了!" -ForegroundColor Cyan
Write-Host ""
Write-Host "下一步建議:" -ForegroundColor Yellow
Write-Host "  1. 查看 DIRECTORY_GUIDE.md 了解目錄結構"
Write-Host "  2. 查看 QUICK_REFERENCE.md 學習常用命令"
Write-Host "  3. 執行 'docker-compose up -d' 啟動服務"
Write-Host ""
