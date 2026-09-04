#  自動筆記生成系統
**版本**: 3.0.7-enhanced | **最後更新**: 2025-10-20

> 基於本地 AI 的智能筆記生成系統，支持影片轉錄、圖片 OCR 和多模態內容分析  
> **v3.1.0-paddleocr-vl** | 🆕 VLM-First架構 | 最後更新: 2025-10-21

執行
bash ops/scripts/setup_llm_services.sh


[![Version](https://img.shields.io/badge/version-3.1.0--paddleocr--vl-blue.svg)](docs/CHANGELOG.md)
[![Docker](https://img.shields.io/badge/docker-ready-green.svg)](ops/docker/docker-compose.yml)
[![Status](https://img.shields.io/badge/status-stable-green.svg)](#)
[![VLM](https://img.shields.io/badge/VLM--First-v1.0.0-orange.svg)](docs/VLM_FIRST_ARCHITECTURE.md)


## 🚀 多模態 LLM Provider

目前預設使用 **Ollama 官方釋出的 `qwen3-vl:4b`**，在 8 GB 級 GPU 上也能穩定運行，長片不再容易因 VRAM 爆滿而失敗。若環境具備 12 GB 以上 VRAM、需要更高畫質，可改成 `qwen3-vl:8b`（請手動修改 `config.yaml` 並重新拉取模型）。如需重新建置或更新模型，步驟如下：

1. **一鍵安裝 / 更新模型**
   ```bash
   bash ops/scripts/setup_llm_services.sh
   ```
   指令會：
   - 透過 `docker compose` 啟動 `ollama_local`
   - 在容器內執行 `ollama pull qwen3-vl:4b`（或 `qwen3-vl:8b`）
   - 重新建置並啟動 `notegen-backend-enhanced`, `notegen-frontend-enhanced`

> 後端會在 **每次 LLM 呼叫前** 自動釋放 Paddle/torch 的 GPU cache，日誌會記錄釋放前後的 VRAM 使用量，方便營運追蹤。

3. **驗證**
   - `curl http://localhost:11434/api/tags` 應能看到 `qwen3-vl:4b`（或你指定的模型）
   - `GET /api/llm/providers` 可確認後端目前匯出的模型列表
   - `GET /api/diagnose` 檢查完整健康狀態
   - 若需要更換到其他模型，可先 `docker exec ollama_local ollama pull <model>`，再修改 `source/backend/app/config.yaml` 中的 `scene_model` / `image_model` / `final_model`


## 🛠 系統資源盤點

執行 `python ops/scripts/collect_system_info.py` 可輸出 CPU / RAM / 磁碟 / GPU 報告至 `docs/infra/`，建議升級前先記錄硬體狀態以供追蹤。


---

## 📁 目錄導覽（2025-11 整理後）

| 目錄 | 內容 / 用途 |
|------|-------------|
| `source/backend/` | FastAPI + 多模態筆記管線主程式。`app/` 內含 `main.py`、`config.yaml`，`modules/` 保存核心邏輯。 |
| `source/frontend/` | Vue 3 前端。為避免舊版產物干擾，`node_modules/`、`dist/` 已移除，請依 `package.json` 重新 `npm install` 後再啟動。 |
| `ops/docker/` | Dockerfile、Compose、部署腳本，是容器化入口。 |
| `ops/scripts/` | 清理、診斷、模型下載等工具腳本。 |
| `docs/` | 現行技術/操作文件，`docs/PROJECT_STRUCTURE.md` 有更細節的結構圖。 |
| `openspec/` | 規格、Proposal、任務追蹤的權威來源。 |
| `data/` | 本地大型資產（影片/圖片/模型），已在 `.gitignore` 排除。 |
| `var/` | 執行期輸出（logs、notes、images、tmp），部署時請視需求清理或備份。 |
| `archive/` | 已清空，只保留 `README.md`。若未來放入歷史檔案，請於該檔註明來源與用途。 |

> ✅ 舊的 `archive/backups/`、`archive/docs/`、`archive/legacy-code/`、`.cursor/`、`.specstory/`、`.pytest_cache/`、`source/frontend/dist/`、`source/frontend/node_modules/` 等目錄已刪除，避免與現行程式混在一起。若需歷史版本，請回到 Git tag/branch。

---

## 🎯 核心特性

| 功能 | 說明 | 狀態 |
|------|------|------|
| 🎬 **影片處理** | 場景檢測 + OCR 識別 + AI 視覺摘要 | ✅ 穩定 |
| 🖼️ **圖片處理** | PaddleOCR-VL 識別 + 多模態視覺模型分析 | ✅ 穩定 |
| 🤖 **VLM-First架構** | 視覺語言模型優先,OCR輔助,支援程式碼內容 | 🆕 v1.0.0 |
| 📝 **智能筆記** | 結構化筆記生成、講義過濾、內容去重 | ✅ 穩定 |
| 🌏 **多語言支持** | 中文/英文/日文內容處理 | ✅ 穩定 |
| 🎨 **現代化 UI** | Vue 3 + 響應式設計 + 深色模式 | ✅ 穩定 |
| 🐳 **容器化部署** | Docker Compose 一鍵啟動 | ✅ 穩定 |
| ⚡ **GPU 加速** | PaddleOCR-VL + Qwen3-VL 自動偵測 CUDA，無 GPU 時安全回退 | ✅ 穩定 |

---

## 🆕 VLM-First 架構

**什麼是VLM-First?**
- **V**ision **L**anguage **M**odel 為核心的筆記生成架構
- 直接分析課程截圖,不依賴日文比例檢查
- 完整支援程式碼(Java/Python)、英文講義、混合語言內容

**核心優勢**:
```
傳統: OCR提取 → 日文檢查 → ❌ 過濾掉Java程式碼

VLM-First: 截圖 + OCR → VLM分析 → ✅ 完整程式碼筆記
```

**詳細文檔**: [VLM_FIRST_ARCHITECTURE.md](docs/VLM_FIRST_ARCHITECTURE.md) (永久參考版本)

---

##  AI 助手指引

> **如果您是 AI 助手，請優先閱讀以下文檔以理解系統:**

###  必讀文檔 (按順序)
1. **[docs/VLM_FIRST_ARCHITECTURE.md](docs/VLM_FIRST_ARCHITECTURE.md)** - 🆕 VLM-First架構說明 (永久參考版本)
2. **[docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)** -  完整目錄結構與用途說明
3. **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** -  系統架構與技術棧
4. **[docs/系統文件說明.md](docs/系統文件說明.md)** -  模組功能與資料流程
5. **[docs/TECHNICAL_DOCS.md](docs/TECHNICAL_DOCS.md)** -  API 規範與實作細節

###  問題排查文檔
- **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - 故障排除
- **[docs/NOTE_OUTPUT_TROUBLESHOOTING.md](docs/NOTE_OUTPUT_TROUBLESHOOTING.md)** - 筆記輸出問題
- **[docs/reports/QUICK_REFERENCE.md](docs/reports/QUICK_REFERENCE.md)** - 常用命令速查

###  核心程式碼位置
- **VLM-First架構**: `source/backend/modules/note_generator.py` (核心筆記藍圖邏輯)
- **後端邏輯**: `source/backend/modules/image_analyzer.py`, `source/backend/modules/summarize_video.py`
- **前端主頁**: `source/frontend/src/views/Home.vue`
- **API 路由**: `source/backend/modules/api_routes.py`
- **主程式**: `source/backend/app/main.py`

---

##  重要目錄說明

> **完整說明請參考: [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)**

| 目錄 | 用途 | 大小 |
|------|------|------|
| **source/backend/app/** | FastAPI 入口、配置 (`config.yaml`)、啟動腳本 | |
| **source/backend/modules/** | 後端核心模組 (OCR、LLM、筆記生成) | |
| **source/frontend/** | Vue 3 前端應用與開發資源 | |
| **var/** | 執行期輸出 (`notes/`, `output/`, `log/`, `tmp/`) | 動態 |
| **data/** | 外部掛載、模型與大型資產 (`external/`, `models/`) | 動態 |
| **ops/** | Docker、維運腳本、結構檢查 | |
| **archive/** | 歷史備份與舊版程式 | |
| **docs/** | 完整文檔 (35+ 個技術文檔) | ~500 KB |
| **openspec/** | Spec 驅動需求、變更提案 | |

---

##  快速開始

```bash
# 啟動所有服務
docker compose -f ops/docker/docker-compose.yml up -d

# 訪問應用
# 前端: http://localhost:5173
# API: http://localhost:18000/docs

# 檢查Ollama模型
curl http://localhost:11434/api/tags

# 本地開發 (僅後端)
uvicorn source.backend.app.main:app --reload
```

## ⚡ GPU 配置

- 建置時啟用 GPU 版 Paddle：`USE_PADDLE_GPU=true docker compose build notegen`
- 於 `source/backend/app/config.yaml` 設定 `runtime.prefer_gpu` 與 `fallback_to_cpu` 控制 GPU/CPU 切換
- 參考 [`docs/GPU_RUNTIME_GUIDE.md`](docs/GPU_RUNTIME_GUIDE.md) 取得詳細操作與排查步驟

---

##  完整文檔

### 核心文檔
- **[docs/VLM_FIRST_ARCHITECTURE.md](docs/VLM_FIRST_ARCHITECTURE.md)** - 🆕 VLM-First架構 (永久參考)
- **[docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)** -  目錄結構說明
- **[docs/reports/QUICK_REFERENCE.md](docs/reports/QUICK_REFERENCE.md)** -  命令速查
- **[docs/README.md](docs/README.md)** -  文檔索引

### 技術文檔
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - 系統架構
- **[docs/TECHNICAL_DOCS.md](docs/TECHNICAL_DOCS.md)** - API規範
- **[docs/MODEL_CONFIGURATION.md](docs/MODEL_CONFIGURATION.md)** - 模型配置
- **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** -  故障排除

**版本**: 3.0.7-enhanced | **最後更新**: 2025-10-20

