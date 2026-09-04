# 📚 Docs 目錄導覽（2025-11）

本目錄僅保留「常用核心文件 + 分類子資料夾」，其餘歷史/冗長文檔已搬到 `docs/archive/2025-11-cleanup/`，避免與現行資訊混在一起。

## 🎯 現役核心文件

| 檔名 | 內容摘要 |
|------|----------|
| `ARCHITECTURE.md` | 系統組件與資料流程。 |
| `PROJECT_STRUCTURE.md` | 專案樹狀結構、各資料夾職責。 |
| `MODEL_CONFIGURATION.md` | 目前使用的 VLM / LLM / OCR 設定。 |
| `VLM_FIRST_ARCHITECTURE.md` | VLM-First 筆記產線詳細說明。 |

> 依需求可從這四份文件交錯查閱：`ARCHITECTURE` = 宏觀、`PROJECT_STRUCTURE` = 目錄定位、`MODEL_CONFIGURATION` = 模型設定、`VLM_FIRST_ARCHITECTURE` = 筆記邏輯。

## 🗂️ 子資料夾

| 子資料夾 | 用途 |
|----------|------|
| `backend/` | 後端專用補充（API、資產盤點等）。 |
| `frontend/` | 前端 UI / 組件 / 主題說明。 |
| `infra/` | 部署、機房與 GPU / 系統監控紀錄。 |
| `reports/` | 新版報告、量測結果（若無特別說明，默認為 2025-10 之後）。 |
| `test_reports/` | 測試紀錄、驗收清單。 |
| `筆記分析/` | 中文需求稿與學員筆記解析。 |
| `archive/2025-11-cleanup/` | 本次整理移出的舊文件，保留查考但不再影響主流程。 |

## 🧭 如何使用

1. **想知道程式碼在哪 / 如何啟動？** → `PROJECT_STRUCTURE.md` + `ARCHITECTURE.md`.
2. **調整 LLM / VLM / OCR 設定？** → `MODEL_CONFIGURATION.md`.
3. **理解 VLM-First 筆記規則或擴充？** → `VLM_FIRST_ARCHITECTURE.md`.
4. **找過往報告或修復紀錄？** → 先看對應子資料夾；若不在，至 `docs/archive/2025-11-cleanup/`.

## 🗂️ 移動紀錄（2025-11-12）

為了讓 `docs/` 更好找資料，我們把下列舊檔統一移到 `docs/archive/2025-11-cleanup/`：

- `CHANGELOG.md`、`DOCUMENTATION_MAP.md`、`NOTE_OUTPUT_*`, `UI_*`, `CLEANUP_*`, 各式分析/報告等共 30+ 份文件。
- 任何未來新增的歷史檔若不再常用，也請放進 `docs/archive/<日期>/` 並於此 README 註明。

## ✍️ 維護建議

- 新增文檔時，若為常用指南或需長期參考，請同步更新此 README 的「核心文件 / 子資料夾」描述。
- 舊文件若僅供備查，請直接放進 `docs/archive/<yyyy-mm>-<描述>/`，並在此記錄整理日期與範圍。

最後更新：2025-11-12  
維護者：平台維運/AI 工程組
