<template>
  <div class="super-code-block">
    <!-- 程式碼標題行 -->
    <div class="code-header">
      <div class="header-left">
        <span v-if="displayTitle" class="code-title">{{ displayTitle }}</span>
        <span class="language-badge">{{ language || 'code' }}</span>
      </div>
      <div class="header-right">
        <button 
          v-if="copyable" 
          @click="copyCode" 
          :class="{ copied: copySuccessful }"
          class="copy-btn"
        >
          {{ copySuccessful ? '✅' : '📋' }} {{ copySuccessful ? '已複製' : '複製' }}
        </button>
      </div>
    </div>

    <!-- 程式碼內容 -->
    <div class="code-content-wrapper">
      <pre class="code-pre"><code ref="codeRef" :class="`language-${language}`">{{ cleanedCode }}</code></pre>
      
      <!-- 程式碼解釋 (如果有的話) -->
      <div v-if="explanation && explanation.length" class="code-explanation">
        <div class="explanation-header">
          <span class="explanation-icon">💡</span>
          <span class="explanation-title">程式碼說明</span>
        </div>
        <ul class="explanation-list">
          <li 
            v-for="(line, i) in explanation" 
            :key="i" 
            class="explanation-item"
            v-html="renderMarkdown(line)"
          ></li>
        </ul>
      </div>
    </div>

    <!-- 預期輸出 (如果有的話) -->
    <div v-if="expectedOutput" class="expected-output">
      <div class="output-header">
        <span class="output-icon">📤</span>
        <span class="output-title">預期輸出</span>
      </div>
      <div class="output-content">{{ expectedOutput }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { stripNoisyTextLabels, formatFlattenedCode } from '../utils/markdownRenderer'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js'
import 'highlight.js/styles/atom-one-dark.css'

const props = defineProps({
  code: {
    type: String,
    default: ''
  },
  language: {
    type: String,
    default: 'text'
  },
  title: {
    type: String,
    default: ''
  },
  explanation: {
    type: Array,
    default: () => []
  },
  expectedOutput: {
    type: String,
    default: ''
  },
  copyable: {
    type: Boolean,
    default: true
  }
})

const codeRef = ref(null)
const copySuccessful = ref(false)

const cleanedCode = computed(() => {
  if (!props.code) return ''
  let c = props.code
  
  // 使用共用的清理邏輯移除 text 前綴
  c = stripNoisyTextLabels(c)
  
  // 嘗試修復壓扁的程式碼
  c = formatFlattenedCode(c)
  
  // Remove markdown code block markers
  c = c.replace(/^```\w*\s*/, '').replace(/\s*```$/, '')
  return c
})

const displayTitle = computed(() => {
  if (!props.title) return ''
  return stripNoisyTextLabels(props.title)
})

const renderMarkdown = (text) => {
  if (!text) return ''
  try {
    const html = marked.parse(text)
    return DOMPurify.sanitize(html)
  } catch (e) {
    return text
  }
}

// 語法高亮已由 markdownRenderer.js 的 markedHighlight 插件處理
// 移除重複的高亮呼叫以避免衝突
// onMounted(async () => {
//   await nextTick()
//   if (codeRef.value) {
//     hljs.highlightElement(codeRef.value)
//   }
// })

// 複製功能
const copyCode = async () => {
  if (!cleanedCode.value) return
  
  try {
    // 優先使用現代 Clipboard API
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(cleanedCode.value)
    } else {
      // 回退到選取方法
      const textArea = document.createElement('textarea')
      textArea.value = cleanedCode.value
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)
    }
    
    copySuccessful.value = true
    ElMessage.success('程式碼已複製到剪貼簿！')
    
    // 2秒後重置狀態
    setTimeout(() => {
      copySuccessful.value = false
    }, 2000)
    
  } catch (error) {
    console.error('複製失敗:', error)
    ElMessage.error('複製失敗，請手動選取程式碼')
  }
}
</script>

<style scoped>
.super-code-block {
  background: var(--card-bg, #0f172a);
  border: 1px solid var(--border-color, rgba(255,255,255,0.1));
  border-radius: var(--radius-lg, 16px);
  overflow: hidden;
  margin: var(--spacing-md, 16px) 0;
  box-shadow: var(--shadow-md, 0 4px 14px rgba(0,0,0,0.25));
  transition: all var(--transition-slow, 0.3s ease);
}

.super-code-block:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg, 0 8px 30px rgba(0,0,0,0.15));
  border-color: var(--border-hover, rgba(255,255,255,0.2));
}

/* 標題行 */
.code-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-sm, 8px) var(--spacing-md, 16px);
  background: var(--secondary-bg, #1e293b);
  border-bottom: 1px solid var(--border-color, rgba(255,255,255,0.1));
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm, 8px);
}

.code-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #e5e7eb);
}

.language-badge {
  background: var(--gradient-accent, linear-gradient(135deg, #667eea 0%, #764ba2 100%));
  color: white;
  padding: var(--spacing-xs, 4px) var(--spacing-sm, 8px);
  border-radius: var(--radius-sm, 6px);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.header-right {
  display: flex;
  align-items: center;
}

.copy-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: var(--text-primary, #e5e7eb);
  padding: var(--spacing-xs, 4px) var(--spacing-sm, 8px);
  border-radius: var(--radius-md, 12px);
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: all var(--transition-normal, 0.2s ease);
}

.copy-btn:hover {
  background: rgba(255, 255, 255, 0.2);
  transform: translateY(-1px);
}

.copy-btn.copied {
  background: var(--gradient-accent, linear-gradient(135deg, #10b981 0%, #059669 100%));
  border-color: transparent;
  color: white;
}

/* 程式碼內容 */
.code-content-wrapper {
  background: #1e293b;
}

.code-pre {
  padding: var(--spacing-lg, 24px);
  margin: 0;
  background: #1e293b;
  color: #e5e7eb;
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', 'SF Mono', 'Monaco', 'Inconsolata', monospace;
  font-size: 14px;
  line-height: 1.6;
  overflow-x: auto;
  border-radius: 0;
}

/* 程式碼解釋 */
.code-explanation {
  border-top: 1px solid rgba(255,255,255,0.1);
  background: rgba(255,255,255,0.03);
}

.explanation-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs, 4px);
  padding: var(--spacing-sm, 8px) var(--spacing-md, 16px);
  border-bottom: 1px solid rgba(255,255,255,0.05);
}

.explanation-icon {
  font-size: 14px;
}

.explanation-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary, rgba(255,255,255,0.8));
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.explanation-list {
  margin: 0;
  padding: var(--spacing-sm, 8px) var(--spacing-lg, 24px) var(--spacing-md, 16px);
  list-style: none;
}

.explanation-item {
  margin-bottom: var(--spacing-xs, 4px);
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-secondary, rgba(255,255,255,0.8));
}

.explanation-item:last-child {
  margin-bottom: 0;
}

.explanation-item::before {
  content: '•';
  color: var(--success, #10b981);
  margin-right: var(--spacing-xs, 4px);
  font-weight: bold;
}

/* 預期輸出 */
.expected-output {
  border-top: 1px solid rgba(255,255,255,0.1);
  background: rgba(59, 130, 246, 0.05);
}

.output-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs, 4px);
  padding: var(--spacing-sm, 8px) var(--spacing-md, 16px);
  border-bottom: 1px solid rgba(59, 130, 246, 0.1);
}

.output-icon {
  font-size: 14px;
}

.output-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--chinese-color, #3b82f6);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.output-content {
  padding: var(--spacing-md, 16px);
  background: rgba(59, 130, 246, 0.02);
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  font-size: 13px;
  color: var(--text-primary, #e5e7eb);
  border-radius: 0 0 var(--radius-md, 12px) var(--radius-md, 12px);
  border-left: 3px solid var(--chinese-color, #3b82f6);
}

/* 響應式設計 */
@media (max-width: 768px) {
  .code-header {
    flex-direction: column;
    gap: var(--spacing-sm, 8px);
    align-items: flex-start;
  }
  
  .header-left,
  .header-right {
    width: 100%;
    justify-content: space-between;
  }
  
  .code-pre {
    padding: var(--spacing-md, 16px);
    font-size: 13px;
  }
}

@media (max-width: 480px) {
  .copy-btn {
    font-size: 11px;
    padding: var(--spacing-xs, 4px) var(--spacing-xs, 4px);
  }
  
  .language-badge {
    font-size: 10px;
  }
}

/* 📱 深色模式優化 */
@media (prefers-color-scheme: dark) {
  .code-content-wrapper {
    background: #1e293b;
  }
  
  .code-pre {
    background: #1e293b;
    color: #e5e7eb;
  }
  
  .super-code-block {
    border-color: rgba(255,255,255,0.1);
  }
  
  .super-code-block:hover {
    border-color: rgba(255,255,255,0.2);
  }
}

/* 🎭 動畫效果 */
@keyframes codeShow {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.super-code-block {
  animation: codeShow 0.3s ease-out;
}

/* 🔋 減少動畫（效能友善） */
@media (prefers-reduced-motion: reduce) {
  .super-code-block {
    animation: none;
    transition: none;
  }
  
  .copy-btn:hover,
  .super-code-block:hover {
    transform: none;
  }
}

/* ✨ 語法高亮優化 */
.code-pre code {
  background: transparent !important;
  padding: 0 !important;
  border: none !important;
  border-radius: 0 !important;
}

/* 確保程式碼不被截斷 */
.code-pre {
  white-space: pre-wrap;
  word-break: break-word;
}

/* 關鍵字顏色優化 */
.token.comment {
  color: #6b7280 !important;
  font-style: italic;
}

.token.keyword {
  color: #60a5fa !important;
  font-weight: 600;
}

.token.string {
  color: #34d399 !important;
}

.token.number {
  color: #fbbf24 !important;
}
</style>
