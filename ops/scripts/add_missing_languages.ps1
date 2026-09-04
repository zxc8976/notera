# 添加缺失語言和翻譯的腳本
# 越南文 (vi)、緬甸文 (my)、蒙古文 (mn)

$i18nFile = "f:\日本電子\自動筆記駐守2\frontend\src\i18n\index.js"
$content = Get-Content $i18nFile -Raw

# 檢查是否需要添加新語言
if ($content -notmatch "'vi':\s*\{") {
    Write-Host "需要添加越南文翻譯"
}

if ($content -notmatch "'my':\s*\{") {
    Write-Host "需要添加緬甸文翻譯"
}

if ($content -notmatch "'mn':\s*\{") {
    Write-Host "需要添加蒙古文翻譯"
}

Write-Host "請手動在 i18n/index.js 中添加以下語言的翻譯"
Write-Host "1. 越南文 (vi)"
Write-Host "2. 緬甸文 (my)"  
Write-Host "3. 蒙古文 (mn)"
