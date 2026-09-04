<template>
  <div class="smart-text-block" :class="`view-${view}`">
    <!-- 來源標記 -->
    <div v-if="showSource && evidence && evidence.length" class="source-badge">
      📍 {{ evidence.join(', ') }}
    </div>
    
    <!-- 智能文本顯示 -->
    <div class="text-content">
      <!-- 分割視圖 -->
      <div v-if="view === 'split'" class="split-view">
        <div class="jp-text">
          <div class="lang-label">🇯🇵 日文</div>
          <div class="japanese-content" v-html="renderMarkdown(displayText.jp || displayText)"></div>
        </div>
        <div class="tw-text">
          <div class="lang-label">🇹🇼 繁中</div>
          <div class="chinese-content" v-html="renderMarkdown(displayText.tw || displayText)"></div>
        </div>
      </div>
      
      <!-- 日文視圖 -->
      <div v-else-if="view === 'jp'" @click="setView('jp')" class="single-view jp">
        <div class="lang-label">🇯🇵 日文原文</div>
        <div class="japanese-content" v-html="renderMarkdown(displayText.jp || displayText)"></div>
      </div>
      
      <!-- 繁中視圖 -->
      <div v-else-if="view === 'tw'" @click="setView('tw')" class="single-view tw">
        <div class="lang-label">🇹🇼 中文解釋</div>
        <div class="chinese-content" v-html="renderMarkdown(displayText.tw || displayText)"></div>
      </div>
      
      <!-- 無內容警告 -->
      <div v-else class="empty-content">
        <div class="empty-icon">⚠️</div>
        <div class="empty-text">
          內容載入中或來源不夠...<br>
          <small>建議：重新截圖或調整 OCR 來源</small>
        </div>
        <button class="retry-btn" @click="$emit('retry')">🔄 重試</button>
      </div>
    </div>
    
    <!-- 語言切換按鈕 -->
    <div class="view-controls">
      <button 
        v-for="mode in ['split', 'jp', 'tw']" 
        :key="mode"
        :class="{ active: view === mode }"
        @click="setView(mode)"
        class="view-btn"
      >
        {{ modeLabels[mode] }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { cleanMarkdown } from '../utils/markdownRenderer'

const props = defineProps({
  text: {
    type: String,
    default: ''
  },
  evidence: {
    type: Array,
    default: () => []
  },
  view: {
    type: String,
    default: 'split'
  },
  showSource: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['retry'])

// 語言標籤
const modeLabels = {
  split: '🔄 並排',
  jp: '🇯🇵 日文',
  tw: '🇹🇼 中文'
}

// Markdown 渲染函數
const renderMarkdown = (text) => {
  if (!text) return ''
  try {
    // 先清理雜訊
    const cleaned = cleanMarkdown(text)
    const html = marked.parse(cleaned, { breaks: true })
    return DOMPurify.sanitize(html)
  } catch (e) {
    console.error('Markdown render error:', e)
    return text
  }
}

// 解析文本內容
const displayText = computed(() => {
  if (!props.text) return {}
  
  // 嘗試解析中日雙語格式
  const jptwMatch = props.text.match(/^(.+?)\s*\|\|?\s*(.+)$/)
  if (jptwMatch) {
    return {
      jp: jptwMatch[1].trim(),
      tw: jptwMatch[2].trim()
    }
  }
  
  // 檢查是否主要是日文
  const japaneseChars = (props.text.match(/[\u3040-\u309f\u30a0-\u30ff\u31f0-\u31ff\u4e00-\u9fff]/g) || []).length
  const totalChars = props.text.length - (props.text.match(/[\s]/g) || []).length
  
  if (japaneseChars / totalChars > 0.3) {
    return { jp: props.text }
  } else {
    return { tw: props.text }
  }
})

const currentView = ref(props.view)

const setView = (newView) => {
  currentView.value = newView
}
</script>

<style scoped>
.smart-text-block {
  position: relative;
  background: var(--card-bg, #0f172a);
  border: 1px solid var(--border-color, rgba(255,255,255,0.1));
  border-radius: 16px;
  padding: 16px;
  margin: 16px 0;
  transition: all 0.3s ease;
  box-shadow: 0 4px 14px rgba(0,0,0,0.25);
}

.smart-text-block:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15);
  border-color: rgba(255,255,255,0.2);
}

.source-badge {
  position: absolute;
  top: -8px;
  right: 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
  z-index: 10;
}

.text-content {
  margin-top: 20px;
  margin-bottom: 16px;
}

/* 分割視圖 */
.split-view {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.jp-text,
.tw-text {
  padding: 12px;
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.03);
}

.jp-text {
  border-left: 4px solid #dc2626;
  background: rgba(220, 38, 38, 0.05);
}

.tw-text {
  border-left: 4px solid #3b82f6;
  background: rgba(59, 130, 246, 0.05);
}

/* 單一視圖 */
.single-view {
  padding: 16px;
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.03);
  cursor: pointer;
  transition: all 0.2s ease;
}

.single-view.jp {
  border-left: 4px solid #dc2626;
  background: rgba(220, 38, 38, 0.05);
}

.single-view.tw {
  border-left: 4px solid #3b82f6;
  background: rgba(59, 130, 246, 0.05);
}

.single-view:hover {
  transform: scale(1.02);
  border-color: rgba(255,255,255,0.2);
}

/* 語言標籤 */
.lang-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  margin-bottom: 8px;
  letter-spacing: 0.1em;
  color: rgba(255,255,255,0.8);
}

.jp-text .lang-label,
.single-view.jp .lang-label {
  color: #fca5a5;
}

.tw-text .lang-label,
.single-view.tw .lang-label {
  color: #93c5fd;
}

/* 文本內容 */
.japanese-content,
.chinese-content {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-color, #e5e7eb);
  word-break: break-word;
}

.japanese-content :deep(p),
.chinese-content :deep(p) {
  margin-bottom: 0.8em;
}

.japanese-content :deep(p:last-child),
.chinese-content :deep(p:last-child) {
  margin-bottom: 0;
}

.japanese-content :deep(ul),
.chinese-content :deep(ul),
.japanese-content :deep(ol),
.chinese-content :deep(ol) {
  padding-left: 1.5em;
  margin-bottom: 0.8em;
}

.japanese-content :deep(code),
.chinese-content :deep(code) {
  background: rgba(255,255,255,0.1);
  padding: 0.2em 0.4em;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.9em;
}

.japanese-content :deep(pre),
.chinese-content :deep(pre) {
  background: rgba(0,0,0,0.3);
  padding: 1em;
  border-radius: 8px;
  overflow-x: auto;
  margin-bottom: 0.8em;
}

.japanese-content :deep(strong),
.chinese-content :deep(strong) {
  color: var(--primary-color, #60a5fa);
  font-weight: 600;
}

.japanese-content {
  font-family: 'Noto Sans JP', 'Hiragino Kaku Gothic ProN', sans-serif;
}

/* 視圖控制 */
.view-controls {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(255,255,255,0.1);
  display: flex;
  gap: 8px;
  justify-content: center;
}

.view-btn {
  padding: 6px 12px;
  border: 1px solid rgba(255,255,255,0.2);
  background: rgba(255,255,255,0.05);
  color: rgba(255,255,255,0.8);
  border-radius: 8px;
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.view-btn:hover {
  background: rgba(255,255,255,0.1);
  transform: translateY(-1px);
}

.view-btn.active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-color: transparent;
}

/* 空內容顯示 */
.empty-content {
  text-align: center;
  padding: 24px;
  color: rgba(255,255,255,0.6);
}

.empty-icon {
  font-size: 24px;
  margin-bottom: 8px;
}

.empty-text {
  margin-bottom: 16px;
  line-height: 1.5;
}

.retry-btn {
  padding: 8px 16px;
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.2);
  color: rgba(255,255,255,0.8);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.retry-btn:hover {
  background: rgba(255,255,255,0.2);
  transform: translateY(-1px);
}

/* 響應式設計 */
@media (max-width: 768px) {
  .split-view {
    grid-template-columns: 1fr;
    gap: 12px;
  }
  
  .smart-text-block {
  }
}

@media (max-width: 480px) {
  .view-controls {
    flex-direction: column;
    gap: 6px;
  }
  
  .view-btn {
    font-size: 10px;
    padding: 4px 8px;
  }
}

/* 深色模式適配 */
@media (prefers-color-scheme: dark) {
  .smart-text-block {
    background: #0f172a;
    border-color: rgba(255,255,255,0.1);
  }
  
  .jp-text,
  .tw-text,
  .single-view {
    background: rgba(255,255,255,0.03);
    border-color: rgba(255,255,255,0.1);
  }
}
</style>

