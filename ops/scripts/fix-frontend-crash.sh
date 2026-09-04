#!/bin/bash
# 前端崩潰修復腳本 - 解決 Bun Segmentation Fault 問題
# 創建時間: 2026-01-31
# 用途: 清理並重新建置前端環境

set -e  # 遇到錯誤時停止

echo "========================================"
echo "前端崩潰修復工具"
echo "========================================"
echo ""

# 切換到前端目錄
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/../../source/frontend"
cd "$FRONTEND_DIR"

echo "[1/5] 停止可能正在運行的開發伺服器..."
pkill -f "bun.*dev" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 2

echo "[2/5] 清理舊的 node_modules 和 lock 檔案..."
if [ -d "node_modules" ]; then
    echo "正在刪除 node_modules..."
    rm -rf node_modules
fi

if [ -f "bun.lockb" ]; then
    echo "正在刪除 bun.lockb..."
    rm -f bun.lockb
fi

if [ -f "package-lock.json" ]; then
    echo "正在刪除 package-lock.json..."
    rm -f package-lock.json
fi

echo "[3/5] 清理 Bun 快取..."
bun pm cache rm 2>/dev/null || true

echo "[4/5] 重新安裝依賴 (這可能需要幾分鐘)..."
if bun install --force; then
    echo "✅ Bun 安裝成功"
else
    echo "❌ Bun 安裝失敗,嘗試使用 npm..."
    npm install
fi

echo "[5/5] 清理開發伺服器快取..."
if [ -d ".vite" ]; then
    rm -rf .vite
fi

echo ""
echo "========================================"
echo "✅ 修復完成!"
echo "========================================"
echo ""
echo "現在你可以嘗試重新啟動開發伺服器:"
echo "  cd source/frontend"
echo "  bun run dev"
echo ""
echo "如果問題仍然存在,請嘗試:"
echo "  1. 更新 Bun: bun upgrade"
echo "  2. 使用 npm 代替: npm run dev"
echo "  3. 檢查系統記憶體是否充足 (至少需要 4GB 可用記憶體)"
echo "  4. 檢查 /var/log/syslog 或 dmesg 查看崩潰原因"
echo ""
