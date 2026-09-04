# 後端模組盤點

> 最後更新：2025-10-01
> 框架：FastAPI + AsyncIO + Ollama（LLM） + PaddleOCR-VL

## 核心模組概觀

| 路徑 | 狀態 | 說明 |
| --- | --- | --- |
| `main.py` | ✅ 使用中 | FastAPI 入口（約 3,200 行），整合路由、背景任務、存取 `modules/*`。含大量歷史路由與處理流程。 |
| `modules/api_routes.py` | ⚠️ 部分重複 | 早期嘗試拆分路由；與 `main.py` 內邏輯重疊且未全面導入。建議後續正式抽離或移除。 |
| `modules/file_handlers.py` | ✅ 使用中 | 檔案存取工具：影音清單、HEIC/MP4 正規化、Base64 編碼。`FileProcessor` 提供統一介面。 |
| `modules/image_analyzer.py` | ✅ 使用中 | 多模態圖片分析，整合 OCR 與 LLM；含 HEIC 轉換、OCR 回退邏輯。 |
| `modules/note_generator.py` | ✅ 使用中 | 影像/影片筆記格式化，負責中日雙語模板與圖片路徑填充。 |
| `modules/summarize_image.py` | ✅ 使用中 | 單張圖片摘要流程，調用 `ImageAnalyzer` 與 `NoteGenerator`。 |
| `modules/summarize_video.py` | ✅ 使用中 | 影片分鏡摘要入口，與 `video_cut`、`NoteGenerator` 整合。 |
| `modules/llm_utils.py` | ✅ 使用中 | 與 Ollama 互動的統一封裝，含重試/快取。 |
| `modules/core/ocr_utils.py` | ✅ 使用中 | 單例 `OCRManager`，集中管理 PaddleOCR-VL 引擎。 |

## 周邊腳本與工具

| 檔案 | 狀態 | 作用 |
| --- | --- | --- |
| `backend_ocr_cleanup.py` | ✅ 保留 | 產線級 OCR 噪音清理器；提供文字降噪與圖片預處理。可合併進 `modules/core`。 |
| `convert_heic_images.py` | 🛠️ 手動工具 | 批次 HEIC → JPG 轉換。與 `FileProcessor.handle_heic_format` 功能重疊，建議整併。 |
| `optimize_system.py` | ✅ 使用中 | 系統優化腳本，重建索引、清理暫存、更新模型。 |
| `scripts/doc_audit.py` | ✅ 使用中 | 文檔稽核（目前已用於 Markdown 清點）。 |
| `scripts/manual_tests/ocr_check.py` | ✅ 使用中 | 整合的 OCR 手動檢測工具。 |

## 資料夾與資產

- `output/`：生成的筆記 (`docs/`, `images/`, `tmp/`)，已在 `.gitignore` 排除。
- `saved_notes/`：最終輸出的筆記儲存，需與 `main.py` 頁面維持一致。
- `models/whisper/`：語音模型資源。
- `ollama_models/`：Ollama 客戶端緩存。

## 發現的重疊/待清理項目

1. **路由重複**：`main.py` 與 `modules/api_routes.py` 均定義 `/api/models`、`/api/paths`。後者未真正掛載，易造成維護混淆。
2. **HEIC 處理重複**：`FileProcessor.handle_heic_format`、`convert_heic_images.py`、`ImageAnalyzer._handle_heic_format` 三處實作已統一走 `FileProcessor`，維護點縮減。
3. **OCR 清理位置**：`backend_ocr_cleanup.py` 與 `ImageAnalyzer`/`NoteGenerator` 功能重疊。建議將 `OCRContentCleaner` 納入 `modules/core` 並在影像/影片流程中套用。
4. **主檔案過大**：`main.py` 過於肥大，建議逐步模組化（路由、背景任務、資源管理）。

## 建議的模組化方向

- ✅ **短期**：
  - 將 `backend_ocr_cleanup.py` 中的 `OCRContentCleaner` 整合進 `modules/core/cleanup.py`（或現有模組），並更新 `ImageAnalyzer` 調用鏈。
  - 把 `convert_heic_images.py` 中的批次轉換功能包入 `FileProcessor`，提供 CLI 入口。
- 🔁 **中期**：
  - 抽取 `main.py` 路由至 FastAPI Router（`modules/api_routes.py`），並確保單一引用來源。
  - 建立 `modules/services/`，將影片處理、圖片處理、筆記生成拆分為清晰的服務層。
- 🧪 **測試**：
  - 為 `modules/file_handlers.py`、`modules/note_generator.py` 補充單元測試，覆蓋 HEIC 轉換與 Markdown 格式生成。

## 待辦追蹤

- [ ] 確認 `modules/api_routes.py` 是否仍需保留；若無，搬遷或移除以避免混淆。
- [x] 整併 HEIC 處理邏輯，避免三處維護風險。
- [ ] 將 `OCRContentCleaner` 納入主流程並撰寫對應測試。
- [ ] 制定 `main.py` 拆分計畫，建立 `routers/` 與 `services/` 子資料夾。

完成以上整理後，後端模組將具備清晰邊界與維護策略，便於持續重構與部署。
