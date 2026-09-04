# 監控筆記生成處理狀態
# 用法: powershell -ExecutionPolicy Bypass -File ops/scripts/monitor_processing.ps1

Write-Host "=== 自動筆記生成監控 ===" -ForegroundColor Cyan
Write-Host "按 Ctrl+C 停止監控" -ForegroundColor Yellow
Write-Host ""

# 顏色定義
$colors = @{
    "場景" = "Green"
    "章節" = "Blue"
    "LLM" = "Magenta"
    "ERROR" = "Red"
    "WARNING" = "Yellow"
    "remote_model" = "Cyan"
    "completed" = "Green"
}

# 持續監控
$lastLines = 0
while ($true) {
    Clear-Host
    Write-Host "=== 處理狀態監控 (即時更新) ===" -ForegroundColor Cyan
    Write-Host "時間: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
    Write-Host ""
    
    # 取得最新 50 行日誌
    $logs = docker logs notegen-backend-enhanced --tail 50 2>&1 | Out-String
    
    # 過濾關鍵資訊
    $lines = $logs -split "`n" | Where-Object { 
        $_ -match "場景|章節|LLM|ERROR|WARNING|remote_model|completed|Processing|總共" 
    }
    
    # 顯示帶顏色的日誌
    foreach ($line in $lines) {
        $color = "White"
        foreach ($key in $colors.Keys) {
            if ($line -match $key) {
                $color = $colors[$key]
                break
            }
        }
        Write-Host $line -ForegroundColor $color
    }
    
    Write-Host ""
    Write-Host "--- 雲端 API 使用統計 ---" -ForegroundColor Cyan
    $cloudCalls = (docker logs notegen-backend-enhanced 2>&1 | Select-String "remote_model" | Measure-Object).Count
    Write-Host "雲端 API 呼叫次數: $cloudCalls" -ForegroundColor Magenta
    
    Write-Host ""
    Write-Host "--- 最新輸出檔案 ---" -ForegroundColor Cyan
    docker exec notegen-backend-enhanced ls -lt /app/var/output/ 2>&1 | Select-String ".json|.md" | Select-Object -First 3
    
    Start-Sleep -Seconds 5
}
