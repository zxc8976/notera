# VLM 筆記質量檢查腳本
# 用途：檢查視頻處理結果，診斷 VLM 分析失敗的場景

param(
    [Parameter(Mandatory=$false)]
    [string]$VideoName = "test_5min"
)

Write-Host "🔍 檢查 $VideoName 的處理結果..." -ForegroundColor Cyan
Write-Host ""

# 1. 檢查輸出文件
$mdFile = "output\$VideoName.md"
$jsonFile = "output\$VideoName.json"

if (Test-Path $mdFile) {
    $mdSize = (Get-Item $mdFile).Length
    Write-Host "✅ Markdown 文件: $mdFile ($mdSize bytes)" -ForegroundColor Green
} else {
    Write-Host "❌ Markdown 文件不存在: $mdFile" -ForegroundColor Red
    exit 1
}

if (Test-Path $jsonFile) {
    $jsonSize = (Get-Item $jsonFile).Length
    $json = Get-Content $jsonFile | ConvertFrom-Json
    Write-Host "✅ JSON 文件: $jsonFile ($jsonSize bytes)" -ForegroundColor Green
    Write-Host "   - Quality: $($json.quality)" -ForegroundColor Yellow
    Write-Host "   - Is VLM Note: $($json.isVlmNote)" -ForegroundColor Yellow
    Write-Host "   - Use Markdown: $($json.useMarkdown)" -ForegroundColor Yellow
} else {
    Write-Host "❌ JSON 文件不存在: $jsonFile" -ForegroundColor Red
}

Write-Host ""

# 2. 檢查截圖文件
$imageDir = "output\images\$VideoName"
if (Test-Path $imageDir) {
    $images = Get-ChildItem $imageDir -Filter "*.jpg"
    Write-Host "✅ 截圖文件夾: $imageDir ($($images.Count) 張圖片)" -ForegroundColor Green
    foreach ($img in $images) {
        $sizeKB = [math]::Round($img.Length / 1KB, 2)
        Write-Host "   - $($img.Name): $sizeKB KB" -ForegroundColor Gray
    }
} else {
    Write-Host "❌ 截圖文件夾不存在: $imageDir" -ForegroundColor Red
}

Write-Host ""

# 3. 分析 Markdown 內容
Write-Host "📝 分析 Markdown 內容..." -ForegroundColor Cyan
$content = Get-Content $mdFile -Encoding UTF8 -Raw

# 檢查場景數量
$sceneMatches = [regex]::Matches($content, "## 場景 \d+")
Write-Host "   - 場景總數: $($sceneMatches.Count)" -ForegroundColor Yellow

# 檢查降級警告
$warningMatches = [regex]::Matches($content, "⚠️ 自動解析未能擷取可靠的日文重點")
if ($warningMatches.Count -gt 0) {
    Write-Host "   - ⚠️ 發現 $($warningMatches.Count) 個降級場景（VLM 分析失敗）" -ForegroundColor Yellow
    
    # 找出哪些場景降級了
    $lines = $content -split "`n"
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "## 場景 (\d+)") {
            $sceneNum = $matches[1]
            # 檢查接下來的 20 行是否有警告
            $hasWarning = $false
            for ($j = $i; $j -lt [Math]::Min($i + 20, $lines.Count); $j++) {
                if ($lines[$j] -match "⚠️ 自動解析未能擷取") {
                    $hasWarning = $true
                    break
                }
            }
            
            if ($hasWarning) {
                Write-Host "      - 場景 $sceneNum: ❌ VLM 分析失敗（已降級到 OCR）" -ForegroundColor Red
            } else {
                Write-Host "      - 場景 $sceneNum: ✅ VLM 分析成功" -ForegroundColor Green
            }
        }
    }
} else {
    Write-Host "   - ✅ 所有場景 VLM 分析都成功！" -ForegroundColor Green
}

Write-Host ""

# 4. 檢查後端日誌（最近的處理記錄）
Write-Host "📋 檢查後端日誌（最近 20 行相關記錄）..." -ForegroundColor Cyan
docker logs notegen-backend-enhanced 2>&1 | Select-String "$VideoName|場景.*處理|VLM" | Select-Object -Last 20

Write-Host ""
Write-Host "✅ 檢查完成！" -ForegroundColor Green
