# 使用Node.js官方鏡像作為基礎鏡像
FROM node:20-alpine

# 安裝必要的系統依賴
RUN apk add --no-cache curl dumb-init git

WORKDIR /app

# 複製package.json和package-lock.json
COPY package*.json ./

# 設置環境變量
ENV NODE_ENV=development
ENV VITE_API_BASE_URL=http://notegen:8000
ENV VITE_HOST=0.0.0.0
ENV VITE_PORT=5173

# 安裝前端依賴（使用 package-lock 確保版本鎖定）
RUN npm ci

# 複製源代碼
COPY . .

# 創建必要的目錄
RUN mkdir -p /app/public/images

# 設置目錄權限
RUN chmod -R 755 /app/public

# 為前端添加環境標記，確保重新構建時能識別架構重構
ENV VITE_BUILD_TIME="ui-3.1.7-fix-$(date +%Y%m%d%H%M%S)"
ENV VITE_UI_VERSION="3.1.7-fix"
ENV VITE_ARCHITECTURE_VERSION="modular-layouts"
ENV VITE_CSS_SYSTEM="unified-variables"
ENV VITE_DIAGNOSTICS_TIMESTAMP="true"
ENV VITE_NOTE_HEADING_VARIANT="accented"

# 健康檢查 - 檢查前端服務和統一主題系統
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://0.0.0.0:5173 && \
        test -f /app/src/layouts/DefaultLayout.vue && \
        test -f /app/src/layouts/ChatbotLayout.vue && \
        test -f /app/src/styles/theme-unified.css && \
        test -f /app/src/composables/useTheme.js || exit 1

# 暴露端口
EXPOSE 5173

# 使用dumb-init來處理信號
ENTRYPOINT ["dumb-init", "--"]

# 啟動命令 - 添加更多開發選項
CMD ["npx", "vite", "--host", "0.0.0.0", "--port", "5173", "--strictPort", "--clearScreen", "false", "--force"] 
