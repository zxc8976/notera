#!/bin/bash

# OpenCode Skills 安裝驗證腳本
# 用途: 驗證 UI UX Pro Max, Superpowers, Context7 是否正確安裝

echo "🔍 OpenCode Skills 安裝驗證"
echo "=============================="
echo ""

# 檢查計數器
PASSED=0
FAILED=0

# 1. 檢查 UI UX Pro Max (專案本地)
echo "1️⃣  檢查 UI UX Pro Max..."
if [ -d ".opencode/skills/ui-ux-pro-max" ]; then
    echo "   ✅ 已安裝在 .opencode/skills/ui-ux-pro-max/"
    if [ -f ".opencode/skills/ui-ux-pro-max/SKILL.md" ]; then
        echo "   ✅ SKILL.md 存在"
        ((PASSED++))
    else
        echo "   ❌ SKILL.md 不存在"
        ((FAILED++))
    fi
else
    echo "   ❌ 未找到 .opencode/skills/ui-ux-pro-max/"
    ((FAILED++))
fi
echo ""

# 2. 檢查 Superpowers (全域安裝)
echo "2️⃣  檢查 Superpowers..."
if [ -d "$HOME/.config/opencode/superpowers" ]; then
    echo "   ✅ 已複製到 ~/.config/opencode/superpowers/"
    
    # 檢查 plugin
    if [ -f "$HOME/.config/opencode/plugins/superpowers.js" ]; then
        echo "   ✅ Plugin 已註冊"
    else
        echo "   ❌ Plugin 未註冊"
        ((FAILED++))
    fi
    
    # 檢查 skills symlink (Windows 上可能是目錄)
    if [ -L "$HOME/.config/opencode/skills/superpowers" ] || [ -d "$HOME/.config/opencode/skills/superpowers" ]; then
        echo "   ✅ Skills 已連結/複製"
        # 驗證內容
        if [ -f "$HOME/.config/opencode/skills/superpowers/brainstorming/SKILL.md" ]; then
            echo "   ✅ Skills 內容完整"
            ((PASSED++))
        else
            echo "   ⚠️  Skills 內容不完整"
            ((FAILED++))
        fi
    else
        echo "   ❌ Skills 目錄不存在"
        ((FAILED++))
    fi
else
    echo "   ❌ 未找到 ~/.config/opencode/superpowers/"
    ((FAILED++))
fi
echo ""

# 3. 檢查 Context7 CLI
echo "3️⃣  檢查 Context7 CLI..."
if command -v ctx7 &> /dev/null; then
    VERSION=$(ctx7 --version 2>&1 | head -1)
    echo "   ✅ ctx7 已安裝: $VERSION"
    ((PASSED++))
else
    echo "   ❌ ctx7 未安裝"
    echo "      安裝指令: npm install -g ctx7"
    ((FAILED++))
fi
echo ""

# 4. 檢查文件
echo "4️⃣  檢查文件..."
if [ -f "AGENTS.md" ]; then
    if grep -q "## AI Assistant Skill Invocation Rules" AGENTS.md; then
        echo "   ✅ AGENTS.md 已更新"
        ((PASSED++))
    else
        echo "   ⚠️  AGENTS.md 缺少技能調用規則"
        ((FAILED++))
    fi
else
    echo "   ❌ AGENTS.md 不存在"
    ((FAILED++))
fi

if [ -f "docs/SKILLS_USAGE_GUIDE.md" ]; then
    echo "   ✅ 使用指南已建立"
else
    echo "   ⚠️  docs/SKILLS_USAGE_GUIDE.md 不存在"
fi

if [ -f ".opencode/SKILLS_QUICKREF.md" ]; then
    echo "   ✅ 快速參考已建立"
else
    echo "   ⚠️  .opencode/SKILLS_QUICKREF.md 不存在"
fi
echo ""

# 總結
echo "=============================="
echo "📊 驗證結果"
echo "=============================="
echo "✅ 通過: $PASSED"
echo "❌ 失敗: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "🎉 所有技能安裝成功！"
    echo ""
    echo "📖 下一步:"
    echo "   1. 重啟 OpenCode"
    echo "   2. 測試 UI UX Pro Max: \"Build a landing page for healthcare\""
    echo "   3. 測試 Superpowers: \"use skill tool to load superpowers/brainstorming\""
    echo "   4. 搜尋更多技能: ctx7 skills search react"
    exit 0
else
    echo "⚠️  有 $FAILED 項檢查失敗，請修復後重試"
    exit 1
fi
