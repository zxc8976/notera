# 手動測試工具

> 位置：`scripts/manual_tests/`

| 檔案 | 目的 | 使用方式 |
| --- | --- | --- |
| `ocr_check.py` | 針對單張圖片或資料夾進行 PaddleOCR-VL / Tesseract 對比，驗證辨識品質。 | `python scripts/manual_tests/ocr_check.py --help` 查看指令說明。 |
| `theme_system_test.html` | 檢視前端主題系統（深淺色、CSS 變數）在純靜態環境的呈現效果。 | 直接以瀏覽器開啟，或透過 `npm run dev` 後使用 `http://localhost:5173/scripts/manual_tests/theme_system_test.html`。 |

## 使用建議

1. **版本控管**：此資料夾僅存放手動驗證需要的工具，不應包含打包產物。
2. **跨團隊可見性**：若新增手動測試腳本，請同步更新本表格並在 `docs/DOCUMENTATION_MAP.md` 註記。
3. **與自動化測試互補**：手動測試完成後，建議將穩定需求轉換為 Vitest/pytest 測試案例，降低回歸風險。
