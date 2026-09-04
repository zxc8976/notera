# 🤖 模型配置說明（2025-10 更新）

系統目前 **僅維護一條推論流程**：Ollama 服務搭配 **`qwen3-vl:4b`**。此模型在 8–10 GB VRAM 的 GPU 上即可與 PaddleOCR-VL 同時運行，長時間處理影片也能保持穩定；若需要更高畫質輸出、且具備 12 GB 以上 VRAM，可手動改回 `qwen3-vl:8b`。

## ✅ 為什麼選擇 `qwen3-vl:4b`

| 重點 | 說明 |
|------|------|
| 多模態支援 | 單一模型即可分析講義截圖與輸出段落摘要。 |
| 資源需求 | 約 6–7 GB VRAM，可與 PaddleOCR-VL 併行；若有 12 GB 以上 VRAM，可改用 `qwen3-vl:8b` 取得更佳品質。 |
| 維運簡單 | 官方模型即可使用，無需自定 Modelfile。 |
| 行為一致 | 場景摘要、圖片分析與最終整合全部使用同一個模型。 |

## 📦 預設配置

```yaml
llm:
  provider: ollama
  max_tokens: 4096
  temperature: 0.4
  scene_model: "qwen3-vl:4b"
  image_model: "qwen3-vl:4b"
  final_model: "qwen3-vl:4b"
  ollama:
    base_url: http://ollama_local:11434
    timeout: 600
    supports_images: true
    models:
      - qwen3-vl:4b
```

> `setup_llm_services.sh` 會自動拉取所需模型並啟動 `ollama_local`、後端與前端容器。若要切換到 8B，請先修改 `source/backend/app/config.yaml`，再重新執行腳本與建置流程。

## 🚀 安裝／更新模型

```bash
# 啟動整個堆疊並下載模型
bash ops/scripts/setup_llm_services.sh

# 再次執行可以更新模型版本
docker compose -f ops/docker/docker-compose.yml exec ollama_local ollama pull qwen3-vl:4b
```

確認模型是否存在：

```bash
docker compose -f ops/docker/docker-compose.yml exec ollama_local ollama list
```

輸出中應該包含 `qwen3-vl:4b`。

## 🧹 清理未使用模型

如需釋放空間，建議定期檢查並移除過期模型：

```bash
docker compose -f ops/docker/docker-compose.yml exec ollama_local ollama list
docker compose -f ops/docker/docker-compose.yml exec ollama_local ollama rm <model-name>
```

- `max_tokens` 影響 LLM 一次呼叫的輸出長度，本系統建議維持 **4096** 以確保能輸出完整段落；若 VRAM 有壓力，可視情況降到 3072，但需自行驗證筆記長度。
- `temperature` 預設為 **0.4**，讓結果更穩定；需要更多創意時再調整。

> 建議保留 `qwen3-vl:4b` 作為主要模型；其他大型模型（如 `qwen3-vl:8b`、`qwen3-vl:30b`、`llama3` 等）可視需求移除釋放空間。若需要升級畫質，可再 `ollama pull qwen3-vl:8b` 並於 `config.yaml` 指定。

## 📊 資源參考

| 資源 | 估計值 |
|------|--------|
| GPU VRAM | 8–9 GB（含 PaddleOCR-VL 及背景任務） |
| 系統 RAM | 8–12 GB |
| 模型磁碟 | ~3.5 GB（4B）／~6 GB（8B） |

> 後端會在 **每次 LLM 呼叫前** 釋放 Paddle/torch 的 GPU cache，並在日誌中記錄釋放前後的使用量。如觀察到 VRAM 漲幅，可檢查 `/var/log/backend.log` 或 `docker compose logs notegen`.

## ❓ 常見問題

- **可以切換成其他模型嗎？**  
  目前不支援。若要實驗其他模型，請另開變更並新增專屬 provider，避免污染正式流程。

- **可以改用 `qwen3-vl:4b` 嗎？**  
  可以。請先 `ollama pull qwen3-vl:4b`，再將 `config.yaml` 的 `scene_model` / `image_model` / `final_model` 改為 `qwen3-vl:4b`。模型容量約 5 GB，適合 VRAM 8–10 GB 的環境，但視覺推理能力較 8B 略弱。

- **還需要保留舊版模型嗎？**  
  不需要。新流程已全面改用 Qwen3-VL。若磁碟空間有限，可執行 `docker compose exec ollama_local ollama rm <deprecated-model>` 清理歷史殘留。

## 🔗 相關文件

- [CONFIGURATION.md](CONFIGURATION.md) – 系統配置總覽
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) – 常見問題排查
- [ARCHITECTURE.md](ARCHITECTURE.md) – 架構說明

---

**最後更新**：2025-10-28  
**維運負責人**：AI Platform 維運組
