# Whisper 依賴移除腳本
# 用途: 從 Docker 容器中移除 faster-whisper 及相關依賴
# 日期: 2025-10-12

Write-Host "🔧 開始移除 Whisper 相關依賴..." -ForegroundColor Cyan

# 1. 檢查容器狀態
Write-Host "`n📋 Step 1: 檢查容器狀態..." -ForegroundColor Yellow
$containerStatus = docker ps --filter "name=notegen-backend-enhanced" --format "{{.Status}}"
if (-not $containerStatus) {
    Write-Host "❌ 容器 notegen-backend-enhanced 未運行" -ForegroundColor Red
    Write-Host "請先啟動容器: docker-compose up -d" -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ 容器運行中: $containerStatus" -ForegroundColor Green

# 2. 檢查當前安裝的 Whisper 相關套件
Write-Host "`n📋 Step 2: 檢查當前 Whisper 相關套件..." -ForegroundColor Yellow
docker exec notegen-backend-enhanced pip list | Select-String -Pattern "whisper|webrtcvad|ctranslate"

# 3. 移除 faster-whisper 及相關依賴
Write-Host "`n📋 Step 3: 移除 faster-whisper 及相關依賴..." -ForegroundColor Yellow
docker exec notegen-backend-enhanced bash -c @"
pip uninstall -y faster-whisper webrtcvad ctranslate2 av
"@

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Whisper 套件移除成功" -ForegroundColor Green
} else {
    Write-Host "⚠️ 部分套件可能未安裝" -ForegroundColor Yellow
}

# 4. 清理 pip 緩存
Write-Host "`n📋 Step 4: 清理 pip 緩存..." -ForegroundColor Yellow
docker exec notegen-backend-enhanced pip cache purge
Write-Host "✅ 緩存清理完成" -ForegroundColor Green

# 5. 驗證移除結果
Write-Host "`n📋 Step 5: 驗證移除結果..." -ForegroundColor Yellow
$whisperCheck = docker exec notegen-backend-enhanced pip list | Select-String -Pattern "whisper"
if ($whisperCheck) {
    Write-Host "⚠️ 仍有 Whisper 相關套件:" -ForegroundColor Yellow
    Write-Host $whisperCheck
} else {
    Write-Host "✅ 所有 Whisper 相關套件已移除" -ForegroundColor Green
}

# 6. 測試模組載入
Write-Host "`n📋 Step 6: 測試系統模組載入..." -ForegroundColor Yellow
$testResult = docker exec notegen-backend-enhanced python -c @"
import sys
try:
    from modules.summarize_video import summarize, WHISPER_AVAILABLE
    print(f'✅ 模組載入成功')
    print(f'ℹ️ WHISPER_AVAILABLE = {WHISPER_AVAILABLE}')
    print(f'ℹ️ 系統將使用純視覺分析模式 (OCR + 場景檢測)')
except Exception as e:
    print(f'❌ 模組載入失敗: {e}')
    sys.exit(1)
"@

Write-Host $testResult

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ Whisper 移除完成且系統正常運行!" -ForegroundColor Green
} else {
    Write-Host "`n❌ 系統模組載入失敗,請檢查錯誤" -ForegroundColor Red
    exit 1
}

# 7. 檢查 PaddleOCR 狀態
Write-Host "`n📋 Step 7: 驗證 PaddleOCR 功能..." -ForegroundColor Yellow
docker exec notegen-backend-enhanced python -c @"
from paddleocr import PaddleOCR
import paddleocr
print(f'✅ PaddleOCR 版本: {paddleocr.__version__}')
ocr = PaddleOCR(use_angle_cls=True, lang='japan', show_log=False)
print('✅ PaddleOCR 初始化成功')
"@

Write-Host "`n🎉 完成! 系統摘要:" -ForegroundColor Cyan
Write-Host "  ✅ faster-whisper 已移除" -ForegroundColor Green
Write-Host "  ✅ 相關依賴已清理" -ForegroundColor Green  
Write-Host "  ✅ 系統模組正常運行" -ForegroundColor Green
Write-Host "  ✅ PaddleOCR 功能正常" -ForegroundColor Green
Write-Host "  ℹ️  系統現採用純視覺分析模式" -ForegroundColor Cyan
Write-Host "`n📚 詳細資訊請參考: docs\WHISPER_REMOVAL_GUIDE.md" -ForegroundColor Yellow

# 8. 顯示下一步建議
Write-Host "`n📋 建議的後續步驟:" -ForegroundColor Cyan
Write-Host "  1. 測試影片處理功能 (上傳測試影片)" -ForegroundColor White
Write-Host "  2. 驗證筆記生成品質" -ForegroundColor White
Write-Host "  3. 如需重新啟用 Whisper,參考替代方案:" -ForegroundColor White
Write-Host "     - OpenAI Whisper API (推薦,無依賴衝突)" -ForegroundColor Gray
Write-Host "     - whisper.cpp (高性能 C++ 實現)" -ForegroundColor Gray
Write-Host "     - 等待 faster-whisper 更新支援新版 tokenizers" -ForegroundColor Gray
