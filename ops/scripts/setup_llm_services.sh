#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}/../.."
COMPOSE_FILE=${COMPOSE_FILE:-${PROJECT_ROOT}/ops/docker/docker-compose.yml}
OLLAMA_MODEL_NAME=${OLLAMA_MODEL_NAME:-qwen3-vl:4b}
export USE_PADDLE_GPU="${USE_PADDLE_GPU:-true}"

printf '\n[setup_llm_services] 建置並啟動容器 (ollama, backend, frontend)\n'
docker compose -f "$COMPOSE_FILE" up -d --build ollama_local

printf '\n[setup_llm_services] 下載 Ollama 模型：%s\n' "$OLLAMA_MODEL_NAME"
if docker compose -f "$COMPOSE_FILE" exec ollama_local ollama pull "$OLLAMA_MODEL_NAME"; then
  echo "✅ 模型 ${OLLAMA_MODEL_NAME} 已就緒"
else
  echo "⚠️ 模型下載失敗，請檢查網路或授權設定。" >&2
  exit 1
fi

printf '\n[setup_llm_services] 啟動後端 / 前端服務\n'
docker compose -f "$COMPOSE_FILE" up -d --build notegen frontend

printf '\n[setup_llm_services] 目前容器狀態\n'
docker compose -f "$COMPOSE_FILE" ps
