# 🎯 自動筆記生成系統架構簡報文檔

> **版本**: v3.1.0-paddleocr-vl  
> **建立日期**: 2026-01-31  
> **文檔類型**: 技術簡報 / 架構總覽  
> **適用對象**: 技術團隊、管理層、外部合作夥伴

---

## 📋 目錄

1. [系統概述](#系統概述)
2. [核心架構](#核心架構)
3. [VLM-First 創新](#vlm-first-創新)
4. [技術棧](#技術棧)
5. [部署架構](#部署架構)
6. [關鍵特性](#關鍵特性)
7. [資料流程](#資料流程)
8. [專案結構](#專案結構)

---

## 🎯 系統概述

### 什麼是自動筆記生成系統？

**基於本地 AI 的智能筆記生成平台**，自動從影片講義和圖片截圖中提取內容，生成結構化的雙語學習筆記。

### 核心價值

```
傳統筆記方式                  自動筆記生成系統
─────────────────            ─────────────────
👨‍💻 手動整理 2-4 小時    →    🤖 自動生成 5-10 分鐘
📝 容易遺漏重點           →    🎯 AI 提取關鍵概念
📚 格式不統一             →    📋 標準化 Markdown
🇯🇵 僅日文內容           →    🌐 雙語對照（日文/中文）
☁️ 依賴雲端 API          →    🔒 完全本地化部署
```

### 主要功能

| 功能 | 說明 | 狀態 |
|------|------|------|
| 🎬 **影片處理** | 場景檢測 + OCR + AI 視覺摘要 | ✅ 穩定 |
| 🖼️ **圖片處理** | PaddleOCR-VL + 多模態視覺分析 | ✅ 穩定 |
| 🤖 **VLM-First** | 視覺語言模型優先，OCR 輔助 | 🆕 v1.0.0 |
| 📝 **智能筆記** | 結構化生成、去重、過濾 | ✅ 穩定 |
| 🌏 **多語言** | 中文/日文/英文內容處理 | ✅ 穩定 |
| 🎨 **現代 UI** | Vue 3 響應式界面 + 深色模式 | ✅ 穩定 |
| 🐳 **容器化** | Docker Compose 一鍵部署 | ✅ 穩定 |
| ⚡ **GPU 加速** | CUDA 自動偵測，無 GPU 安全回退 | ✅ 穩定 |

---

## 🏗️ 核心架構

### 整體架構圖

```
┌─────────────────────────────────────────────────────────────┐
│                      用戶瀏覽器                              │
│                  Vue 3 前端界面                              │
│                 (localhost:5173)                            │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP/REST API
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI 後端服務                           │
│                  (localhost:18000)                          │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ 影片處理模組  │  │ 圖片處理模組  │  │ 筆記生成模組  │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                  │                  │             │
│         └──────────────────┴──────────────────┘             │
│                            │                                │
└────────────────────────────┼────────────────────────────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
            ▼                ▼                ▼
    ┌───────────┐    ┌──────────┐    ┌──────────┐
    │  Ollama   │    │ PaddleOCR│    │ Whisper  │
    │ (VLM/LLM) │    │   (OCR)  │    │  (ASR)   │
    │ qwen3-vl  │    │  GPU版   │    │ large-v3 │
    └───────────┘    └──────────┘    └──────────┘
         |                |                 |
         └────────────────┴─────────────────┘
                          │
                    ┌─────▼─────┐
                    │  NVIDIA   │
                    │    GPU    │
                    │ (8GB+ VRA)│
                    └───────────┘
```

### 三層架構設計

| 層級 | 技術 | 職責 |
|------|------|------|
| **呈現層** | Vue 3 + Element Plus | 用戶界面、筆記預覽、設定管理 |
| **業務層** | FastAPI + Python | API 路由、筆記生成邏輯、模型調度 |
| **資料層** | 文件系統 + AI 模型 | 影片/圖片儲存、筆記輸出、模型推理 |

---

## 🆕 VLM-First 創新

### 什麼是 VLM-First？

**V**ision **L**anguage **M**odel 優先的筆記生成架構，直接分析課程截圖，不依賴日文比例檢查。

### 為什麼需要 VLM-First？

#### 傳統 OCR-First 的問題

```python
# ❌ 舊架構：OCR-First + 日文比例檢查
ocr_text = extract_text(image)
jp_ratio = count_japanese_chars(ocr_text) / len(ocr_text)

if jp_ratio < 0.05:  # 過濾掉程式碼內容！
    skip_this_scene()
    
# 結果：Java/Python 程式碼被過濾掉
```

#### VLM-First 的解決方案

```python
# ✅ 新架構：VLM-First
image = load_image(scene_path)
ocr_text = extract_text(image)  # 僅作參考

vlm_prompt = f"""
分析這張課堂截圖，提取關鍵學習內容。

參考 OCR 文字（以圖片為準）：
{ocr_text[:500]}

請提取：
1. 核心概念或標題
2. 重要程式碼片段
3. 關鍵說明或注意事項
"""

note = call_vlm(image, vlm_prompt)
# 結果：完整保留程式碼和英文內容
```

### VLM-First 核心優勢

| 傳統方式 | VLM-First | 改進 |
|---------|-----------|------|
| 依賴 OCR 文字 | 直接理解圖片 | ✅ 減少 OCR 錯誤影響 |
| 日文比例檢查 | 內容智能判斷 | ✅ 支援多語言混合 |
| 過濾程式碼 | 保留程式碼 | ✅ 適用程式設計課程 |
| 無法理解佈局 | 理解視覺結構 | ✅ 更好的筆記組織 |
| 處理率 ~60% | 處理率 ~95% | ✅ 大幅提升覆蓋率 |

### 處理流程對比

```
┌──────────────────────────────────────────────────────────┐
│ 傳統 OCR-First 流程                                       │
├──────────────────────────────────────────────────────────┤
│ 影片 → 場景檢測 → OCR 提取 → 日文比例檢查 → 過濾         │
│                                    ↓                      │
│                              ❌ 程式碼被過濾               │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│ VLM-First 流程                                           │
├──────────────────────────────────────────────────────────┤
│ 影片 → 場景檢測 → OCR 提取（參考）→ VLM 多模態分析       │
│                                    ↓                      │
│                              ✅ 完整程式碼筆記             │
└──────────────────────────────────────────────────────────┘
```

---

## 🛠️ 技術棧

### 後端技術

| 技術 | 版本 | 用途 | 特點 |
|------|------|------|------|
| **Python** | 3.10+ | 主要語言 | 豐富的 AI 生態系 |
| **FastAPI** | 0.100+ | Web 框架 | 高性能、自動文檔 |
| **Uvicorn** | 0.23+ | ASGI 服務器 | 支援異步處理 |
| **Ollama** | Latest | 本地 LLM | 開源、GPU 加速 |
| **Whisper** | Large-v3 | 語音識別 | OpenAI 預訓練 |
| **PaddleOCR-VL** | 3.0+ | 文字識別 | 中日英優化 |
| **OpenCV** | 4.8+ | 影片處理 | 場景檢測 |
| **PySceneDetect** | 0.6+ | 場景切換 | 自適應閾值 |

### 前端技術

| 技術 | 版本 | 用途 | 特點 |
|------|------|------|------|
| **Vue 3** | 3.3+ | 前端框架 | Composition API |
| **Vite** | 4.4+ | 建構工具 | 極速 HMR |
| **Element Plus** | 2.3+ | UI 組件 | 企業級設計 |
| **Tailwind CSS** | 3.3+ | CSS 框架 | 工具類優先 |
| **marked.js** | 9.0+ | Markdown 渲染 | 輕量高效 |
| **highlight.js** | 11.8+ | 代碼高亮 | 語法識別 |
| **Axios** | 1.5+ | HTTP 客戶端 | Promise 風格 |

### AI 模型

| 模型 | 用途 | 硬體需求 | 備註 |
|------|------|----------|------|
| **Qwen3-VL:4b** | 視覺語言模型 | GPU 8GB+ | 預設使用 |
| **Qwen3-VL:8b** | 高精度 VLM | GPU 12GB+ | 可選升級 |
| **Whisper Large-v3** | 語音轉文字 | GPU 6GB+ | 多語言支援 |
| **PaddleOCR-VL** | 結構化 OCR | GPU 8GB+ | 佈局分析 |

---

## 🐳 部署架構

### Docker Compose 容器編排

```yaml
services:
  # Ollama LLM 服務
  ollama_local:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_models:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  # 後端服務
  notegen-backend-enhanced:
    build: ./ops/docker
    ports:
      - "18000:18000"
    volumes:
      - ./source/backend:/app/source/backend
      - ./var:/app/var
      - ./data:/app/data
    environment:
      - USE_PADDLE_GPU=true
      - CUDA_VISIBLE_DEVICES=0

  # 前端服務
  notegen-frontend-enhanced:
    build: ./source/frontend
    ports:
      - "5173:5173"
    volumes:
      - ./source/frontend:/app
```

### 一鍵啟動腳本

```bash
# ops/scripts/setup_llm_services.sh
bash ops/scripts/setup_llm_services.sh

# 自動執行：
# 1. 啟動 Ollama 容器
# 2. 拉取 qwen3-vl:4b 模型
# 3. 建置並啟動後端/前端
# 4. 驗證服務健康狀態
```

### 硬體需求

| 配置 | 最低需求 | 推薦配置 |
|------|---------|---------|
| **CPU** | 4 核心 | 8 核心 |
| **RAM** | 16 GB | 32 GB |
| **GPU** | NVIDIA 8GB VRAM | NVIDIA 12GB+ VRAM |
| **儲存** | 50 GB SSD | 100 GB NVMe |
| **網路** | 100 Mbps | 1 Gbps |

---

## ⚡ 關鍵特性

### 1. 完全本地化

```
✅ 所有 AI 模型運行在本地
✅ 無需雲端 API
✅ 數據不外流
✅ 可離線運行（模型下載後）
```

### 2. GPU 自動偵測

```python
# 自動偵測 CUDA 並回退
if torch.cuda.is_available():
    device = "cuda"
    logger.info(f"使用 GPU: {torch.cuda.get_device_name(0)}")
else:
    device = "cpu"
    logger.warning("GPU 不可用，回退至 CPU")
```

### 3. 實時進度追蹤

- WebSocket 推送處理進度
- 場景級別進度更新
- 處理時間預估
- GPU/記憶體使用率監控

### 4. 智能噪音過濾

```python
# 只過濾系統畫面，保留課程內容
noise_keywords = [
    'file explorer',
    'ファイルエクスプローラ',
    'chrome://settings',
    '系統設定'
]

# ✅ 保留 Google Classroom
# ✅ 保留程式碼截圖
# ✅ 保留英文講義
```

### 5. 多格式輸出

| 格式 | 說明 | 用途 |
|------|------|------|
| **Markdown** | 標準筆記格式 | Git 版本控制 |
| **HTML** | 網頁預覽 | 分享、列印 |
| **PDF** | 瀏覽器列印 | 存檔、發佈 |

---

## 🔄 資料流程

### 影片處理流程

```
1️⃣ 影片上傳
   ├─ 檔案驗證（格式、大小）
   └─ 儲存至 data/videos/

2️⃣ 場景檢測
   ├─ PySceneDetect 分析
   ├─ 提取關鍵幀（閾值：30）
   └─ 儲存至 var/output/images/

3️⃣ OCR 提取
   ├─ PaddleOCR-VL 識別
   ├─ 佈局分析
   └─ 結構化輸出

4️⃣ VLM 分析
   ├─ 載入場景圖片
   ├─ 調用 Qwen3-VL（base64）
   ├─ 傳入 OCR 文字（參考）
   └─ 生成場景筆記

5️⃣ 筆記整合
   ├─ 合併所有場景
   ├─ 去重過濾
   ├─ 格式標準化
   └─ 輸出 Markdown

6️⃣ 結果儲存
   └─ var/notes/{filename}.md
```

### 圖片處理流程

```
1️⃣ 圖片資料夾上傳
   ├─ 支援格式：JPG, PNG, HEIC
   └─ 自動轉換 HEIC → JPG

2️⃣ OCR + VLM 分析
   ├─ PaddleOCR 提取文字
   └─ Qwen3-VL 理解圖片

3️⃣ 筆記生成
   ├─ 圖片 + 日文重點 + 中文說明
   ├─ 術語表
   └─ 程式碼/公式

4️⃣ 儲存輸出
   └─ var/notes/{foldername}.md
```

---

## 📁 專案結構

```
自動筆記駐守2/
│
├── source/                        # 原始碼
│   ├── backend/                   # 後端服務
│   │   ├── app/                   # FastAPI 入口
│   │   │   ├── main.py           # ⭐ 主程式
│   │   │   └── config.yaml       # ⭐ 系統配置
│   │   ├── modules/              # 核心模組
│   │   │   ├── note_generator.py # ⭐ VLM-First 邏輯
│   │   │   ├── summarize_video.py# 影片處理
│   │   │   ├── image_analyzer.py # 圖片處理
│   │   │   └── api_routes.py     # REST API
│   │   └── tests/                # 單元測試
│   │
│   └── frontend/                  # Vue 3 前端
│       ├── src/
│       │   ├── views/
│       │   │   └── Home.vue      # ⭐ 主頁面
│       │   ├── components/       # UI 組件
│       │   └── composables/      # 可組合式 API
│       └── public/               # 靜態資源
│
├── ops/                          # 運維工具
│   ├── docker/
│   │   ├── Dockerfile           # ⭐ 後端容器
│   │   └── docker-compose.yml   # ⭐ 容器編排
│   └── scripts/                 # 自動化腳本
│       └── setup_llm_services.sh# ⭐ 一鍵部署
│
├── data/                        # 外部資料（git 忽略）
│   ├── videos/                  # 影片來源
│   ├── images/                  # 圖片來源
│   └── models/                  # AI 模型
│
├── var/                         # 執行期輸出（git 忽略）
│   ├── notes/                   # 生成的筆記
│   ├── output/                  # 處理輸出
│   ├── log/                     # 系統日誌
│   └── tmp/                     # 臨時檔案
│
├── docs/                        # 文檔
│   ├── ARCHITECTURE.md          # 系統架構
│   ├── VLM_FIRST_ARCHITECTURE.md# VLM-First 詳解
│   └── PROJECT_STRUCTURE.md     # 專案結構
│
└── openspec/                    # 規格管理
    ├── AGENTS.md                # AI 代理指令
    └── project.md               # 專案規格
```

### 關鍵檔案說明

| 檔案 | 位置 | 說明 |
|------|------|------|
| **main.py** | `source/backend/app/` | FastAPI 應用入口 |
| **config.yaml** | `source/backend/app/` | 系統配置（GPU、模型、路徑） |
| **note_generator.py** | `source/backend/modules/` | VLM-First 核心邏輯 |
| **Home.vue** | `source/frontend/src/views/` | 主界面元件 |
| **docker-compose.yml** | `ops/docker/` | 容器編排配置 |
| **setup_llm_services.sh** | `ops/scripts/` | 一鍵部署腳本 |

---

## 📊 系統監控

### 即時指標

```yaml
系統健康度:
  - CPU 使用率
  - RAM 使用量
  - GPU 使用率
  - VRAM 使用量
  - 磁碟空間

處理狀態:
  - 當前處理檔案
  - 已處理場景數
  - 進度百分比
  - 預估剩餘時間

模型狀態:
  - Ollama 服務狀態
  - 已載入模型列表
  - 模型切換功能
```

### 診斷 API

```bash
# 系統健康檢查
GET /api/diagnose

# 回應範例
{
  "ollama": { "status": "online", "models": ["qwen3-vl:4b"] },
  "gpu": { "available": true, "name": "NVIDIA RTX 3090" },
  "storage": { "free_gb": 250 },
  "runtime": { "uptime_hours": 12.5 }
}
```

---

## 🚀 快速開始

### 前置需求

```bash
# 1. 安裝 Docker + Docker Compose
docker --version  # >= 24.0
docker compose version  # >= 2.20

# 2. 安裝 NVIDIA Container Toolkit（若使用 GPU）
nvidia-smi

# 3. 確認磁碟空間
df -h  # 需要至少 50 GB
```

### 部署步驟

```bash
# 1. Clone 專案
git clone <repository-url>
cd 自動筆記駐守2

# 2. 一鍵啟動
bash ops/scripts/setup_llm_services.sh

# 3. 訪問服務
# 前端: http://localhost:5173
# API: http://localhost:18000/docs
```

### 驗證安裝

```bash
# 檢查 Ollama 模型
curl http://localhost:11434/api/tags

# 檢查後端健康
curl http://localhost:18000/api/version

# 檢查系統狀態
curl http://localhost:18000/api/diagnose
```

---

## 📈 性能指標

### 處理速度

| 任務類型 | 輸入 | 處理時間 | 硬體 |
|---------|------|---------|------|
| **短影片** | 5 分鐘講義 | ~3 分鐘 | RTX 3090 |
| **長影片** | 60 分鐘講義 | ~20 分鐘 | RTX 3090 |
| **圖片資料夾** | 20 張截圖 | ~5 分鐘 | RTX 3090 |

### 資源使用

| 指標 | 空閒 | 處理中 |
|------|------|--------|
| **CPU** | 5% | 30% |
| **RAM** | 4 GB | 12 GB |
| **GPU** | 0% | 85% |
| **VRAM** | 1 GB | 7 GB |

---

## 🔐 安全性

### 數據隱私

```
✅ 所有處理在本地完成
✅ 無需雲端 API 金鑰
✅ 數據不離開內網
✅ 支援離線運行
```

### 訪問控制

```yaml
# 預設配置（可自訂）
CORS:
  - 允許來源: localhost:5173
  - 允許方法: GET, POST, DELETE
  - 允許憑證: true

API:
  - 速率限制: 100 req/min
  - 檔案大小限制: 500 MB
```

---

## 🛠️ 維護與擴展

### 模型更新

```bash
# 更新 VLM 模型
docker exec ollama_local ollama pull qwen3-vl:8b

# 修改配置使用新模型
vim source/backend/app/config.yaml
# scene_model: qwen3-vl:8b
```

### 擴展功能

```python
# 新增自訂處理模組
# source/backend/modules/custom_processor.py

async def process_custom_content(content: str):
    # 1. 調用 LLM
    result = await call_ollama_llm(...)
    
    # 2. 格式化輸出
    return format_output(result)
```

---

## 📞 技術支援

### 常見問題

**Q: GPU 不可用怎麼辦？**  
A: 系統會自動回退至 CPU 模式，速度較慢但功能完整。

**Q: 記憶體不足？**  
A: 調整 `config.yaml` 中 `batch_size` 降低並發處理數量。

**Q: 模型下載失敗？**  
A: 檢查網路連線，手動執行 `ollama pull qwen3-vl:4b`。

### 日誌位置

```
var/log/
├── app.log              # 應用日誌
├── gpu_metrics.log      # GPU 使用記錄
└── error.log            # 錯誤日誌
```

---

## 📚 相關文檔

| 文檔 | 說明 |
|------|------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 詳細系統架構 |
| [VLM_FIRST_ARCHITECTURE.md](docs/VLM_FIRST_ARCHITECTURE.md) | VLM-First 實作細節 |
| [PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) | 專案結構詳解 |
| [MODEL_CONFIGURATION.md](docs/MODEL_CONFIGURATION.md) | 模型配置指南 |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | 故障排除 |

---

## 🎓 總結

### 系統優勢

```
1. 🎯 準確性高
   - VLM-First 架構提升內容理解
   - 多模態分析減少錯誤

2. ⚡ 效率提升
   - 自動化取代手動整理
   - GPU 加速大幅縮短時間

3. 🔒 隱私安全
   - 完全本地化部署
   - 數據不外流

4. 🌐 多語言支援
   - 雙語筆記（日文/中文）
   - 程式碼內容完整保留

5. 🚀 易於部署
   - Docker 一鍵啟動
   - 自動化運維腳本
```

### 適用場景

- 📚 **教育機構**: 課堂錄影自動筆記
- 💼 **企業培訓**: 內訓課程知識萃取
- 🎓 **個人學習**: 線上課程重點整理
- 🔬 **研究機構**: 研討會內容記錄

---

**文檔版本**: v1.0  
**最後更新**: 2026-01-31  
**維護者**: 自動筆記生成系統團隊
