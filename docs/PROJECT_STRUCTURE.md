# 📁 專案結構說明（2025-10-20）

> **自動筆記生成系統 v3.0.7-enhanced**  
> 說明新版資料夾分層、主要檔案位置與維護重點。

---

## 📚 目錄概覽

```
自動筆記駐守2/
├── source/
│   ├── backend/
│   │   ├── app/                 # FastAPI 入口、配置與啟動腳本
│   │   │   ├── main.py          # 後端主程式 (uvicorn 執行目標)
│   │   │   ├── config.yaml      # 系統配置 (LLM、OCR、runtime)
│   │   │   ├── requirements.txt # Backend 依賴 (Docker build 使用)
│   │   │   └── paths_config.json# 媒體路徑組態
│   │   ├── modules/             # 後端核心模組
│   │   │   ├── api_routes.py    # REST API 定義
│   │   │   ├── image_analyzer.py# 圖片 OCR + VLM 分析
│   │   │   ├── note_generator.py# 筆記藍圖邏輯
│   │   │   ├── summarize_*.py   # 影片/圖片處理管線
│   │   │   ├── services/        # 共用服務 (配置、狀態、路徑)
│   │   │   └── utils/           # 工具函式 (路徑轉換等)
│   │   └── tests/               # 單元 / 手動測試
│   └── frontend/                # Vue3 前端專案
│       ├── src/                 # 組件、頁面、store
│       └── public/              # 靜態資源 (images/.gitkeep)
│
├── ops/                         # 部署與維運工具
│   ├── docker/
│   │   └── Dockerfile           # 後端容器映像 (uvicorn 啟動)
│   └── scripts/                 # 清理、檢查、手動工具
│       ├── cleanup.ps1          # 清理 var/ 與 cache
│       ├── tools/convert_heic_images.py
│       └── verify_prompt_integration.py
│
├── data/                        # 外部映像與大型資產
│   ├── external/                # Docker 掛載 (C:/, F:/ 等)
│   ├── images/                  # 影片/圖片來源 (本地)
│   ├── videos/
│   └── models/                  # AI 模型 (Whisper、Ollama 等)
│
├── var/                         # 執行期輸出（git 忽略）
│   ├── notes/                   # 產生的 Markdown 筆記
│   ├── output/                  # 處理輸出 (images/, tmp/)
│   ├── log/                     # 系統日誌、metrics、traces
│   └── tmp/                     # 臨時檔案
│
├── docs/                        # 技術與操作文件
├── openspec/                    # Spec/Proposal 管理中心
├── archive/                     # 歷史備份 & 舊版程式
└── ops/docker/docker-compose.yml# Docker Compose 編排
```

---

## 🧠 核心程式碼與配置

| 位置 | 說明 | 備註 |
|------|------|------|
| `source/backend/app/main.py` | FastAPI 入口 (`uvicorn source.backend.app.main:app`) | 自動掛載路徑、CORS、API route |
| `source/backend/app/config.yaml` | 系統主配置 | GPU、OCR、LLM、路徑設定 |
| `source/backend/modules/` | Backend 模組 | `note_generator.py`、`summarize_video.py` 等 |
| `source/backend/modules/services/runtime_paths.py` | 路徑常數/工具 | 管理 `data/`、`var/`、`source/` |
| `source/frontend/src/` | Vue 3 前端 | `views/Home.vue` 為入口頁 |
| `source/backend/tests/` | Pytest 測試 | `pytest.ini` 指向此路徑 |

運行路徑在啟動時會自動建立：

- `var/output/`, `var/log/`, `var/notes/`, `var/tmp/`
- `source/frontend/public/images/`

---

## 🛠️ 部署與維運

| 位置 | 內容 | 說明 |
|------|------|------|
| `ops/docker/Dockerfile` | 後端容器映像 | 讀取 `source/backend/app/requirements.txt`，ENTRYPOINT 轉向 `source.backend.app.main:app` |
| `ops/docker/docker-compose.yml` | Docker Compose | 調整後掛載 `data/external/*` 與 `var/*` |
| `ops/scripts/cleanup.ps1` | 清理腳本 | 新版指向 `var/`、`data/` 目錄 |
| `ops/scripts/tools/convert_heic_images.py` | HEIC 工具 | 同步到新 `source/frontend/` 結構 |

啟動指令：

```bash
docker compose -f ops/docker/docker-compose.yml up -d
# 或
uvicorn source.backend.app.main:app --reload
```

---

## 📦 執行期與資料目錄

| 目錄 | 內容 | 備註 |
|------|------|------|
| `var/notes/` | 產生的 Markdown 筆記 | 舊 `saved_notes/` |
| `var/output/` | 影片/圖片輸出、臨時檔案 | 舊 `output/` |
| `var/log/` | `notegen.log`、`system_metrics/`、`traces/` | 舊 `logs/` |
| `data/external/` | Docker 外部掛載根目錄 | 舊 `external_[c|f]/` |
| `data/models/` | Whisper、Ollama、Paddle 等模型 | 舊 `models/`, `ollama_models/` |

這些路徑被視為「使用者資料／暫存」，已在 `.gitignore` 中忽略；部署前請確認備份與清理策略。

---

## 🗃️ 歷史與備份

| 目錄 | 說明 |
|------|------|
| `archive/` | 2025-11 起僅保留 `README.md`。歷史快照請改查 Git tag / release。 |
| `git tag` / branch | 若需完整舊版程式，請切換到對應 Commit，而非在 repo 內保存一份拷貝。 |

> 2025-11-12：清空 `archive/backups/`、`archive/docs/`、`archive/legacy-code/`，移除舊 `.backup` 模組與重複文檔，避免與現行代碼混淆。

---

## ✅ 檢查清單

- [x] 確認 `source/backend/app/config.yaml` 與腳本/測試路徑一致  
- [x] Docker 映像與 Compose 指向新結構 (`ops/docker/…`)  
- [x] 清理腳本、工具腳本更新至 `var/`、`data/`  
- [x] `.gitignore` 忽略 `var/*`, `data/*` 等執行期輸出  
- [x] README 與主要文件同步新目錄說明

若新增模組或資料夾，請依照此分層原則放入對應區域，並更新本文件或 `openspec` 中的相關規範。
