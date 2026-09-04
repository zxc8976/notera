# 專案清理腳本
# 用途: 清理測試文件和Docker快取
# 版本: v1.0
# 日期: 2025-10-04

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  自動筆記系統 - 檔案清理腳本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 設定專案根目錄
$ProjectRoot = "F:\日本電子\自動筆記駐守2"
Set-Location $ProjectRoot

# ============================================
# 1. 檢查舊的JSON文件 (VLM-First架構不需要)
# ============================================
Write-Host "[1/6] 檢查output目錄中的JSON文件..." -ForegroundColor Yellow
$jsonFiles = Get-ChildItem -Path "output" -Filter "*.json" -Recurse
if ($jsonFiles.Count -gt 0) {
    Write-Host "  發現 $($jsonFiles.Count) 個JSON文件:" -ForegroundColor White
    $jsonFiles | ForEach-Object {
        $sizeKB = [math]::Round($_.Length/1KB, 2)
        Write-Host "    - $($_.Name) ($sizeKB KB, $($_.LastWriteTime))" -ForegroundColor Gray
    }
    
    $answer = Read-Host "  是否刪除這些JSON文件? (y/N)"
    if ($answer -eq 'y' -or $answer -eq 'Y') {
        $jsonFiles | Remove-Item -Force
        Write-Host "  ✅ 已刪除 $($jsonFiles.Count) 個JSON文件" -ForegroundColor Green
    } else {
        Write-Host "  ⏭️  跳過JSON文件清理" -ForegroundColor Gray
    }
} else {
    Write-Host "  ✅ 沒有找到JSON文件" -ForegroundColor Green
}
Write-Host ""

# ============================================
# 2. 檢查舊的場景圖片目錄
# ============================================
Write-Host "[2/6] 檢查output/images目錄..." -ForegroundColor Yellow
$imagesDirs = Get-ChildItem -Path "output\images" -Directory -ErrorAction SilentlyContinue
if ($imagesDirs) {
    Write-Host "  發現 $($imagesDirs.Count) 個視頻圖片目錄:" -ForegroundColor White
    $imagesDirs | ForEach-Object {
        $fileCount = (Get-ChildItem $_.FullName -File).Count
        Write-Host "    - $($_.Name) ($fileCount 個場景圖片)" -ForegroundColor Gray
    }
    
    Write-Host "  💡 提示: 如果需要清理舊測試視頻的圖片,請手動刪除對應目錄" -ForegroundColor Cyan
    Write-Host "  例如: Remove-Item 'output\images\舊視頻名' -Recurse -Force" -ForegroundColor Gray
} else {
    Write-Host "  ✅ output/images 目錄為空或不存在" -ForegroundColor Green
}
Write-Host ""

# ============================================
# 3. 清理Python快取文件
# ============================================
Write-Host "[3/6] 檢查Python快取文件..." -ForegroundColor Yellow
$pycacheCount = (Get-ChildItem -Path "." -Filter "__pycache__" -Recurse -Directory -ErrorAction SilentlyContinue).Count
$pycFiles = Get-ChildItem -Path "." -Filter "*.pyc" -Recurse -File -ErrorAction SilentlyContinue
if ($pycacheCount -gt 0 -or $pycFiles.Count -gt 0) {
    Write-Host "  發現 $pycacheCount 個 __pycache__ 目錄和 $($pycFiles.Count) 個 .pyc 文件" -ForegroundColor White
    
    $answer = Read-Host "  是否清理Python快取? (y/N) [建議保留以加速啟動]"
    if ($answer -eq 'y' -or $answer -eq 'Y') {
        Get-ChildItem -Path "." -Filter "__pycache__" -Recurse -Directory | Remove-Item -Recurse -Force
        Get-ChildItem -Path "." -Filter "*.pyc" -Recurse -File | Remove-Item -Force
        Write-Host "  ✅ 已清理Python快取" -ForegroundColor Green
    } else {
        Write-Host "  ⏭️  保留Python快取" -ForegroundColor Gray
    }
} else {
    Write-Host "  ✅ 沒有Python快取文件" -ForegroundColor Green
}
Write-Host ""

# ============================================
# 4. 檢查Docker Build Cache
# ============================================
Write-Host "[4/6] 檢查Docker Build Cache..." -ForegroundColor Yellow
try {
    $dockerDf = docker system df --format "{{.Type}},{{.TotalCount}},{{.Size}},{{.Reclaimable}}" | ConvertFrom-Csv -Header Type,Total,Size,Reclaimable
    $buildCache = $dockerDf | Where-Object { $_.Type -eq "Build Cache" }
    
    if ($buildCache) {
        Write-Host "  Build Cache: $($buildCache.Size) (可回收: $($buildCache.Reclaimable))" -ForegroundColor White
        
        $answer = Read-Host "  是否清理Docker Build Cache? (y/N)"
        if ($answer -eq 'y' -or $answer -eq 'Y') {
            Write-Host "  🧹 正在清理..." -ForegroundColor Yellow
            docker builder prune -a -f | Out-Null
            Write-Host "  ✅ Build Cache已清理" -ForegroundColor Green
        } else {
            Write-Host "  ⏭️  跳過Build Cache清理" -ForegroundColor Gray
        }
    }
} catch {
    Write-Host "  ⚠️  無法查詢Docker狀態 (Docker可能未運行)" -ForegroundColor Yellow
}
Write-Host ""

# ============================================
# 5. 檢查未使用的Docker映像
# ============================================
Write-Host "[5/6] 檢查未使用的Docker映像..." -ForegroundColor Yellow
try {
    $dockerDf = docker system df --format "{{.Type}},{{.TotalCount}},{{.Size}},{{.Reclaimable}}" | ConvertFrom-Csv -Header Type,Total,Size,Reclaimable
    $images = $dockerDf | Where-Object { $_.Type -eq "Images" }
    
    if ($images) {
        Write-Host "  映像檔: $($images.Size) (可回收: $($images.Reclaimable))" -ForegroundColor White
        
        $answer = Read-Host "  是否清理未使用的映像? (y/N) [會刪除未使用的映像]"
        if ($answer -eq 'y' -or $answer -eq 'Y') {
            Write-Host "  🧹 正在清理..." -ForegroundColor Yellow
            docker image prune -a -f | Out-Null
            Write-Host "  ✅ 未使用的映像已清理" -ForegroundColor Green
        } else {
            Write-Host "  ⏭️  跳過映像清理" -ForegroundColor Gray
        }
    }
} catch {
    Write-Host "  ⚠️  無法查詢Docker狀態" -ForegroundColor Yellow
}
Write-Host ""

# ============================================
# 6. 檢查未使用的Docker卷
# ============================================
Write-Host "[6/6] 檢查未使用的Docker卷..." -ForegroundColor Yellow
try {
    $dockerDf = docker system df --format "{{.Type}},{{.TotalCount}},{{.Size}},{{.Reclaimable}}" | ConvertFrom-Csv -Header Type,Total,Size,Reclaimable
    $volumes = $dockerDf | Where-Object { $_.Type -eq "Local Volumes" }
    
    if ($volumes) {
        Write-Host "  卷: $($volumes.Size) (可回收: $($volumes.Reclaimable))" -ForegroundColor White
        
        $answer = Read-Host "  是否清理未使用的卷? (y/N) [會刪除未使用的資料卷]"
        if ($answer -eq 'y' -or $answer -eq 'Y') {
            Write-Host "  🧹 正在清理..." -ForegroundColor Yellow
            docker volume prune -f | Out-Null
            Write-Host "  ✅ 未使用的卷已清理" -ForegroundColor Green
        } else {
            Write-Host "  ⏭️  跳過卷清理" -ForegroundColor Gray
        }
    }
} catch {
    Write-Host "  ⚠️  無法查詢Docker狀態" -ForegroundColor Yellow
}
Write-Host ""

# ============================================
# 總結
# ============================================
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  清理完成!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "💡 建議:" -ForegroundColor Cyan
Write-Host "  1. 執行回歸測試驗證功能正常" -ForegroundColor White
Write-Host "  2. 檢查 docs/CLEANUP_STATUS_REPORT.md 了解詳細狀態" -ForegroundColor White
Write-Host "  3. 定期執行此腳本保持專案整潔" -ForegroundColor White
Write-Host ""

# 顯示最終磁碟使用狀態
Write-Host "📊 當前Docker資源使用狀態:" -ForegroundColor Cyan
try {
    docker system df
} catch {
    Write-Host "  無法查詢Docker狀態" -ForegroundColor Yellow
}
