# 影片處理狀態診斷腳本

Write-Host "`n=== 🎬 影片處理狀態診斷 ===" -ForegroundColor Cyan
Write-Host ""

$videoFile = "Meet - cuq-nvaz-ryv - Google Chrome 2024-12-11 09-17-02.mp4"
$encodedFile = [System.Web.HttpUtility]::UrlEncode($videoFile)

# 1. 檢查後端狀態
Write-Host "1️⃣ 檢查後端處理狀態..." -ForegroundColor Yellow
try {
    $status = Invoke-WebRequest -Uri "http://localhost:18000/api/status/$encodedFile" | 
              Select-Object -ExpandProperty Content | 
              ConvertFrom-Json
    
    Write-Host "   狀態碼: " -NoNewline -ForegroundColor White
    Write-Host $status.status_code -ForegroundColor $(if ($status.status_code -eq 'completed') { 'Green' } else { 'Red' })
    
    Write-Host "   狀態文字: " -NoNewline -ForegroundColor White
    Write-Host $status.status -ForegroundColor Cyan
    
    Write-Host "   進度: " -NoNewline -ForegroundColor White
    Write-Host "$($status.progress)%" -ForegroundColor Green
    
    Write-Host "   結果路徑: " -NoNewline -ForegroundColor White
    Write-Host $status.result_path -ForegroundColor Green
    
    if ($status.status_code -eq 'completed') {
        Write-Host "`n   ✅ 影片處理已完成！" -ForegroundColor Green
    } else {
        Write-Host "`n   ⏳ 影片還在處理中..." -ForegroundColor Yellow
    }
} catch {
    Write-Host "   ❌ 無法獲取狀態: $_" -ForegroundColor Red
}

# 2. 檢查輸出檔案
Write-Host "`n2️⃣ 檢查輸出檔案..." -ForegroundColor Yellow
$mdFile = "output\Meet - cuq-nvaz-ryv - Google Chrome 2024-12-11 09-17-02.md"
$jsonFile = "output\Meet - cuq-nvaz-ryv - Google Chrome 2024-12-11 09-17-02.json"

if (Test-Path $mdFile) {
    $mdSize = (Get-Item $mdFile).Length
    Write-Host "   ✅ MD 檔案存在: $mdSize bytes" -ForegroundColor Green
} else {
    Write-Host "   ❌ MD 檔案不存在" -ForegroundColor Red
}

if (Test-Path $jsonFile) {
    $jsonSize = (Get-Item $jsonFile).Length
    Write-Host "   ✅ JSON 檔案存在: $jsonSize bytes" -ForegroundColor Green
} else {
    Write-Host "   ⚠️ JSON 檔案不存在" -ForegroundColor Yellow
}

# 3. 檢查容器狀態
Write-Host "`n3️⃣ 檢查 Docker 容器狀態..." -ForegroundColor Yellow
$containers = docker ps --format "table {{.Names}}\t{{.Status}}" | Select-String "notegen"
$containers | ForEach-Object {
    if ($_ -match "Up") {
        Write-Host "   ✅ $_" -ForegroundColor Green
    } else {
        Write-Host "   ❌ $_" -ForegroundColor Red
    }
}

# 4. 檢查前端連接
Write-Host "`n4️⃣ 檢查前端連接..." -ForegroundColor Yellow
try {
    $frontend = Invoke-WebRequest -Uri "http://localhost:5173" -TimeoutSec 3 -UseBasicParsing
    Write-Host "   ✅ 前端正常運行 (http://localhost:5173)" -ForegroundColor Green
} catch {
    Write-Host "   ❌ 前端無法訪問" -ForegroundColor Red
}

# 5. 測試建議
Write-Host "`n5️⃣ 測試建議:" -ForegroundColor Yellow
if ($status.status_code -eq 'completed') {
    Write-Host "   1. 在瀏覽器刷新頁面 (F5)" -ForegroundColor Cyan
    Write-Host "   2. 點擊影片名稱載入結果" -ForegroundColor Cyan
    Write-Host "   3. 查看 Console 日誌: 📊 [pollStatus]" -ForegroundColor Cyan
} else {
    Write-Host "   1. 重新處理影片" -ForegroundColor Cyan
    Write-Host "   2. 查看後端日誌: docker logs notegen-backend-enhanced --tail 50" -ForegroundColor Cyan
}

Write-Host "`n" -NoNewline
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""
