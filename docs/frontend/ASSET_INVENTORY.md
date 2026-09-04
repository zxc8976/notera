# 前端資產盤點

> 最後更新：2025-10-01
> 框架：Vue 3 + Vite + Element Plus + Pinia

## 目錄結構總覽

| 路徑 | 狀態 | 說明 |
| --- | --- | --- |
| `src/App.vue` | ✅ 使用中 | 全域入口；載入 `DefaultLayout` 與主題設定。 |
| `src/main.js` | ✅ 使用中 | 建立 Vue 應用、註冊 Element Plus、Highlight.js、PrismJS，並設置全域錯誤處理。 |
| `src/components/` | ✅ 使用中 | 筆記渲染、對話側欄、表格等核心元件。`SuperCodeBlock.vue`、`NoteSectionRenderer.vue` 為主要渲染器。 |
| `src/layouts/` | ✅ 使用中 | `DefaultLayout.vue`、`ChatbotLayout.vue` 提供頁面佈局與側邊欄。 |
| `src/views/` | ✅ 使用中 | `Home.vue`、`Notes.vue`、`NotePage.vue`、`Chatbot.vue` 對應主要頁面。 |
| `src/router/` | ✅ 使用中 | 設定前端路由，連結主視圖與筆記頁。 |
| `src/stores/` | ✅ 使用中 | Pinia 狀態管理：`appState.js`（全域狀態）、`language.js`（語言切換）。 |
| `src/composables/` | ✅ 使用中 | `useTheme.js` 統一深淺色、`useLanguage.js` 封裝語系切換。 |
| `src/utils/` | ✅ 使用中 | Markdown/Evidence 驗證與語法高亮工具。含 `codeHighlight.test.js` 測試。 |
| `src/styles/` | ✅ 使用中 | 主題與組件樣式（`theme-unified.css`、`chatbot.css` 等）。 |
| `src/assets/print-ready.css` | ✅ 使用中 | PDF/列印版式樣式。 |
| `public/code-enhance.js` | 🔁 待確認 | 與 `src/utils/codeHighlight.js` 功能重疊；可考慮整併，以避免雙重高亮方案。 |
| `public/images/` | ✅ 使用中 | 預設圖示資產；僅含 `.gitkeep`。 |
| `scripts/manual_tests/theme_system_test.html` | 🧪 手動測試 | 主題系統手動測試頁，從前端目錄搬移至手動測試專區；原位置僅保留導向檔。 |
| `dist/` | 🧹 應忽略 | Vite 打包輸出，應保持在 `.gitignore` 中。現存檔案需確認是否可移除。 |
| `archive/old-components/` | 🗂️ 歷史備份 | 舊版元件 (`NoteBlock.vue` 等) 未被引用，可保留於 `archive` 或轉為文件附錄。 |

## 組件細節

- **筆記渲染組件**：`LlmMarkdownNote.vue`、`SuperCodeBlock.vue`、`SmartTextBlock.vue` 共同處理 AI 生成內容。
- **側欄與互動**：`RightSidebar.vue`、`ExportFab.vue` 提供工具列與匯出功能。
- **資料呈現**：`SectionCard.vue`、`TableTerm.vue` 針對章節與術語表做專用排版。
- **語系支援**：`useLanguage.js` 與 `stores/language.js` 管理繁中/日/英翻譯；`i18n/index.js` 定義詞彙。

## 觀察與建議

1. **Highlight 雙軌並行**：`highlight.js` 與 `PrismJS` 同時載入，並在 `window` 掛載。若無必要雙軌，應評估統一策略，減少 bundle 體積與維護成本。
2. **主題測試頁面**：`test-theme-system.html` 是舊版調試工具。建議搬移至 `scripts/manual_tests/` 並納入更新後的手動測試流程。
3. **歷史元件備份**：`archive/old-components/*.vue` 與現行版本名稱相似。可移至 `docs/archive/` 或補充差異說明，避免誤用。
4. **程式碼測試覆蓋**：現僅有 `src/utils/codeHighlight.test.js`；可補強核心組件的 Vitest 測試以保護重構。

## 待辦追蹤

- [ ] 確認 `public/code-enhance.js` 是否仍被使用，若無則汰除或整併。
- [x] 調整主題測試頁放置位置並更新文檔引用。
- [ ] 清理 `frontend/dist/` 可能已提交的舊檔案。
- [ ] 更新 `docs/DOCUMENTATION_MAP.md`，指向本盤點與後續前端指南。

完成上述事項後，前端資產即具備明確歸屬與維護指引。
