# =====================================
# 自動化 API 測試腳本
# 測試長影片處理功能
# =====================================

$ErrorActionPreference = "Continue"
$API_BASE = "http://localhost:18000"
$VIDEO_FILE = "2025-09-29 13-31-03.mp4"

Write-Host "`n🚀 ===== 自動化測試開始 =====" -ForegroundColor Cyan
Write-Host "測試時間: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray

# =====================================
# 1. 檢查服務器狀態
# =====================================
Write-Host "`n📡 [步驟 1/5] 檢查服務器狀態..." -ForegroundColor Yellow

try {
    $version = Invoke-RestMethod -Uri "$API_BASE/api/version" -Method GET -TimeoutSec 5
    Write-Host "✅ 後端服務器正常運行" -ForegroundColor Green
    Write-Host "   版本: $($version.version)" -ForegroundColor Gray
} catch {
    Write-Host "❌ 後端服務器無法連接！" -ForegroundColor Red
    Write-Host "   錯誤: $_" -ForegroundColor Red
    exit 1
}

# =====================================
# 2. 檢查影片是否存在
# =====================================
Write-Host "`n📹 [步驟 2/5] 檢查影片文件..." -ForegroundColor Yellow

try {
    $files = Invoke-RestMethod -Uri "$API_BASE/api/files" -Method GET -TimeoutSec 10
    $targetFile = $files | Where-Object { $_.name -eq $VIDEO_FILE }
    
    if ($targetFile) {
        Write-Host "✅ 找到影片: $VIDEO_FILE" -ForegroundColor Green
        Write-Host "   大小: $([math]::Round($targetFile.size / 1MB, 2)) MB" -ForegroundColor Gray
    } else {
        Write-Host "⚠️  影片不存在,請先上傳: $VIDEO_FILE" -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "❌ 無法獲取文件列表！" -ForegroundColor Red
    Write-Host "   錯誤: $_" -ForegroundColor Red
    exit 1
}

# =====================================
# 3. 開始處理影片
# =====================================
Write-Host "`n🎬 [步驟 3/5] 開始處理影片..." -ForegroundColor Yellow

try {
    $body = @{
        filename = $VIDEO_FILE
        language = "zh-TW"
        include_japanese = $true
    } | ConvertTo-Json
    
    $headers = @{
        "Content-Type" = "application/json"
    }
    
    $response = Invoke-RestMethod -Uri "$API_BASE/api/summarize" -Method POST -Body $body -Headers $headers -TimeoutSec 10
    Write-Host "✅ 處理請求已發送" -ForegroundColor Green
    Write-Host "   狀態: $($response.status)" -ForegroundColor Gray
} catch {
    Write-Host "❌ 處理請求失敗！" -ForegroundColor Red
    Write-Host "   錯誤: $_" -ForegroundColor Red
    exit 1
}

# =====================================
# 4. 監控處理進度
# =====================================
Write-Host "`n⏳ [步驟 4/5] 監控處理進度..." -ForegroundColor Yellow
Write-Host "   (這可能需要幾分鐘...)" -ForegroundColor Gray

$maxWaitSeconds = 600  # 最多等待 10 分鐘
$startTime = Get-Date
$lastProgress = -1

while ($true) {
    Start-Sleep -Seconds 5
    
    try {
        $encodedFilename = [System.Web.HttpUtility]::UrlEncode($VIDEO_FILE)
        $status = Invoke-RestMethod -Uri "$API_BASE/api/status/$encodedFilename" -Method GET -TimeoutSec 5
        
        # 只在進度變化時顯示
        if ($status.progress -ne $lastProgress) {
            $elapsed = ((Get-Date) - $startTime).TotalSeconds
            Write-Host "   進度: $($status.progress)% - $($status.detail) (已耗時: $([math]::Round($elapsed))秒)" -ForegroundColor Cyan
            $lastProgress = $status.progress
        }
        
        # 檢查是否完成
        if ($status.status_code -eq "completed") {
            Write-Host "✅ 處理完成！" -ForegroundColor Green
            break
        }
        
        # 檢查是否錯誤
        if ($status.status_code -eq "error") {
            Write-Host "❌ 處理失敗: $($status.detail)" -ForegroundColor Red
            exit 1
        }
        
        # 檢查是否超時
        $elapsed = ((Get-Date) - $startTime).TotalSeconds
        if ($elapsed -gt $maxWaitSeconds) {
            Write-Host "⏰ 處理超時 (超過 $maxWaitSeconds 秒)" -ForegroundColor Red
            exit 1
        }
        
    } catch {
        Write-Host "⚠️  無法獲取狀態,繼續等待..." -ForegroundColor Yellow
    }
}

# =====================================
# 5. 獲取並驗證結果
# =====================================
Write-Host "`n📄 [步驟 5/5] 獲取並驗證結果..." -ForegroundColor Yellow

try {
    $encodedFilename = [System.Web.HttpUtility]::UrlEncode($VIDEO_FILE)
    $result = Invoke-RestMethod -Uri "$API_BASE/api/result/$encodedFilename" -Method GET -TimeoutSec 10
    
    Write-Host "✅ 成功獲取結果" -ForegroundColor Green
    
    # 解析 JSON 結構
    if ($result.structured) {
        $structured = $result.structured
        
        Write-Host "`n📊 ===== 測試驗證結果 =====" -ForegroundColor Cyan
        
        # 驗證 1: 檢查場景數量
        $sceneCount = $structured.notes.Count
        Write-Host "`n1️⃣  場景數量:" -ForegroundColor Yellow
        Write-Host "   共 $sceneCount 個場景" -ForegroundColor Gray
        
        if ($sceneCount -gt 0) {
            Write-Host "   ✅ PASS" -ForegroundColor Green
        } else {
            Write-Host "   ❌ FAIL - 沒有場景內容" -ForegroundColor Red
        }
        
        # 驗證 2: 檢查核心內容列表
        Write-Host "`n2️⃣  核心內容列表格式 (場景 1-3):" -ForegroundColor Yellow
        $hasListFormat = $true
        
        for ($i = 0; $i -lt [math]::Min(3, $sceneCount); $i++) {
            $scene = $structured.notes[$i]
            $content = $scene.content
            
            # 檢查是否有列表格式 (- 或 • 開頭的行)
            $hasListItems = $content -match '^\s*[-•]' -or $content -match '\n\s*[-•]'
            
            Write-Host "   場景 $($i+1): " -NoNewline
            if ($hasListItems) {
                Write-Host "✅ 有列表格式" -ForegroundColor Green
            } else {
                Write-Host "❌ 缺少列表格式" -ForegroundColor Red
                $hasListFormat = $false
            }
        }
        
        if ($hasListFormat) {
            Write-Host "`n   ✅ PASS - 所有場景都有列表格式" -ForegroundColor Green
        } else {
            Write-Host "`n   ❌ FAIL - 部分場景缺少列表格式" -ForegroundColor Red
        }
        
        # 驗證 3: 檢查日文原文
        Write-Host "`n3️⃣  日文原文保留 (場景 1-3):" -ForegroundColor Yellow
        $hasJapanese = $true
        
        for ($i = 0; $i -lt [math]::Min(3, $sceneCount); $i++) {
            $scene = $structured.notes[$i]
            
            # 檢查主題是否包含日文(平假名/片假名/漢字)
            $topicHasJapanese = $scene.topic -match '[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]'
            
            # 檢查內容是否包含日文
            $contentHasJapanese = $scene.content -match '[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]'
            
            Write-Host "   場景 $($i+1): " -NoNewline
            if ($topicHasJapanese -and $contentHasJapanese) {
                Write-Host "✅ 包含日文原文" -ForegroundColor Green
            } else {
                Write-Host "❌ 缺少日文原文 (主題:$topicHasJapanese, 內容:$contentHasJapanese)" -ForegroundColor Red
                $hasJapanese = $false
            }
        }
        
        if ($hasJapanese) {
            Write-Host "`n   ✅ PASS - 所有場景都保留日文原文" -ForegroundColor Green
        } else {
            Write-Host "`n   ❌ FAIL - 部分場景缺少日文原文" -ForegroundColor Red
        }
        
        # 驗證 4: 檢查詞彙表質量
        Write-Host "`n4️⃣  詞彙表質量:" -ForegroundColor Yellow
        $vocabCount = $structured.terms.Count
        Write-Host "   共 $vocabCount 個詞彙" -ForegroundColor Gray
        
        # 檢查是否有單字詞
        $singleCharTerms = $structured.terms | Where-Object { $_.japanese.Length -eq 1 }
        $singleCharCount = ($singleCharTerms | Measure-Object).Count
        
        Write-Host "   單字詞數量: $singleCharCount" -ForegroundColor Gray
        
        if ($singleCharCount -eq 0) {
            Write-Host "   ✅ PASS - 無單字詞" -ForegroundColor Green
        } else {
            Write-Host "   ⚠️  WARNING - 發現 $singleCharCount 個單字詞" -ForegroundColor Yellow
            $singleCharTerms | ForEach-Object {
                Write-Host "     - $($_.japanese) ($($_.chinese))" -ForegroundColor Gray
            }
        }
        
        # 驗證 5: OCR 信心度
        Write-Host "`n5️⃣  OCR 品質:" -ForegroundColor Yellow
        $ocrConfidence = $structured.ocrConfidence
        Write-Host "   OCR 信心度: $ocrConfidence" -ForegroundColor Gray
        
        if ($ocrConfidence -gt 0.5) {
            Write-Host "   ✅ PASS - OCR 品質良好" -ForegroundColor Green
        } elseif ($ocrConfidence -gt 0) {
            Write-Host "   ⚠️  WARNING - OCR 品質一般" -ForegroundColor Yellow
        } else {
            Write-Host "   ❌ FAIL - OCR 失敗" -ForegroundColor Red
        }
        
        # 保存完整結果到文件
        $outputPath = "test-results-$(Get-Date -Format 'yyyyMMdd-HHmmss').json"
        $result | ConvertTo-Json -Depth 10 | Out-File -FilePath $outputPath -Encoding UTF8
        Write-Host "`n💾 完整結果已保存到: $outputPath" -ForegroundColor Cyan
        
    } else {
        Write-Host "❌ 無法解析結構化數據" -ForegroundColor Red
    }
    
} catch {
    Write-Host "❌ 無法獲取結果！" -ForegroundColor Red
    Write-Host "   錯誤: $_" -ForegroundColor Red
    exit 1
}

Write-Host "`n🎉 ===== 測試完成 =====" -ForegroundColor Cyan
Write-Host "測試時間: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
