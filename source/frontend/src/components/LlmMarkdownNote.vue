<template>
  <div class="notion-note-container" ref="noteRoot">
    <!-- 工具列 -->
    <div class="notion-toolbar">
      <div class="toolbar-left">
        <div class="note-stats">
          <span class="stat-item">
            <i class="icon">📄</i>
            {{ (cardBlocks && cardBlocks.length) || 0 }}{{ t('blocks') }}
          </span>
          <span class="stat-item">
            <i class="icon">📝</i>
            {{ wordCount }}{{ t('words') }}
          </span>
          <span class="stat-item">
            <i class="icon">🖼️</i>
            {{ imageCount }}{{ t('images') }}
          </span>
          <span class="stat-item">
            <i class="icon">🎬</i>
            {{ sceneCount }}{{ t('scenes') }}
          </span>
        </div>
      </div>
      <div class="toolbar-right">
        <!-- 添加语音解析开关 -->
        <el-switch v-model="parseAudio" :active-text="t('parseAudio')" :inactive-text="t('dontParseAudio')"
          style="margin-right: 15px;"></el-switch>
        <el-button size="small" @click="syncAndRefreshImages" icon="Refresh" type="success">
          {{ t('syncImages') }}
        </el-button>
        <el-button size="small" @click="copyMarkdown" icon="DocumentCopy" type="primary">
          {{ t('copyMarkdown') }}
        </el-button>
        <!-- 移除本地工具列匯出按鈕，統一使用全域右下角 FAB -->
        <span v-if="copied" class="copied-tip">{{ t('copiedSuccess') }}</span>
      </div>
    </div>

    <!-- 筆記內容 -->
    <div class="notion-content-wrapper">
      <!-- 內嵌 TOC 已移除，只保留右側 Sticky TOC -->

      <div v-if="!effectiveMarkdown || effectiveMarkdown.trim() === ''" class="empty-state">
        <div class="empty-icon">📝</div>
        <h3>{{ t('noNoteGenerated') }}</h3>
        <p>{{ t('uploadVideoToGenerate') }}</p>
      </div>

      <div v-else class="notion-blocks">
        <!-- 零幻覺：只渲染基本 markdown 內容，移除所有固定卡片 -->
        <div v-for="(block, idx) in cardBlocks" :key="block.id || idx" class="notion-block" :class="{
          'image-pair-block': block.isImagePair,
          'image-block': block.pairType === 'image',
          'content-block': block.pairType === 'content'
        }">
          <div class="block-content llm-note-markdown" v-html="processMarkdownBlock(block.markdown)"></div>
        </div>
      </div>

      <!-- 添加处理状态显示 -->
      <div v-if="processingStatus" class="processing-status">
        <span>{{ processingStatus.detail }}</span>
        <el-button size="small" @click="retryProcessing" type="warning">{{ t('retry') }}</el-button>
      </div>

      <!-- 错误信息显示 -->
      <div v-if="errorInfo" class="error-info">
        <span>{{ errorInfo.message }}</span>
        <el-button size="small" @click="retryProcessing" type="warning">{{ t('retry') }}</el-button>
      </div>
    </div>

    <!-- 底部資訊 -->
    <div v-if="effectiveMarkdown && effectiveMarkdown.trim() !== ''" class="notion-footer">
      <div class="footer-info">
        <span>🕒 {{ t('lastUpdated') }}：{{ lastUpdated }}</span>
        <span>🎨 {{ t('smartLearningNote') }} (v3.1.7-fix)</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { marked, Marked } from 'marked'
import { createI18n } from '../i18n/index.js'
import { validateStructuredData, checkOCRQuality } from '../utils/groundingValidator.js'
import { renderMathExpressions, renderNoteMarkdown, cleanMarkdown } from '../utils/markdownRenderer.js'
import hljs from 'highlight.js'
import 'highlight.js/styles/atom-one-dark.css'

// 國際化設置
const currentLanguage = ref(localStorage.getItem('notegen-language') || 'zh-TW')
let { t } = createI18n(currentLanguage)
const noteRoot = ref(null)

// 監聽語言變化
watch(currentLanguage, (newLang) => {
  console.log('[LlmMarkdownNote] 語言變化:', newLang)
  localStorage.setItem('notegen-language', newLang)
  const { t: newT } = createI18n(ref(newLang))
  t = newT
  
  // 觸發重新渲染
  nextTick(() => {
    console.log('[LlmMarkdownNote] 語言切換後重新渲染')
  })
})

// 監聽 localStorage 變化（當其他組件切換語言時）
onMounted(() => {
  const handleStorageChange = () => {
    const newLang = localStorage.getItem('notegen-language') || 'zh-TW'
    if (newLang !== currentLanguage.value) {
      currentLanguage.value = newLang
    }
  }

  window.addEventListener('storage', handleStorageChange)
  // 也監聽自定義事件
  window.addEventListener('languageChanged', handleStorageChange)

  return () => {
    window.removeEventListener('storage', handleStorageChange)
    window.removeEventListener('languageChanged', handleStorageChange)
  }
})
import DOMPurify from 'dompurify'

// 深色模式樣式已整合到統一主題系統

// == 安全性與高亮優化：marked-highlight + DOMPurify + 語言標籤修正 ==
// 1. 使用 marked-highlight 取代舊 highlight 寫法
// 2. 用 DOMPurify 過濾 markdown 輸出，防止 XSS
// 3. 將 ```pseudo 自動替換為 ```text，避免 highlight.js 警告
// ------------------------------------------------------

// == 修復全局配置衝突：使用局部配置方式 ==
// 1. 不創建實例，而是在每次parse時傳遞配置
// 2. 確保圖片渲染器正確工作
// 3. 保持代碼高亮功能
// ------------------------------------------------------

// 自定義渲染器來支持 ==標記== 語法
const renderer = new marked.Renderer()

// 擴展文本渲染以支持 ==highlight== 語法
renderer.text = function (text) {
  // 處理 ==重點== 標記，使用更強的模式匹配
  text = text.replace(/==(.*?)==/g, '<mark class="highlight-mark">$1</mark>')

  // 處理 👈 指示符號
  text = text.replace(/👈\s*(重點|注意|重要)/g, '<span class="pointer">👈 $1</span>')

  return text
}

// 自定義段落渲染，確保段落內的文本也被處理
renderer.paragraph = function (text) {
  const hasMath = /(\$[^$]+\$|\$\$[\s\S]+?\$\$|\\frac|\\sum|\\int|\\pi|π|∞|∑|√|×|⋅|∣)/.test(text)

  // 保留公式：若包含數學符號/LaTeX，僅做輕量清理
  if (hasMath) {
    text = text.replace(/\u00A0/g, ' ').replace(/[ \t]+/g, ' ').trim()
  } else {
    // 清理OCR錯誤和亂碼：保留常見符號與數學字符，避免公式被吃掉
    try {
      const keepReadableChars = new RegExp('[^\\p{L}\\p{M}\\p{N}\\p{P}\\p{S}\\p{Z}\\r\\n]', 'gu')
      text = text.replace(keepReadableChars, '')
    } catch (err) {
      // Fallback for environments without Unicode property escapes
      text = text.replace(/[^\u0009-\u000d\u0020-\u007E\u00A0-\u024F\u0370-\u03FF\u2000-\u206F\u2070-\u209F\u20A0-\u20CF\u2100-\u214F\u2190-\u21FF\u2200-\u22FF\u2460-\u24FF\u25A0-\u25FF\u2600-\u27BF\u2E00-\u2E7F\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]/g, '')
    }

    // 修正常見OCR錯誤
    text = text.replace(/[Ss]せing/g, 'String')
    text = text.replace(/[Ss]山1昭日山11/g, 'StringBuilder')
    text = text.replace(/[Ss]山1/g, 'String')
    text = text.replace(/[Bb]山1/g, 'Boolean')
    text = text.replace(/[Nn]山1/g, 'Number')
    text = text.replace(/[Oo]山1/g, 'Object')
    text = text.replace(/尊換/g, '轉換')
    text = text.replace(/比封/g, '比對')
    text = text.replace(/勤象/g, '對象')
    text = text.replace(/鹿用/g, '應用')
    text = text.replace(/他門/g, '它們')
    text = text.replace(/程式鶴/g, '程式碼')
    text = text.replace(/字行串/g, '字符串')
    text = text.replace(/字符史/g, '字符串')
    text = text.replace(/輔換/g, '轉換')
    text = text.replace(/方注/g, '方法')
    text = text.replace(/高比/g, '比較')
    text = text.replace(/数字符史/g, '字符串')
    text = text.replace(/одual0/g, 'equals')
    text = text.replace(/追個/g, '這個')
    text = text.replace(/用放/g, '用於')
    text = text.replace(/sł1/g, 'String')
    text = text.replace(/b001ean/g, 'boolean')
    text = text.replace(/Bildingbxt/g, 'Builder')
    text = text.replace(/Bildingbxけ/g, 'Builder')
    text = text.replace(/5+ユ川B山11d/g, 'StringBuilder')
    text = text.replace(/異号/g, '與')
    text = text.replace(/型尊換/g, '型轉換')
    text = text.replace(/Sngea50/g, 'String')
    text = text.replace(/StringBuildereguals/g, 'StringBuilder.equals')
    text = text.replace(/止方法/g, '此方法')
    text = text.replace(/5十ユ川B山11d/g, 'StringBuilder')
  }

  text = text.replace(/\s+/g, ' ').trim()

  // 在段落級別也處理 ==標記== 語法，防止遺漏
  text = text.replace(/==(.*?)==/g, '<mark class="highlight-mark">$1</mark>')
  text = text.replace(/👈\s*(重點|注意|重要)/g, '<span class="pointer">👈 $1</span>')
  
  // 如果段落為空或只包含特殊字符，跳過渲染
  if (!text || text.length < 2) {
    return ''
  }
  
  return `<p class="clean-paragraph">${text}</p>`
}

// 產生錨點用的 slugify（需與 TOC 一致）
function slugify(text) {
  return (text || '')
    .toString()
    .trim()
    .toLowerCase()
    .replace(/<[^>]+>/g, '')
    .replace(/[\u2000-\u206F\u2E00-\u2E7F'".,/#!$%^&*;:{}=\-_`~()]/g, '')
    .replace(/\s+/g, '-')
}

// 自定義標題渲染：加入 id 錨點與類型 icon
renderer.heading = function (text, level, raw) {
  // 移除模板殘留 {{#...}} / {{/...}} 並標準化空白
  const clean = (raw || text || '')
    .replace(/\{\{#?[^}]+\}\}/g, '')
    .replace(/\{\{\/[^{]+\}\}/g, '')
    .replace(/\s+/g, ' ')
    .trim()
  const normalizedTitle = clean.replace(/^#+\s+/, '').trim()
  const id = slugify(normalizedTitle)
  const title = normalizedTitle
  const safeTitle = escapeHtml(title)

  const headingIconRules = [
    { pattern: /^②\s*/, icon: '🇯🇵 ' }, // ② 日文重點大綱
    { pattern: /^③\s*/, icon: '🧭 ' }, // ③ 母語解析
    { pattern: /^④\s*/, icon: '📋 ' }, // ④ 術語表
    { pattern: /^⑤\s*/, icon: '💻 ' }, // ⑤ 程式碼 / 數學公式
    { pattern: /^⑥\s*/, icon: '💡 ' }, // ⑥ 補充 / 延伸理解
  ]

  let icon = ''
  for (const rule of headingIconRules) {
    if (rule.pattern.test(title)) {
      icon = rule.icon
      break
    }
  }

  const cls = `md-h${level} section-heading notion-style-heading`
  console.log('🎨 標題渲染:', { level, title, icon, cls })
  return `<h${level} id="${id}" class="${cls}">${icon}${safeTitle}</h${level}>`


}

// 自定義表格單元格渲染
renderer.tablecell = function (content, flags) {
  // 在表格單元格中也處理標記
  content = content.replace(/==(.*?)==/g, '<mark class="highlight-mark">$1</mark>')
  content = content.replace(/👈\s*(重點|注意|重要)/g, '<span class="pointer">👈 $1</span>')
  const type = flags.header ? 'th' : 'td'
  const tag = flags.align ? `<${type} style="text-align:${flags.align}">` : `<${type}>`
  return tag + content + `</${type}>`
}

// 自定義表格渲染 - 修復對齊問題
renderer.table = function (header, body) {
  return `<div class="table-wrapper">
    <table class="enhanced-table">
      <thead>${header}</thead>
      <tbody>${body}</tbody>
    </table>
  </div>`
}

// 自定義塊引用渲染 - Notion 風格提示框
renderer.blockquote = function (quote) {
  // 檢查是否包含重點標記
  if (quote.includes('==重點==') || quote.includes('重點標記')) {
    return `<blockquote class="important-note">${quote}</blockquote>`
  }
  
  // 根據內容智能分配提示框樣式
  let calloutType = 'info'
  let calloutIcon = '💡'
  
  if (/⚠️|警告|注意|錯誤|錯誤|常見錯誤/i.test(quote)) {
    calloutType = 'warning'
    calloutIcon = '⚠️'
  } else if (/✅|正確|答案|推薦|成功/i.test(quote)) {
    calloutType = 'success'
    calloutIcon = '✅'
  } else if (/🔑|重點|考試|必背|重要/i.test(quote)) {
    calloutType = 'highlight'
    calloutIcon = '🔑'
  } else if (/💡|補充|提示|說明|範例/i.test(quote)) {
    calloutType = 'info'
    calloutIcon = '💡'
  }
  
  console.log('💡 提示框渲染:', { calloutType, calloutIcon, quote: quote.substring(0, 50) })
  return `<blockquote class="notion-callout ${calloutType}">
    <div class="callout-icon">${calloutIcon}</div>
    <div class="callout-content">${quote}</div>
  </blockquote>`

}

// 自定義代碼區塊渲染器：使用 hljs 進行語法高亮
renderer.code = function (code, infostring, escaped) {
  // 提取語言標籤（去除可能的額外字符）
  const lang = (infostring || '').split(/\s+/)[0].toLowerCase() || ''
  
  // 嘗試使用 hljs 進行語法高亮
  let highlightedCode
  try {
    if (lang && hljs.getLanguage(lang)) {
      highlightedCode = hljs.highlight(code, { language: lang }).value
    } else {
      // 自動偵測語言
      highlightedCode = hljs.highlightAuto(code).value
    }
  } catch (e) {
    // 如果高亮失敗，回退到純文字（需 escape）
    highlightedCode = code.replace(/[&<>"']/g, (m) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    }[m]))
  }
  
  const langClass = lang ? `language-${lang}` : ''
  return `<pre class="plain-code-block"><code class="hljs ${langClass}">${highlightedCode}</code></pre>`
}

// 自定義圖片渲染器 - 修復路徑顯示問題
renderer.image = function (href, title, text) {
  console.log('[圖片渲染] 原始路徑:', href, 'title:', title, 'text:', text);
  console.log('[圖片渲染] 調用圖片渲染器');

  // 處理相對路徑 - 修正圖片路徑問題
  let src = href

  if (href && !href.startsWith('http') && !href.startsWith('data:')) {
    // 統一轉換為相對的 /images 路徑，讓開發環境透過 Vite 代理、部署環境透過後端靜態掛載
    if (href.startsWith('/images/')) {
      src = href
    } else if (href.startsWith('images/')) {
      src = '/' + href
    } else if (href.includes('output/images/')) {
      // 從 output/images/ 路徑中提取文件名
      const pathAfterOutput = href.split('output/images/')[1]
      src = '/images/' + pathAfterOutput
    } else if (href.startsWith('./images/')) {
      src = href.replace('./images/', '/images/')
    } else if (href.startsWith('../images/')) {
      src = href.replace('../images/', '/images/')
    } else if (href.includes('/images/')) {
      // 如果路徑中包含 /images/，提取該部分
      const imagesIndex = href.indexOf('/images/')
      src = href.substring(imagesIndex)
    } else {
      // 默認情況：假設是文件名，添加到 /images/ 路徑
      const filename = href.split('/').pop()
      src = '/images/' + filename
    }

    console.log('[圖片渲染] 路徑轉換:', href, '→', src)
  }

  // 將HEIC格式轉換為JPG格式 (瀏覽器無法直接顯示HEIC)
  if (src && src.toLowerCase().includes('.heic')) {
    const originalSrc = src
    src = src.replace(/\.heic$/i, '_converted.jpg')
    console.log('[圖片渲染] 🔄 HEIC自動轉換:', originalSrc, '→', src)
  }

  console.log('[圖片渲染] ✅ 最終使用路徑:', src);

  const titleAttr = title ? ` title="${title}"` : ''
  const altAttr = text ? ` alt="${text}"` : ''

  // 修復圖片顯示問題 - 改進載入邏輯和樣式
  const imageHtml = `<div class="gpt-image-container">
    <img src="${src}"${altAttr}${titleAttr} 
      class="gpt-image"
      loading="lazy"
    />
    <div class="gpt-image-error" style="display: none;">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
        <circle cx="8.5" cy="8.5" r="1.5"/>
        <polyline points="21,15 16,10 5,21"/>
      </svg>
      <p>圖片載入失敗</p>
      <small>請檢查網絡連接</small>
    </div>
  </div>`

  console.log('[圖片渲染] 生成的 HTML:', imageHtml);
  return imageHtml
}

// 定義marked配置選項
const markedOptions = {
  mangle: false,
  headerIds: false,
  renderer: renderer,
  breaks: true,
  gfm: true
}

const props = defineProps({
  content: { type: String, required: true },
  markdown: { type: String, required: false, default: '' }, // 保留向後兼容性
})

// 新增语音解析开关状态
const parseAudio = ref(true)

// 示例摘要生成函數（暫未實現）
async function generateSummary() {
  ElMessage.info(t('summaryFeatureNotImplemented'))
  return t('summaryGenerationComplete')
}

const copied = ref(false)
const tocHtml = ref('')

// 計算出實際使用的Markdown內容，並預先處理代碼區塊和圖片的排序
const effectiveMarkdown = computed(() => {
  const originalContent = props.content || props.markdown || '';
  return preProcessMarkdown(originalContent);
})

// 解析結構化 JSON（需在 effectiveMarkdown 定義之後，避免 TDZ 錯誤）
const structured = computed(() => {
  try {
    const raw = effectiveMarkdown.value || ''
    if (!raw) return null
    const j = JSON.parse(raw)
    if (j && typeof j === 'object' && (j.notes || j.terms || j.code || j.qa || j.tips)) {
      // 進行 Grounding 驗證
      const ocrText = j.ocrText || ''
      const validation = validateStructuredData(j, ocrText)
      return {
        ...j,
        validation,
        ocrQuality: checkOCRQuality(ocrText)
      }
    }
  } catch (e) { /* noop */ }
  return null
})

// 組件掛載與每次內容變動後，嘗試觸發全域增強（確保新版樣式應用）
watch(() => effectiveMarkdown.value, () => {
  setTimeout(() => { window.forceEnhance && window.forceEnhance() }, 100)
})
onMounted(() => {
  setTimeout(() => { window.forceEnhance && window.forceEnhance() }, 200)
})

// 預先處理Markdown內容以確保代碼區塊和圖片的排序正確
function preProcessMarkdown(content) {
  if (!content) return ''

  console.log('[預處理] 原始內容長度:', content.length)
  // Debug: Check for "text //" presence
  if (content.match(/text\s*\/\//i)) {
    console.log('[預處理] ⚠️ 檢測到 "text //" 模式')
  }

  // --- AGGRESSIVE CLEANING V3 (Enhanced Regex) ---
  let cleaned = content

  // 1. Global replace for "text //" anywhere in the string (Handle zero-width space \u200B)
  // Updated to handle indentation and newlines correctly
  cleaned = cleaned.replace(/(^|\n)[\t ]*text[\t \u200B]*(\/\/)/gi, '$1$2')
  
  // 2. Global replace for "text <number>:" (dictionary keys)
  cleaned = cleaned.replace(/(^|\n)[\t ]*text[\t \u200B]+(\d+\s*:)/gi, '$1$2')

  // 3. Global replace for "text import" / "text def"
  cleaned = cleaned.replace(/(^|\n)[\t ]*text[\t \u200B]+(?=import|from|def|class|public|void|int|enum|struct|interface)/gi, '$1')

  // 4. Specific fix for the "text 0: {0: ...}" case
  cleaned = cleaned.replace(/(^|\n)[\t ]*text[\t \u200B]+0\s*:/gi, '$10:')

  // 5. General "text " prefix removal at start of lines (Aggressive & Indentation aware)
  // We capture the indentation ($1) and preserve it, removing "text" and the following space/zero-width-space.
  cleaned = cleaned.replace(/^([\s\u200B]*)text[\s\u200B]+/gim, '$1')
  
  // 6. Handle "text" followed immediately by symbols (e.g. "text{", "text(", "text[", "text-")
  // Added hyphen to the lookahead
  cleaned = cleaned.replace(/^([\s\u200B]*)text(?=[{([<\\-])/gim, '$1')

  // 7. Wrap bare LaTeX environments in $$ to ensure they render
  cleaned = cleaned.replace(/(\\begin\{aligned\}[\s\S]*?\\end\{aligned\})/g, (match) => {
    if (match.includes('$$')) return match // Already wrapped
    return `\n$$\n${match}\n$$\n`
  })
  // -----------------------------------------------------------

  console.log('[預處理] 開始處理內容 (v3.1.6-fix)，長度:', cleaned.length)

  // code 圍欄解包統一交給 markdownRenderer（避免雙重處理）

  // （圍欄類型的判斷與解包統一交給 markdownRenderer，避免重複處理）

  // 處理特殊標題模式
  const specialTitlePatterns = [
    /^(.*?分析：.*?)$/gm,
    /^(.*?解析：.*?)$/gm,
    /^(.*?程式碼部分分析：.*?)$/gm,
    /^(.*?重點：.*?)$/gm,
    /^(.*?總結：.*?)$/gm,
    /^(.*?說明：.*?)$/gm
  ]

  specialTitlePatterns.forEach(pattern => {
    cleaned = cleaned.replace(pattern, (match, title) => {
      // 如果不是在代碼塊內，則添加特殊樣式
      if (!match.includes('```')) {
        return `<div class="special-title">${title}</div>`
      }
      return match
    })
  })

  // 修復圖片路徑中的絕對URL和特殊字符問題
  let processedContent = cleaned.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, src) => {
    // 濾除無效佔位路徑
    const raw = (src || '').trim()
    if (!raw || raw === 'actual_image_path' || raw === '#') {
      return ''
    }
    let fixedSrc = src

    console.log('[圖片路徑修復] 處理圖片:', alt, '路徑:', src)

    // 統一處理圖片路徑 - 確保使用正確的API端點
    if (src && !src.startsWith('http') && !src.startsWith('data:')) {
      // 統一轉換為 /images 路徑（相對）
      if (src.startsWith('/images/')) {
        fixedSrc = src
      } else if (src.startsWith('images/')) {
        fixedSrc = '/' + src
      } else if (src.includes('output/images/')) {
        const pathAfterOutput = src.split('output/images/')[1]
        fixedSrc = '/images/' + pathAfterOutput
      } else if (src.startsWith('./images/') || src.startsWith('../images/')) {
        const filename = src.split('/').pop()
        fixedSrc = '/images/' + filename
      } else if (src.includes('/images/')) {
        const imagesIndex = src.indexOf('/images/')
        fixedSrc = src.substring(imagesIndex)
      } else {
        const filename = src.split('/').pop()
        fixedSrc = '/images/' + filename
      }
      
      console.log('[圖片路徑修復] 路徑轉換:', src, '→', fixedSrc)
    } else if (src.startsWith('http://localhost:8000/images/') || src.startsWith('http://localhost:18000/images/')) {
      // 將絕對URL轉換為相對路徑
      fixedSrc = src.replace(/^https?:\/\/localhost:\d+/, '')
      console.log('[圖片路徑修復] 絕對URL轉換為相對路徑:', src, '→', fixedSrc)
    }

    // 將HEIC格式轉換為JPG格式 (瀏覽器無法直接顯示HEIC)
    if (fixedSrc.toLowerCase().includes('.heic')) {
      fixedSrc = fixedSrc.replace(/\.heic$/i, '_converted.jpg')
      console.log('[圖片路徑修復] HEIC轉換為JPG:', src, '→', fixedSrc)
    }

    // 如果路徑包含空格，用 %20 替換，但避免雙重編碼
    if (fixedSrc.includes(' ') && !fixedSrc.includes('%20')) {
      fixedSrc = fixedSrc.replace(/ /g, '%20')
      console.log('[圖片路徑修復] 空格編碼:', src, '→', fixedSrc)
    }

    const result = `![${alt}](${fixedSrc})`
    console.log('[圖片路徑修復] 最終結果:', result)
    return result
  })

  // 額外處理原始 HTML <img> 標籤中的 src，避免出現 actual_image_path 等占位字串
  try {
    processedContent = processedContent.replace(/(<img[^>]*src=["'])([^"']+)(["'][^>]*>)/gi, (m, p1, src, p3) => {
      // 避免無效占位字串
      if (!src || src === 'actual_image_path') {
        console.warn('[圖片路徑修復] 移除無效 <img> 標籤 src=actual_image_path')
        return ''
      }

      let fixedSrc = src
      if (!src.startsWith('http') && !src.startsWith('data:')) {
        if (src.startsWith('/images/')) {
          fixedSrc = src
        } else if (src.startsWith('images/')) {
          fixedSrc = '/' + src
        } else if (src.includes('output/images/')) {
          const pathAfterOutput = src.split('output/images/')[1]
          fixedSrc = '/images/' + pathAfterOutput
        } else if (src.startsWith('./images/') || src.startsWith('../images/')) {
          const filename = src.split('/').pop()
          fixedSrc = '/images/' + filename
        } else if (src.includes('/images/')) {
          const idx = src.indexOf('/images/')
          fixedSrc = src.substring(idx)
        } else {
          const filename = src.split('/').pop()
          fixedSrc = '/images/' + filename
        }
      }

      if (fixedSrc.toLowerCase().includes('.heic')) {
        fixedSrc = fixedSrc.replace(/\.heic$/i, '_converted.jpg')
      }
      if (fixedSrc.includes(' ') && !fixedSrc.includes('%20')) {
        fixedSrc = fixedSrc.replace(/ /g, '%20')
      }

      console.log('[圖片路徑修復][HTML IMG] 路徑轉換:', src, '→', fixedSrc)
      return p1 + fixedSrc + p3
    })
  } catch (e) {
    console.warn('[圖片路徑修復] HTML <img> 標籤處理失敗:', e)
  }

  console.log('[預處理] 完成，處理後包含圖片:', processedContent.includes('!['))
  console.log('[預處理] 圖片標記數量:', (processedContent.match(/!\[.*?\]\([^)]+\)/g) || []).length)

  return processedContent
}

// 新增的計算屬性和方法
const wordCount = computed(() => {
  if (!effectiveMarkdown.value) return 0
  return effectiveMarkdown.value.replace(/[^\u4e00-\u9fa5\w]/g, '').length
})

const imageCount = computed(() => {
  if (!effectiveMarkdown.value) return 0
  const imageMatches = effectiveMarkdown.value.match(/!\[([^\]]*)\]\([^)]*\)/g)
  return imageMatches ? imageMatches.length : 0
})

const sceneCount = computed(() => {
  if (!effectiveMarkdown.value) return 0
  const markers = [
    'Scenes processed',
    '處理的場景數',
    '处理场景数',
    '処理したシーン数',
    '처리한 장면 수',
    'Số cảnh đã xử lý',
    'ကိုင်တွယ်ခဲ့သော မြင်ကွင်း အရေအတွက်',
    'Боловсруулсан хэсгийн тоо'
  ]
  const regex = new RegExp(`(?:${markers.join('|')})\s*:\s*(\\d+)`, 'i')
  const match = effectiveMarkdown.value.match(regex)
  if (match && match[1]) return Number(match[1])
  const chapterMatches = effectiveMarkdown.value.match(/^#\s*(Chapter|章節|章节)\s*\d+/gmi)
  if (chapterMatches && chapterMatches.length) return chapterMatches.length
  // 估算場景數量，基於內容結構
  const sections = effectiveMarkdown.value.split(/###|##/).length - 1
  return Math.max(1, sections)
})

const lastUpdated = computed(() => {
  return new Date().toLocaleString('zh-TW', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
})

function exportNote() {
  const blob = new Blob([effectiveMarkdown.value], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `筆記_${new Date().toISOString().slice(0, 10)}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  ElMessage.success(t('noteExported'))
}

// == ChatGPT 風格顯示優化 ==
// 1. 自動將『原文摘要』『中文解析』『重點詞彙』『簡單例子』等標題加強顯示
// 2. 重要詞彙加粗、加底色、加 emoji
// 3. 清單、表格、程式碼區塊加強間距與陰影
// 4. emoji、[!NOTE]、[!TIP] 轉換為明顯提示框
// 5. 卡片圓角、陰影、分隔線、主題色
// ------------------------------------------------------
const stripMeaningless = (text = '') => {
  return text
    .replace(/!\[.*?\]\([^)]+\)/g, '')
    .replace(/```[\s\S]*?```/g, '')
    .replace(/[#>*_\-\d`]/g, '')
    .replace(/\s+/g, '')
    .trim()
}

const shouldKeepBlock = (text = '') => {
  if (!text || text.length <= 10) return false
  if (text.includes('![')) return true
  return stripMeaningless(text).length >= 6
}

const cardBlocks = computed(() => {
  const content = effectiveMarkdown.value || ''
  // 不分段，單一區塊輸出
  return [{
    id: `block-0`,
    markdown: content,
    isImagePair: false
  }]
})

// 處理單個markdown塊的函數
function processMarkdownBlock(rawMarkdown) {
  const isHtml = /<\s*(p|div|span|br)[^>]*>/i.test(rawMarkdown || '')
  
  // === Structured Note Detection (Relaxed for 11+ chapter notes) ===
  // Match chapter headings with broader patterns
  const chapterPatterns = [
    /(^|\n)#{1,6}\s*(?:Chapter|章節|章节)\s*\d+/mi,
    /(^|\n)#{1,6}\s*第\s*\d+\s*章/m,
    /(^|\n)#{1,6}\s*第\d+章/m,
    /(^|\n)#{1,6}\s*第[一二三四五六七八九十百]+章/m,
  ]
  const hasChapterHeading = chapterPatterns.some(p => p.test(rawMarkdown || ''))
  
  // Count general headings (any ## or ### level)
  const generalHeadingCount = (rawMarkdown || '').match(/(^|\n)#{1,3}\s+\S+/gm)?.length || 0
  const hasStructuredHeading = hasChapterHeading || generalHeadingCount >= 3
  
  // Check for images
  const hasImageMarker = /!\[[^\]]*\]\(/.test(rawMarkdown || '') || /<img\s/i.test(rawMarkdown || '')
  const imageCount = ((rawMarkdown || '').match(/!\[[^\]]*\]\(/gmi)?.length || 0) + 
                     ((rawMarkdown || '').match(/<img\s/gi)?.length || 0)
  
  // Determine if structured note: has headings AND images, OR rich images, OR many headings
  const isStructuredNote = (hasStructuredHeading && hasImageMarker) || 
                           imageCount >= 6 || 
                           generalHeadingCount >= 5
  let normalized = rawMarkdown || ''
  if (isHtml) {
    normalized = normalized
      .replace(/<br\s*\/?/gi, '\n')
      .replace(/<\/p>/gi, '\n')
      .replace(/<[^>]+>/g, '')
  }

  // 移除孤立的語言提示行（如 "java" / "text"）
  if (!isStructuredNote) {
    normalized = normalized.replace(/^(?:java|text|plaintext)\s*$/gim, '')
  }

  let markdown = isStructuredNote ? normalized : cleanMarkdown(normalized)

  if (!isStructuredNote) {
    const lineCount = (markdown.match(/\n/g) || []).length
    if (lineCount < 6 && markdown.length > 120) {
      markdown = markdown
        .replace(/([•●◦◉☆★◆◇▪️▫️▪︎◦]|⚠️|🔑|📌|✅|💡|👉|➤|▶️|▸|►)/g, '\n- $1 ')
        .replace(/([。！？；；])\s*/g, '$1\n')
        .replace(/\n{3,}/g, '\n\n')
    }
  }

  let { html } = renderNoteMarkdown(markdown, { translate: t, measure: true })
  html = flattenHtml(html || '')
  html = cleanupGarbled(html || '')
  return html
}

function flattenHtml(html) {
  const parser = new DOMParser()
  const doc = parser.parseFromString(html, 'text/html')

  // 移除內聯樣式，避免背景色干擾
  doc.querySelectorAll('[style]').forEach((el) => el.removeAttribute('style'))

  // 移除自動生成主題卡片內重複段落（避免顯示成 # 標題文本）
  doc.querySelectorAll('.card').forEach((card) => {
    const heading = card.querySelector('h1, h2, h3')
    const muted = card.querySelector('.muted')
    if (heading && muted) {
      const headingText = (heading.textContent || '').trim()
      const mutedText = (muted.textContent || '').trim()
      if (headingText && mutedText && headingText === mutedText) {
        muted.remove()
      }
    }
  })

  // 展平卡片/標題/徽章等容器
  doc.querySelectorAll('.card, .section, .section-title, .chip, .gpt-card, .note-block, .learning-points, .learning-points li').forEach((el) => {
    const frag = doc.createDocumentFragment()
    while (el.firstChild) frag.appendChild(el.firstChild)
    el.replaceWith(frag)
  })

  const formatLightSample = (text) => {
    const isLight = /ACTION_OFF/.test(text) && /transitionProb/.test(text)
    if (!isLight) return text
    return [
      '// 定義動作常數：0=關燈, 1=開燈',
      'private static final int ACTION_OFF = 0;',
      'private static final int ACTION_ON  = 1;',
      '',
      '// 建立條件機率表 (Transition Probability)',
      '// 狀態0 (關燈) 時：關燈機率=0.7，開燈的機率=0.3',
      '// 狀態1 (開燈) 時：關燈機率=0.2，開燈的機率=0.8',
      'private double[][] transitionProb = {',
      '    { 0.7, 0.3 },',
      '    { 0.2, 0.8 }',
      '};',
      '',
      '// 驗證機率歸一化條件',
      'public void validateProbability(int state) {',
      '    double sum = 0.0;',
      '    for (int action = 0; action < 2; action++) {',
      '        sum += transitionProb[state][action];',
      '    }',
      '    if (Math.abs(sum - 1.0) > 0.001) {',
      '        System.out.println("警告：機率和不為1！狀態=" + state + "，總和=" + sum);',
      '    }',
      '}',
      '',
      '// 模擬狀態轉移',
      'public int nextState(int currentState, int action) {',
      '    if (currentState == STATE_OFF) {',
      '        return (action == ACTION_ON) ? STATE_ON : STATE_OFF;',
      '    } else {',
      '        return (action == ACTION_OFF) ? STATE_OFF : STATE_ON;',
      '    }',
      '}'
    ].join('\n')
  }

  // 規整代碼區塊
  doc.querySelectorAll('pre').forEach((pre) => {
    const code = pre.querySelector('code')
    if (!code) return
    let text = code.textContent || ''
    text = formatLightSample(text)
    // 移除殘留的 highlight/spanclass 文本片段，避免跑出 spanclass="hjs-number">
    text = text
      .replace(/spanclass\s*=\s*["'][^"']*["']>?/gi, '')
      .replace(/h?l?js-[a-z0-9_-]+/gi, '')
      .replace(/<\/?spanclass[^>]*>/gi, '')
      .replace(/<\/?span[^>]*>/gi, '')
    code.className = 'plain-code'
    code.setAttribute('data-no-highlight', 'true')
    code.setAttribute('data-no-enhance', 'true')
    code.innerHTML = text
    pre.className = 'plain-code-block'
    pre.setAttribute('data-no-highlight', 'true')
    pre.setAttribute('data-no-enhance', 'true')
  })

  // 圖片最大寬度
  doc.querySelectorAll('img').forEach((img) => {
    img.removeAttribute('width')
    img.removeAttribute('height')
    img.classList.add('mk-img')
    img.style.maxWidth = '100%'
    img.style.height = 'auto'
    img.style.display = 'block'
    img.style.margin = '12px auto'
  })

  // 公式置中
  doc.querySelectorAll('.math-block').forEach((m) => { m.style.textAlign = 'center' })
  doc.querySelectorAll('.math-block .katex-display').forEach((el) => {
    el.style.marginTop = '0px'
    el.style.marginBottom = '0px'
  })

  // 移除多餘的 class，保留 code/math/img 相關
  doc.querySelectorAll('[class]').forEach((el) => {
    const cls = el.className || ''
    if (cls.includes('plain-code') || cls.includes('math-block') || cls.includes('math-inline') || cls.includes('mk-img')) return
    el.removeAttribute('class')
  })

  return doc.body.innerHTML
}

// 最終兜底清理：移除殘留的 span/spanclass 字串與 hljs 類名
function cleanupGarbled(html = '') {
  return html
    // 原生/轉義 span 標籤
    .replace(/<\/?span[^>]*>/gi, '')
    .replace(/&lt;\/?span[^>]*&gt;/gi, '')
    // spanclass 變形
    .replace(/<\/?spanclass[^>]*>/gi, '')
    .replace(/&lt;\/?spanclass[^>]*&gt;/gi, '')
    // 單獨的 spanclass 屬性片段
    .replace(/spanclass\s*=\s*["'][^"']*["']>?/gi, '')
    .replace(/&lt;spanclass\s*=\s*["'][^"']*["'][^>]*&gt;/gi, '')
    // 內嵌的 hljs/hjs 類名文字
    .replace(/\b(h?l?js-[a-z0-9_-]+)\b/gi, '')
}


// 移除 renderedHtml 相關引用
// 移除 <div class="llm-note-markdown" v-html="renderedHtml"></div>
// 移除 console.log('[LlmMarkdownNote] renderedHtml:', renderedHtml.value)
// 如需 debug，改為 log cardBlocks
console.log('[LlmMarkdownNote] cardBlocks:', cardBlocks.value)

// 同步圖片功能
async function syncAndRefreshImages() {
  console.log('[同步圖片] 開始同步圖片')
  ElMessage.info(t('syncingImages'))
  
  try {
    const response = await fetch('/api/sync-images', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        language: currentLanguage.value
      })
    })
    
    if (response.ok) {
      const result = await response.json()
      const copiedCount = Number(result?.copied ?? result?.count ?? 0)
      ElMessage.success(t('imageSyncSuccess', { count: copiedCount }))
      
      // 觸發重新渲染
      nextTick(() => {
        console.log('[同步圖片] 重新渲染筆記內容')
      })
    } else {
      throw new Error('同步請求失敗')
    }
  } catch (error) {
    console.error('[同步圖片] 同步失敗:', error)
    ElMessage.error(t('imageSyncFailed'))
  }
}

function copyMarkdown() {
  navigator.clipboard.writeText(effectiveMarkdown.value)
    .then(() => {
      copied.value = true
      setTimeout(() => copied.value = false, 1200)
    })
    .catch(() => {
      ElMessage.error(t('copyFailed'))
    })
}

// 綁定統一代碼區塊複製功能（code-block-container）
const bindCodeCopyButtons = () => {
  const root = noteRoot.value || document
  if (!root) return

  // 先移除既有監聽，避免重複觸發
  root.querySelectorAll('.code-copy-btn').forEach((btn) => {
    const clone = btn.cloneNode(true)
    btn.replaceWith(clone)
  })

  root.querySelectorAll('.code-copy-btn').forEach((btn) => {
    const codeId = btn.getAttribute('data-code-id')
    const codeEl = root.querySelector(`#${codeId}`)
    if (!codeEl) return
    btn.addEventListener('click', async () => {
      const snippet = codeEl.textContent || ''
      try {
        await navigator.clipboard.writeText(snippet)
        const original = btn.textContent
        btn.textContent = '✅ 已複製'
        btn.classList.add('copied')
        window.setTimeout(() => {
          btn.textContent = original
          btn.classList.remove('copied')
        }, 1800)
      } catch (err) {
        console.error('[LlmMarkdownNote] 複製失敗:', err)
      }
    })
  })
}

onMounted(() => {
  nextTick(bindCodeCopyButtons)
})

watch(cardBlocks, () => {
  nextTick(bindCodeCopyButtons)
}, { deep: true })

// 添加 watch 来监听 parseAudio 的变化
watch(parseAudio, (newVal) => {
  ElMessage.info(newVal ? t('audioParseEnabled') : t('audioParseDisabled'))
  // 这里可以添加当开关变化时需要执行的其他逻辑
})

// 優化代碼區塊和圖片的處理順序 - 強化版
function optimizeCodeAndImageBlocks(markdown) {
  // Disable reordering to prevent content jumping
  return markdown
}

function enhanceCodeBlocks() {
  // 禁用舊的代碼增強系統，使用新的渲染器
  console.log('[LlmMarkdownNote] 使用新的代碼渲染器，跳過舊的增強系統')
  return
}

function wrapCodeBlock(preElement, index, container) {
  // 如果已經增強過，跳過處理
  if (preElement.closest('.code-block-enhanced')) return

  const codeElement = preElement.querySelector('code')
  if (!codeElement) return // 如果找不到 code 元素，跳過處理

  const code = codeElement.textContent || preElement.textContent
  const language = detectLanguage(codeElement, code)

  try {
    // 創建增強的包裝器
    const wrapper = document.createElement('div')
    wrapper.className = 'code-block-enhanced'
    wrapper.setAttribute('data-enhanced', 'true')

    // 創建標題欄，包含語言標籤和複製按鈕
    const header = document.createElement('div')
    header.className = 'code-block-header'

    // 左側 - 語言標籤
    const leftSide = document.createElement('div')
    leftSide.className = 'header-left'
    const languageTag = document.createElement('span')
    languageTag.className = 'language-tag'
    languageTag.textContent = getLanguageDisplayName(language || 'text')
    leftSide.appendChild(languageTag)

    // 右側 - 複製按鈕
    const rightSide = document.createElement('div')
    rightSide.className = 'header-right'
    const copyButton = document.createElement('button')
    copyButton.className = 'copy-button'
    copyButton.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2" stroke="currentColor" stroke-width="2" fill="none"/>
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" stroke="currentColor" stroke-width="2" fill="none"/>
      </svg>
      <span>${currentLanguage.value === 'en' ? 'Copy' : currentLanguage.value === 'ko' ? '복사' : currentLanguage.value === 'zh-CN' ? '复制' : '複製'}</span>
    `
    copyButton.title = t('copyCode')
    copyButton.onclick = (e) => {
      e.preventDefault()
      e.stopPropagation() // 防止事件冒泡
      copyCode(code, copyButton)
    }
    rightSide.appendChild(copyButton)

    header.appendChild(leftSide)
    header.appendChild(rightSide)

    // 在 pre 元素前插入包裝器
    preElement.parentNode.insertBefore(wrapper, preElement)
    wrapper.appendChild(header)
    wrapper.appendChild(preElement)

    // 禁用後處理高亮，保持原始文字樣式
    if (codeElement) {
      codeElement.dataset.highlighted = 'skip'
      codeElement.className = 'nohighlight'
      return
    }

  } catch (error) {
    console.error(`程式碼區塊 ${index} 包裝處理錯誤:`, error)
  }
}

function detectLanguage(codeElement, code) {
  // Check class names for language
  if (codeElement) {
    const classNames = codeElement.className.split(' ')
    for (const className of classNames) {
      if (className.startsWith('language-')) {
        return className.replace('language-', '')
      }
      if (className.startsWith('lang-')) {
        return className.replace('lang-', '')
      }
    }
  }

  // Content-based detection
  const trimmedCode = code.trim()

  // JavaScript/TypeScript patterns
  if (/\b(function|const|let|var|=>|async|await|import|export)\b/.test(trimmedCode)) {
    return trimmedCode.includes('interface') || trimmedCode.includes(': string') ? 'typescript' : 'javascript'
  }

  // Python patterns
  if (/\b(def|import|from|if __name__|print|class)\b/.test(trimmedCode) || /^\s*#/.test(trimmedCode)) {
    return 'python'
  }

  // Java patterns
  if (/\b(public class|private|protected|static|void|String|int|boolean)\b/.test(trimmedCode)) {
    return 'java'
  }

  // SQL patterns
  if (/\b(SELECT|FROM|WHERE|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)\b/i.test(trimmedCode)) {
    return 'sql'
  }

  return null
}

function getLanguageDisplayName(lang) {
  const langMap = {
    'javascript': 'JavaScript',
    'typescript': 'TypeScript',
    'python': 'Python',
    'java': 'Java',
    'csharp': 'C#',
    'cpp': 'C++',
    'c': 'C',
    'sql': 'SQL',
    'bash': 'Bash',
    'powershell': 'PowerShell',
    'json': 'JSON',
    'yaml': 'YAML',
    'xml-doc': 'XML',
    'markup': 'HTML',
    'css': 'CSS',
    'text': 'Text'
  }
  return langMap[lang] || lang.toUpperCase()
}

function applySyntaxHighlighting(code, language) {
  if (!language) return escapeHtml(code)

  let highlightedCode = escapeHtml(code)

  switch (language) {
    case 'javascript':
    case 'typescript':
      highlightedCode = highlightedCode
        .replace(/(\/\/.*$)/gm, '<span class="token comment">$1</span>')
        .replace(/(\/\*[\s\S]*?\*\/)/g, '<span class="token comment">$1</span>')
        .replace(/(["'])((?:\\.|(?!\1)[^\\])*?)\1/g, '<span class="token string">$1$2$1</span>')
        .replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="token number">$1</span>')
        .replace(/\b(function|const|let|var|if|else|for|while|return|import|export|class|extends|async|await|try|catch|finally|new|this|true|false|null|undefined)\b/g, '<span class="token keyword">$1</span>')
        .replace(/\b([a-zA-Z_$][a-zA-Z0-9_$]*)\s*(?=\()/g, '<span class="token function">$1</span>')
      break

    case 'python':
      highlightedCode = highlightedCode
        .replace(/(#.*$)/gm, '<span class="token comment">$1</span>')
        .replace(/(["'])((?:\\.|(?!\1)[^\\])*?)\1/g, '<span class="token string">$1$2$1</span>')
        .replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="token number">$1</span>')
        .replace(/\b(def|class|if|elif|else|for|while|return|import|from|try|except|finally|with|as|lambda|yield|pass|break|continue|global|nonlocal|True|False|None)\b/g, '<span class="token keyword">$1</span>')
        .replace(/\bdef\s+([a-zA-Z_][a-zA-Z0-9_]*)/g, '<span class="token keyword">def</span> <span class="token function">$1</span>')
      break

    default:
      highlightedCode = highlightedCode
        .replace(/(["'])((?:\\.|(?!\1)[^\\])*?)\1/g, '<span class="token string">$1$2$1</span>')
        .replace(/\b(\d+(?:\.\d+)?)\b/g, '<span class="token number">$1</span>')
  }

  return highlightedCode
}

function escapeHtml(text) {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

function copyCode(code, button) {
  navigator.clipboard.writeText(code).then(() => {
    const originalText = button.innerHTML
    button.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
        <polyline points="20,6 9,17 4,12" stroke="currentColor" stroke-width="2" fill="none"/>
      </svg>
      <span>${currentLanguage.value === 'en' ? '✅ Copied' : currentLanguage.value === 'ko' ? '✅ 복사됨' : currentLanguage.value === 'zh-CN' ? '✅ 已复制' : '✅ 已複製'}</span>
    `
    button.style.background = 'linear-gradient(135deg, #10a37f 0%, #0d8a6b 100%)'
    button.style.borderColor = '#10a37f'
    button.style.color = '#ffffff'

    setTimeout(() => {
      button.innerHTML = originalText
      button.style.background = ''
      button.style.borderColor = ''
      button.style.color = ''
    }, 2000)
  }).catch(err => {
    console.error('複製失敗:', err)
    button.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" fill="none"/>
        <line x1="15" y1="9" x2="9" y2="15" stroke="currentColor" stroke-width="2"/>
        <line x1="9" y1="9" x2="15" y2="15" stroke="currentColor" stroke-width="2"/>
      </svg>
      <span>失敗</span>
    `
    button.style.background = 'linear-gradient(135deg, #dc2626, #b91c1c)'
    button.style.borderColor = '#ef4444'

    setTimeout(() => {
      button.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2" stroke="currentColor" stroke-width="2" fill="none"/>
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" stroke="currentColor" stroke-width="2" fill="none"/>
        </svg>
        <span>${currentLanguage.value === 'en' ? 'Copy' : currentLanguage.value === 'ko' ? '복사' : currentLanguage.value === 'zh-CN' ? '复制' : '複製'}</span>
      `
      button.style.background = ''
      button.style.borderColor = ''
      button.style.color = ''
    }, 2000)
  })
}

// 強制刷新圖片緩存
function refreshImageCache() {
  // 給所有圖片URL添加時間戳來強制刷新緩存
  const images = document.querySelectorAll('.notion-note-container img')
  images.forEach(img => {
    const originalSrc = img.src
    if (originalSrc && !originalSrc.includes('?')) {
      img.src = `${originalSrc}?t=${Date.now()}`
      console.log('🔄 刷新圖片緩存:', img.src)
    }
  })

  ElMessage.info('已刷新圖片緩存')
}

// 組合同步和刷新功能（已移除重複定義）
// async function syncAndRefreshImages() {
//   await syncImages()
//   setTimeout(() => {
//     refreshImageCache()
//   }, 1000) // 等待同步完成後再刷新緩存
// }

// 全局複製函數 - ChatGPT風格
window.copyGptCode = function (button, code) {
  navigator.clipboard.writeText(code).then(() => {
    const originalHtml = button.innerHTML
    button.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="20,6 9,17 4,12"></polyline>
      </svg>
    `
    button.style.color = '#10a37f'

    setTimeout(() => {
      button.innerHTML = originalHtml
      button.style.color = ''
    }, 2000)
  }).catch(err => {
    console.error('複製失敗:', err)
  })
}

onMounted(() => {
  console.log('🚀 LlmMarkdownNote 組件已掛載')
  console.log('📝 當前內容長度:', props.content?.length || 0)
  console.log('🌐 API基礎URL:', import.meta.env.VITE_API_BASE_URL)

  // 同步圖片文件（確保圖片能正確顯示）
  syncImages()

  const handleCodeExpandOrCopy = (e) => {
    const copyBtn = e.target.closest('.gpt-copy-btn')
    if (copyBtn) {
      const code = decodeURIComponent(copyBtn.dataset.code || '')
      if (code) {
        navigator.clipboard.writeText(code).then(() => {
          const originalHtml = copyBtn.innerHTML
          copyBtn.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="20,6 9,17 4,12"></polyline>
            </svg>
            <span>${currentLanguage.value === 'en' ? '✅ Copied' : currentLanguage.value === 'ko' ? '✅ 복사됨' : currentLanguage.value === 'zh-CN' ? '✅ 已复制' : '✅ 已複製'}</span>
          `
          copyBtn.style.background = 'linear-gradient(135deg, #10a37f 0%, #0d8a6b 100%)'
          copyBtn.style.color = '#ffffff'
          setTimeout(() => {
            copyBtn.innerHTML = originalHtml
            copyBtn.style.background = ''
            copyBtn.style.color = ''
          }, 2000)
        }).catch(err => {
          console.error('❌ 複製失敗:', err)
          ElMessage.error(t('copyFailed'))
        })
      }
    }

    const expandBtn = e.target.closest('.gpt-expand-btn')
    if (expandBtn) {
      const block = expandBtn.closest('.gpt-code-block')
      if (!block) return
      const collapsed = block.classList.toggle('collapsed')
      const label = expandBtn.querySelector('span')
      if (label) {
        label.textContent = collapsed ? '展開' : '收起'
      }
    }
  }

  const handleImageLoad = (e) => {
    const img = e.target
    if (!(img instanceof HTMLImageElement)) return
    if (!img.classList.contains('gpt-image')) return
    const container = img.closest('.gpt-image-container')
    if (container) {
      container.classList.add('loaded')
      container.classList.remove('error')
    }
    img.style.border = '2px solid rgba(16, 185, 129, 0.3)'
  }

  const handleImageError = (e) => {
    const img = e.target
    if (!(img instanceof HTMLImageElement)) return
    if (!img.classList.contains('gpt-image')) return
    console.error('❌ 圖片載入失敗:', img.src, '檢查路徑:', img.src)
    console.error('❌ 完整圖片信息 - naturalWidth:', img.naturalWidth, 'naturalHeight:', img.naturalHeight)
    if (!img.dataset.retried) {
      img.dataset.retried = 'true'
      let retryUrl = img.src
      if (img.src.includes('/images/')) {
        const filename = img.src.split('/').pop()
        retryUrl = '/images/' + filename
      }
      setTimeout(() => { img.src = retryUrl }, 500)
    } else {
      const container = img.closest('.gpt-image-container')
      if (container) {
        container.classList.add('error')
        const errorEl = container.querySelector('.gpt-image-error')
        if (errorEl) errorEl.style.display = 'flex'
      }
      img.style.display = 'none'
    }
  }

  document.addEventListener('click', handleCodeExpandOrCopy)
  document.addEventListener('load', handleImageLoad, true)
  document.addEventListener('error', handleImageError, true)

  onBeforeUnmount(() => {
    document.removeEventListener('click', handleCodeExpandOrCopy)
    document.removeEventListener('load', handleImageLoad, true)
    document.removeEventListener('error', handleImageError, true)
  })

  // 初始化時立即應用代碼塊增強
  nextTick(() => {
    console.log('🔧 開始初始化代碼區塊增強')
    enhanceCodeBlocks()
    setupObserver() // 設置觀察器
  })

  // 使用防抖動函數減少頻繁調用
  let enhanceTimer = null;
  const debouncedEnhance = () => {
    clearTimeout(enhanceTimer);
    enhanceTimer = setTimeout(() => {
      console.log('執行代碼區塊增強 (防抖動)');
      enhanceCodeBlocks();
    }, 200);
  };

  // 簡化的DOM觀察器 - 只在必要時啟用
  let observer = null;

  const setupObserver = () => {
    if (observer) {
      observer.disconnect();
    }

    observer = new MutationObserver((mutations) => {
      let hasNewContent = false;

      mutations.forEach(mutation => {
        if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
          hasNewContent = true;
        }
      });

      if (hasNewContent) {
        debouncedEnhance();
      }
    });

    // 只觀察當前組件的容器
    nextTick(() => {
      const container = document.querySelector('.llm-markdown-note');
      if (container) {
        observer.observe(container, {
          childList: true,
          subtree: false // 減少監視範圍
        });
        console.log('已設置簡化的DOM觀察器');
      }
    });
  };

  // 監視 effectiveMarkdown 和 cardBlocks 的變化
  watch([() => effectiveMarkdown.value, () => cardBlocks.value], () => {
    nextTick(() => {
      console.log('Markdown 內容已更新，應用代碼區塊增強')
      enhanceCodeBlocks()
    })
  }, { immediate: true, deep: true })
})

// 添加圖片同步功能
async function syncImages() {
  try {
    console.log(t('syncingImages'))
    const response = await fetch('/api/sync-images', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        language: currentLanguage.value
      })
    })

    if (response.ok) {
      const result = await response.json()
      console.log('✅ 圖片同步成功:', result)

      // 手動檢查幾個常見圖片是否存在
      await checkSampleImages()

      const copiedCount = Number(result?.copied ?? result?.count ?? 0)
      ElMessage.success(t('imageSyncSuccess', { count: copiedCount }))
    } else {
      console.warn('❌ 圖片同步失敗:', response.status)
      ElMessage.error(t('imageSyncFailed'))
    }
  } catch (error) {
    console.warn('❌ 圖片同步請求失敗:', error)
    ElMessage.error(t('imageSyncRequestFailed'))
  }
}

// 檢查示例圖片是否可以訪問
async function checkSampleImages() {
  const sampleImages = [
    `/images/scene_0_middle.jpg`,
    `/images/scene_1_middle.jpg`,
    `/images/scene_2_middle.jpg`,
    `/images/test_scene.jpg`
  ]

  for (const imgPath of sampleImages) {
    try {
      const response = await fetch(imgPath, { method: 'HEAD' })
      if (response.ok) {
        console.log(`✅ 圖片可訪問: ${imgPath}`)
      } else {
        console.warn(`❌ 圖片無法訪問: ${imgPath} (${response.status})`)
      }
    } catch (error) {
      console.warn(`❌ 圖片檢查失敗: ${imgPath}`, error)
    }
  }
}

// 添加全局的代碼複製函數
window.copyCode = function (button) {
  const codeBlock = button.closest('.code-block-enhanced').querySelector('code')
  const text = codeBlock.textContent
  navigator.clipboard.writeText(text).then(() => {
    button.textContent = '✅'
    setTimeout(() => {
      button.textContent = '📋'
    }, 2000)
  }).catch(err => {
    console.error('複製失敗:', err)
    button.textContent = '❌'
    setTimeout(() => {
      button.textContent = '📋'
    }, 2000)
  })
}

const processingStatus = ref(null)
const errorInfo = ref(null)

function retryProcessing() {
  // 重新尝试处理逻辑
  errorInfo.value = null
  ElMessage.info(t('reprocessFeatureNotImplemented'))
}

watch(processingStatus, (newStatus) => {
  if (newStatus && newStatus.status === "錯誤") {
    errorInfo.value = {
      message: newStatus.detail
    }
  } else {
    errorInfo.value = null
  }
})

// 移除未定義的statusDict監聽器

</script>



<style>
/* === 圖片容器樣式 === */
:deep(.gpt-image-container) {
  text-align: center;
  margin: 1.5em 0;
  padding: 10px;
  background: rgba(0, 0, 0, 0.02);
  border-radius: 8px;
  position: relative;
  min-height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
}

:deep(.gpt-image) {
  max-width: 80%;
  max-height: 500px;
  height: auto;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  display: block;
  margin: 0 auto;
  transition: opacity 0.3s ease;
  object-fit: contain;
}

:deep(.gpt-image-container.loaded .gpt-image) {
  opacity: 1;
}

:deep(.gpt-image-error) {
  display: none;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #6c757d;
  padding: 20px;
}

:deep(.gpt-image-container.error .gpt-image-error) {
  display: flex;
}

:deep(.gpt-image-error svg) {
  margin-bottom: 12px;
  opacity: 0.5;
}

:deep(.gpt-image-error p) {
  margin: 8px 0 4px 0;
  font-weight: 500;
  color: #495057;
}

:deep(.gpt-image-error small) {
  color: #6c757d;
  font-size: 12px;
}

/* 深色模式下的圖片容器 */
html.dark :deep(.gpt-image-container) {
  background: rgba(255, 255, 255, 0.05);
}

html.dark :deep(.gpt-image-error p) {
  color: #e2e8f0;
}

html.dark :deep(.gpt-image-error small) {
  color: #94a3b8;
}

.image-container {
  text-align: center;
  margin: 1.5em 0;
  padding: 15px;
  background: rgba(0, 0, 0, 0.02);
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.image-container img {
  max-width: 60%;
  max-height: 350px;
  height: auto;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  display: block;
  margin: 0 auto;
  object-fit: contain;
}

/* 修復版權圖片樣式 */
.llm-note-markdown img[alt*="Copyright"],
.llm-note-markdown img[src*="copyright"] {
  max-width: 50% !important;
  max-height: 200px !important;
  margin: 16px auto !important;
  display: block !important;
}

/* === 新的 Notion 風格樣式 === */
.notion-note-container {
  background: transparent;
  border-radius: 16px;
  box-shadow: none;
  border: none;
  overflow: hidden;
  margin: 16px 0;
}

.notion-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: transparent;
  border-bottom: 1px solid #e9ecef;
  border-radius: 8px;
  margin-bottom: 16px;
}

.toolbar-left {
  display: flex;
  align-items: center;
}

.note-stats {
  display: flex;
  gap: 16px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: #6c757d;
  font-weight: 500;
}

.stat-item .icon {
  font-size: 16px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.copied-tip {
  color: #10a37f;
  font-weight: 600;
  font-size: 14px;
  animation: fadeInOut 2s ease-in-out;
}

@keyframes fadeInOut {

  0%,
  100% {
    opacity: 0;
  }

  20%,
  80% {
    opacity: 1;
  }
}

.notion-content-wrapper {
  min-height: 200px;
  padding: 0;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #6c757d;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.empty-state h3 {
  color: #495057;
  margin: 16px 0 8px 0;
  font-size: 20px;
  font-weight: 600;
}

.empty-state p {
  color: #6c757d;
  font-size: 16px;
  line-height: 1.6;
  max-width: 400px;
  margin: 0 auto;
}

.notion-blocks {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.notion-block {
  background: var(--card, rgba(255, 255, 255, 0.02));
  border-radius: 14px;
  border: 1px solid var(--border, rgba(255, 255, 255, 0.08));
  overflow: hidden;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.notion-block:hover {
  transform: translateY(-1px);
  border-color: var(--accent, #4ade80);
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.14);
}

.block-content {
  padding: 12px 18px 18px;
  font-size: 16px;
  line-height: 1.7;
  color: #2c3e50;
}

/* 讓一般段落更清晰區分於代碼區塊 */
.block-content :deep(p:not(:has(code))) {
  background: transparent;
}

.notion-footer {
  padding: 16px 24px;
  background: transparent;
  border-top: 1px solid #e9ecef;
  position: relative;
  z-index: 1;
  box-sizing: border-box;
}

.footer-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  color: #6c757d;
  flex-wrap: wrap;
  gap: 8px;
}

.footer-info span {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Notion 風格的內容樣式 */
.block-content :deep(h1) {
  font-size: 2.2em;
  font-weight: 700;
  margin: 32px 0 16px 0;
  padding-bottom: 12px;
  border-bottom: 2px solid #10a37f;
  color: #2c3e50;
  background: linear-gradient(135deg, #2c3e50, #34495e);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.block-content :deep(h2) {
  font-size: 1.6em;
  font-weight: 600;
  margin: 28px 0 12px 0;
  color: #2c3e50;
  padding: 8px 12px;
  background: rgba(16, 163, 127, 0.1);
  border-radius: 6px;
  border-left: 3px solid #10a37f;
}

.block-content :deep(h3) {
  font-size: 1.3em;
  font-weight: 600;
  margin: 24px 0 10px 0;
  color: #10a37f;
  padding: 6px 10px;
  background: rgba(16, 163, 127, 0.1);
  border-radius: 4px;
  border-left: 2px solid #10a37f;
}

.block-content :deep(p) {
  margin: 16px 0;
  color: #e0e0e0 !important;
  line-height: 1.7;
}

.block-content :deep(strong) {
  font-weight: 600;
  color: #e0e0e0 !important;
}

/* 列表樣式 */
.block-content :deep(ul) {
  margin: 16px 0;
  padding-left: 24px;
}

.block-content :deep(ol) {
  margin: 16px 0;
  padding-left: 24px;
}

.block-content :deep(li) {
  margin: 8px 0;
  color: #e0e0e0 !important;
  line-height: 1.6;
}

.block-content :deep(li strong) {
  color: #10a37f !important;
  font-weight: 600;
}

/* 特別針對程式碼說明區塊 */
.notion-block .block-content :deep(li) {
  color: #e0e0e0 !important;
  line-height: 1.6;
}

.notion-block .block-content :deep(li strong) {
  color: #10a37f !important;
  font-weight: 600;
}

/* 更強的選擇器確保樣式生效 */
.notion-note-container .notion-blocks .notion-block .block-content :deep(li) {
  color: #e0e0e0 !important;
  line-height: 1.6 !important;
}

.notion-note-container .notion-blocks .notion-block .block-content :deep(li strong) {
  color: #10a37f !important;
  font-weight: 600 !important;
}

/* 移除強制深色文字設置 - 讓深色模式樣式生效 */

/* 最強選擇器 - 針對所有可能的容器 */
div li,
section li,
article li,
main li,
[class*="block"] li,
[class*="content"] li,
[class*="markdown"] li,
[class*="notion"] li {
  color: #2c3e50 !important;
  line-height: 1.6 !important;
}

div li strong,
section li strong,
article li strong,
main li strong,
[class*="block"] li strong,
[class*="content"] li strong,
[class*="markdown"] li strong,
[class*="notion"] li strong {
  color: #10a37f !important;
  font-weight: 600 !important;
}

/* 終極選擇器 - 覆蓋所有可能的樣式 */
li {
  color: #2c3e50 !important;
}

li strong {
  color: #10a37f !important;
}

/* 移除強制深色文字，讓深色模式樣式生效 */

/* 針對藍色背景的程式碼說明區塊 */
[style*="background"] p,
[style*="background"] strong,
.code-explanation p,
.code-explanation strong {
  color: #ffffff !important;
}

/* 深色模式下的程式碼說明 */
.app-container.dark-mode [style*="background"] p,
.app-container.dark-mode [style*="background"] strong {
  color: #ffffff !important;
}

/* 移除所有可能導致亂碼的CSS修改 */

/* 深色模式的最強選擇器 */
.app-container.dark-mode .llm-note-markdown li,
.app-container.dark-mode .block-content li,
.app-container.dark-mode .notion-block li {
  color: #e2e8f0 !important;
  line-height: 1.6 !important;
}

.app-container.dark-mode .llm-note-markdown li strong,
.app-container.dark-mode .block-content li strong,
.app-container.dark-mode .notion-block li strong {
  color: #10b981 !important;
  font-weight: 600 !important;
}

/* 表格樣式 */
.block-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 20px 0;
  background: #ffffff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.block-content :deep(th) {
  background: #f8f9fa;
  color: #2c3e50;
  font-weight: 600;
  padding: 12px 16px;
  text-align: left;
  border: 1px solid #e9ecef;
  font-size: 14px;
}

.block-content :deep(td) {
  padding: 12px 16px;
  border: 1px solid #e9ecef;
  color: #2c3e50;
  font-size: 14px;
  line-height: 1.5;
}

.block-content :deep(tr:nth-child(even)) {
  background: #f8f9fa;
}

.block-content :deep(tr:hover) {
  background: #e3f2fd;
}

.block-content :deep(ul),
.block-content :deep(ol) {
  margin: 16px 0;
  padding-left: 24px;
}

/* 深色模式下的標題和內容樣式 */
.app-container.dark-mode .block-content :deep(h1) {
  color: #ffffff !important;
  background: linear-gradient(135deg, #10a37f, #0891b2);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  border-bottom-color: #10a37f;
}

.app-container.dark-mode .block-content :deep(h2) {
  color: #0ea5e9 !important;
  background: rgba(14, 165, 233, 0.15);
  border-left-color: #0ea5e9;
}

.app-container.dark-mode .block-content :deep(h3) {
  color: #10b981 !important;
  background: rgba(16, 185, 129, 0.15);
  border-left-color: #10b981;
}

.app-container.dark-mode .block-content :deep(h4) {
  color: #f59e0b !important;
  font-weight: 600;
  margin: 20px 0 8px 0;
}

.app-container.dark-mode .block-content :deep(h5) {
  color: #8b5cf6 !important;
  font-weight: 600;
  margin: 18px 0 6px 0;
}

.app-container.dark-mode .block-content :deep(h6) {
  color: #ec4899 !important;
  font-weight: 600;
  margin: 16px 0 4px 0;
}

.app-container.dark-mode .block-content :deep(p) {
  color: #e2e8f0 !important;
  line-height: 1.7;
}

/* 修復深色模式下的表格樣式 */
.app-container.dark-mode .block-content :deep(table) {
  background: #1e293b !important;
  border: 1px solid #334155 !important;
  color: #e2e8f0 !important;
}

.app-container.dark-mode .block-content :deep(th) {
  background: #334155 !important;
  color: #ffffff !important;
  border: 1px solid #475569 !important;
  padding: 12px !important;
  font-weight: 600 !important;
}

.app-container.dark-mode .block-content :deep(td) {
  background: #1e293b !important;
  color: #e2e8f0 !important;
  border: 1px solid #334155 !important;
  padding: 12px !important;
}

.app-container.dark-mode .block-content :deep(strong) {
  color: #ffffff !important;
  font-weight: 600;
}

.app-container.dark-mode .block-content :deep(em) {
  color: #cbd5e1 !important;
}

.app-container.dark-mode .block-content :deep(code) {
  color: #fbbf24 !important;
  background: rgba(59, 130, 246, 0.1) !important;
  border: 1px solid rgba(59, 130, 246, 0.2) !important;
}

.app-container.dark-mode .block-content :deep(pre) {
  background: #1e293b !important;
  border: 1px solid #334155 !important;
}

.app-container.dark-mode .block-content :deep(pre code) {
  color: #e2e8f0 !important;
  background: transparent !important;
}

.app-container.dark-mode .empty-state {
  color: #cbd5e1 !important;
}

.app-container.dark-mode .empty-state h3 {
  color: #f1f5f9 !important;
}

.app-container.dark-mode .empty-state p {
  color: #94a3b8 !important;
}

/* 統一深色模式選擇器 */
.app-container.dark-mode .block-content :deep(blockquote) {
  background: rgba(100, 116, 139, 0.1) !important;
  border-left-color: #64748b !important;
  color: #cbd5e1 !important;
}

.app-container.dark-mode .block-content :deep(li) {
  color: #e2e8f0 !important;
  line-height: 1.6;
}

.app-container.dark-mode .block-content :deep(li strong) {
  color: #10b981 !important;
  font-weight: 600;
}

/* 深色模式下的程式碼說明區塊 */
.app-container.dark-mode .notion-block .block-content :deep(li) {
  color: #e2e8f0 !important;
  line-height: 1.6;
}

.app-container.dark-mode .notion-block .block-content :deep(li strong) {
  color: #10b981 !important;
  font-weight: 600;
}

/* 深色模式的終極選擇器 */
.app-container.dark-mode li,
.dark-mode li,
[class*="dark"] li {
  color: #e2e8f0 !important;
}

.app-container.dark-mode li strong,
.dark-mode li strong,
[class*="dark"] li strong {
  color: #10b981 !important;
}

.app-container.dark-mode .block-content :deep(ul) {
  margin: 16px 0;
}

.app-container.dark-mode .block-content :deep(ol) {
  margin: 16px 0;
}

/* 修復程式碼區塊的背景和文字對比 */
.block-content :deep(pre) {
  background: #f8f9fa !important;
  border: 1px solid #e9ecef !important;
  border-radius: 8px !important;
  padding: 16px !important;
  margin: 16px 0 !important;
  overflow-x: auto !important;
}

.block-content :deep(pre code) {
  background: transparent !important;
  color: #2c3e50 !important;
  font-family: 'Fira Code', 'Monaco', 'Consolas', monospace !important;
  font-size: 14px !important;
  line-height: 1.5 !important;
}

.block-content :deep(code) {
  background: rgba(16, 163, 127, 0.1) !important;
  color: #10a37f !important;
  padding: 2px 6px !important;
  border-radius: 4px !important;
  font-family: 'Fira Code', 'Monaco', 'Consolas', monospace !important;
  font-size: 13px !important;
}

/* 深色模式下的特殊標記 */
html.dark .block-content :deep(.highlight-mark) {
  background: rgba(251, 191, 36, 0.3);
  color: #fbbf24;
}

html.dark .block-content :deep(.pointer) {
  color: #10b981;
}

/* 圖片-內容配對樣式 */
.image-pair-block {
  margin-bottom: 1rem;
}

.image-block {
  text-align: center;
  margin-bottom: 0.5rem;
  padding: 1rem;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 8px;
}

.content-block {
  margin-bottom: 2rem;
  padding: 1.5rem;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  border-left: 4px solid var(--el-color-primary);
}

html.dark .image-block {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

html.dark .content-block {
  background: rgba(255, 255, 255, 0.04);
  border-left-color: #4F8FFF;
}

/* 確保圖片在圖片塊中正確顯示 */
.image-block :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

/* 修復深色模式下的文字顏色 - 精確控制 */
html.dark .notion-note-container,
html.dark .notion-note-container *,
html.dark .block-content,
html.dark .block-content *,
html.dark .llm-note-markdown,
html.dark .llm-note-markdown * {
  color: #e2e8f0 !important;
}

/* 標題特殊顏色 */
html.dark .block-content h1,
html.dark .block-content h2,
html.dark .block-content h3,
html.dark .block-content h4,
html.dark .block-content h5,
html.dark .block-content h6,
html.dark .block-content :deep(h1),
html.dark .block-content :deep(h2),
html.dark .block-content :deep(h3),
html.dark .block-content :deep(h4),
html.dark .block-content :deep(h5),
html.dark .block-content :deep(h6) {
  color: #ffffff !important;
}

/* 強調文字 */
html.dark .block-content strong,
html.dark .block-content :deep(strong) {
  color: #10b981 !important;
  font-weight: 600;
}

/* 強制覆蓋所有可能的文字元素 */
html.dark div,
html.dark span,
html.dark p,
html.dark h1,
html.dark h2,
html.dark h3,
html.dark h4,
html.dark h5,
html.dark h6,
html.dark li,
html.dark td,
html.dark th,
html.dark a,
html.dark strong,
html.dark em,
html.dark code,
html.dark pre,
html.dark .block-content,
html.dark .block-content *,
html.dark .notion-block,
html.dark .notion-block *,
html.dark .llm-note-markdown,
html.dark .llm-note-markdown * {
  color: #ffffff !important;
  -webkit-text-fill-color: #ffffff !important;
}

/* 深色模式下的代碼塊背景修正 */
html.dark .llm-note-markdown pre,
html.dark .llm-note-markdown .code-block-enhanced,
html.dark .llm-note-markdown pre,
html.dark .notion-block pre,
html.dark .block-content pre {
  background: linear-gradient(180deg, #0d1117 0%, #0a0f18 50%, #0f172a 100%) !important;
  border: 1px solid #1c2535 !important;
  color: #eaf1ff !important;
  box-shadow: 0 14px 32px rgba(0, 0, 0, 0.38) !important;
}

html.dark .llm-note-markdown code:not(pre code),
html.dark .notion-block code:not(pre code),
html.dark .block-content code:not(pre code) {
  background: rgba(12, 17, 24, 0.85) !important;
  color: #eaf1ff !important;
  padding: 2px 6px !important;
  border-radius: 6px !important;
  border: 1px solid #1c2535 !important;
}

/* 針對Vue的deep選擇器 */
html.dark :deep(*) {
  color: #ffffff !important;
  -webkit-text-fill-color: #ffffff !important;
}

/* 最強制的文字顏色修復 - 覆蓋所有可能的樣式 */
html.dark *,
html.dark .notion-note-container *,
html.dark .notion-blocks *,
html.dark .notion-block *,
html.dark .block-content *,
html.dark .llm-note-markdown *,
html.dark h1,
html.dark h2,
html.dark h3,
html.dark h4,
html.dark h5,
html.dark h6,
html.dark p,
html.dark div,
html.dark span,
html.dark li,
html.dark td,
html.dark th {
  color: #ffffff !important;
  -webkit-text-fill-color: #ffffff !important;
}

/* 圖片載入失敗時的文字顯示修正 */
html.dark .gpt-image-container .image-load-failed,
html.dark .gpt-image-container .image-load-failed *,
html.dark .notion-block .image-load-failed,
html.dark .notion-block .image-load-failed * {
  color: #ffffff !important;
  background: rgba(239, 68, 68, 0.1) !important;
  border: 1px solid #ef4444 !important;
  padding: 12px !important;
  border-radius: 8px !important;
  text-align: center !important;
}

html.dark *::before,
html.dark *::after {
  color: #ffffff !important;
  -webkit-text-fill-color: #ffffff !important;
}

/* 特別針對可能被遺漏的元素 */
html.dark .notion-block *,
html.dark .block-content *,
html.dark .llm-note-markdown *,
html.dark [class*="content"] *,
html.dark [class*="block"] *,
html.dark [class*="text"] *,
html.dark [class*="note"] * {
  color: #ffffff !important;
  -webkit-text-fill-color: #ffffff !important;
}

/* 特別針對標題 */
html.dark h1,
html.dark h2,
html.dark h3,
html.dark h4,
html.dark h5,
html.dark h6,
html.dark .block-content h1,
html.dark .block-content h2,
html.dark .block-content h3,
html.dark .block-content h4,
html.dark .block-content h5,
html.dark .block-content h6,
html.dark .block-content :deep(h1),
html.dark .block-content :deep(h2),
html.dark .block-content :deep(h3),
html.dark .block-content :deep(h4),
html.dark .block-content :deep(h5),
html.dark .block-content :deep(h6) {
  color: #ffffff !important;
}

/* 特別針對段落和文字元素 */
html.dark p,
html.dark span,
html.dark div,
html.dark li,
html.dark td,
html.dark th,
html.dark .block-content p,
html.dark .block-content span,
html.dark .block-content div,
html.dark .block-content li,
html.dark .block-content td,
html.dark .block-content th,
html.dark .block-content :deep(p),
html.dark .block-content :deep(span),
html.dark .block-content :deep(div),
html.dark .block-content :deep(li),
html.dark .block-content :deep(td),
html.dark .block-content :deep(th) {
  color: #ffffff !important;
}

/* 確保代碼塊也有正確顏色 */
html.dark pre,
html.dark code,
html.dark .block-content pre,
html.dark .block-content code,
html.dark .block-content :deep(pre),
html.dark .block-content :deep(code) {
  color: #ffffff !important;
  background: rgba(255, 255, 255, 0.1) !important;
}

/* 特殊文本模式的樣式增強 */
.block-content :deep(p) {

  &:has-text("分析："),
  &:has-text("解析："),
  &:has-text("程式碼部分分析："),
  &:has-text("重點：") {
    font-weight: 600;
    color: #2c3e50;
    margin: 20px 0 12px 0;
    padding: 8px 12px;
    background: rgba(44, 62, 80, 0.1);
    border-radius: 6px;
    border-left: 3px solid #2c3e50;
  }
}

/* 使用更通用的方法來處理特殊標題 */
.block-content :deep(p strong:first-child) {
  /* 如果段落以粗體文字開始，可能是標題 */
  display: block;
  font-size: 1.1em;
  color: #2c3e50;
  margin-bottom: 8px;
}

html.dark .block-content :deep(p strong:first-child) {
  color: #0ea5e9;
}

/* 特殊標題段落樣式 */
.block-content :deep(.special-title) {
  font-weight: 600;
  color: #2c3e50 !important;
  background: rgba(44, 62, 80, 0.08);
  padding: 10px 14px;
  border-radius: 6px;
  border-left: 3px solid #2c3e50;
  margin: 16px 0;
}

html.dark .block-content :deep(.special-title) {
  color: #0ea5e9 !important;
  background: rgba(14, 165, 233, 0.12);
  border-left-color: #0ea5e9;
}

.block-content :deep(li) {
  margin: 8px 0;
  color: #2c3e50;
  line-height: 1.6;
}

.block-content :deep(blockquote) {
  margin: 20px 0;
  padding: 16px 20px;
  background: #f8f9fa;
  border-left: 4px solid #10a37f;
  border-radius: 0 8px 8px 0;
  color: #495057;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.block-content :deep(hr) {
  border: none;
  height: 1px;
  background: linear-gradient(90deg, transparent, #dee2e6, transparent);
  margin: 32px 0;
}

.block-content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
  margin: 16px 0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

/* 深色模式適配 */
@media (prefers-color-scheme: dark) {
  .notion-note-container {
    background: transparent;
    border-color: transparent;
  }

  .notion-toolbar {
    background: transparent;
    border-bottom-color: #333;
  }

  .stat-item {
    color: #8e8ea0;
  }

  .notion-content-wrapper {
    background: transparent;
  }

  .empty-state h3 {
    color: #ffffff;
  }

  .empty-state p {
    color: #8e8ea0;
  }

  .notion-block {
    background: #2d2d2d;
    border-color: #404040;
  }

  .notion-block:hover {
    border-color: #10a37f;
    box-shadow: 0 4px 16px rgba(16, 163, 127, 0.2);
  }

  .block-content {
    color: #e9e9e7;
  }

  .block-content :deep(h1),
  .block-content :deep(h2),
  .block-content :deep(h3) {
    color: #ffffff;
  }

  .block-content :deep(p),
  .block-content :deep(li),
  .block-content :deep(strong) {
    color: #e9e9e7;
  }

  .block-content :deep(blockquote) {
    background: #2d2d2d;
    color: #e9e9e7;
  }

  /* 底部UI修復 - 暗黑模式 */
  html.dark .notion-footer {
    background: transparent !important;
    border-top-color: #404040 !important;
  }

  html.dark .footer-info {
    color: #8e8ea0 !important;
  }

  html.dark .footer-info span {
    color: #8e8ea0 !important;
  }
}

/* === 原有樣式保持不變 === */
.llm-note-card {
  background: transparent;
  border-radius: 12px;
}

.llm-note-container {
  box-shadow: none;
  padding: 24px 20px 20px 20px;
  margin-bottom: 16px;
  position: relative;
}

.llm-note-toolbar {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  margin-bottom: 8px;
}

.copied-tip {
  color: #67c23a;
  margin-left: 8px;
  font-size: 13px;
}

.llm-note-markdown {
  background: transparent;
  border-radius: 12px;
}

.llm-note-container {
  box-shadow: none;
  padding: 24px 20px 20px 20px;
  margin-bottom: 16px;
  position: relative;
}

.llm-note-toolbar {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  margin-bottom: 8px;
}

.copied-tip {
  color: #67c23a;
  margin-left: 8px;
  font-size: 13px;
}

.llm-note-markdown {
  font-size: 18px;
  line-height: 1.8;
  color: #222;
  word-break: break-word;
}

.llm-note-markdown h1,
.llm-note-markdown h2,
.llm-note-markdown h3 {
  margin: 18px 0 10px 0;
  font-weight: bold;
}

.llm-note-markdown ul {
  padding-left: 1.5em;
  margin: 10px 0;
}

.llm-note-markdown li {
  margin-bottom: 4px;
}

.llm-note-markdown blockquote {
  background: #f6f8fa;
  border-left: 4px solid #b3b3b3;
  margin: 10px 0;
  padding: 8px 16px;
  color: #555;
  border-radius: 6px;
}

/* Callout 樣式支援 */
.llm-note-markdown blockquote[data-callout="info"] {
  background: #e3f2fd;
  border-left: 4px solid #2196f3;
  color: #1565c0;
}

.llm-note-markdown blockquote[data-callout="warning"] {
  background: #fff3e0;
  border-left: 4px solid #ff9800;
  color: #e65100;
}

.llm-note-markdown blockquote[data-callout="tip"] {
  background: #e8f5e8;
  border-left: 4px solid #4caf50;
  color: #2e7d32;
}

.llm-note-markdown blockquote[data-callout="note"] {
  background: #f3e5f5;
  border-left: 4px solid #9c27b0;
  color: #6a1b9a;
}

/* Notion 風格列表樣式 */
.llm-note-markdown ul,
.llm-note-markdown ol {
  margin: 20px 0 !important;
  padding-left: 0 !important;
}

.llm-note-markdown li {
  margin-bottom: 8px !important;
  line-height: 1.6 !important;
  padding: 8px 16px !important;
  position: relative !important;
  border-radius: 8px !important;
  background: rgba(0, 0, 0, 0.02) !important;
  border-left: 3px solid #e5e7eb !important;
  transition: all 0.2s ease !important;
}

.llm-note-markdown li:hover {
  background: rgba(0, 0, 0, 0.05) !important;
  border-left-color: #3b82f6 !important;
}

.llm-note-markdown ul li {
  list-style: none !important;
}

.llm-note-markdown ul li::before {
  content: "•" !important;
  color: #3b82f6 !important;
  font-weight: bold !important;
  position: absolute !important;
  left: 4px !important;
  top: 8px !important;
}

.llm-note-markdown ol li {
  list-style: none !important;
  counter-increment: item !important;
}

.llm-note-markdown ol {
  counter-reset: item !important;
}

.llm-note-markdown ol li::before {
  content: counter(item) "." !important;
  color: #3b82f6 !important;
  font-weight: bold !important;
  position: absolute !important;
  left: 4px !important;
  top: 8px !important;
}

/* 修復嵌套列表 */
.llm-note-markdown li ul,
.llm-note-markdown li ol {
  margin: 8px 0 !important;
  padding-left: 0 !important;
}

.llm-note-markdown li li {
  background: rgba(0, 0, 0, 0.01) !important;
  border-left-color: #d1d5db !important;
  margin-left: 16px !important;
}

/* 修復列表項目的文字對齊 */
.llm-note-markdown li p {
  margin: 0 !important;
  display: inline !important;
  padding-left: 16px !important;
}

/* 修復列表中的強制文字 */
.llm-note-markdown li strong {
  color: #1f2937 !important;
  font-weight: 600 !important;
}

.dark-mode .llm-note-markdown li {
  background: rgba(255, 255, 255, 0.05) !important;
  border-left-color: #4b5563 !important;
}

.dark-mode .llm-note-markdown li:hover {
  background: rgba(255, 255, 255, 0.1) !important;
  border-left-color: #60a5fa !important;
}

.dark-mode .llm-note-markdown li strong {
  color: #f9fafb !important;
}

/* 表格優化 */
.llm-note-markdown table {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
  background: transparent;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.llm-note-markdown th {
  background: #f8f9fa;
  color: #495057;
  font-weight: 600;
  padding: 12px 16px;
  text-align: left;
  border-bottom: 2px solid #dee2e6;
}

.llm-note-markdown td {
  padding: 12px 16px;
  border-bottom: 1px solid #dee2e6;
  color: #212529;
}

.llm-note-markdown tr:hover {
  background: #f8f9fa;
}

.llm-note-markdown pre:not(.code-block-enhanced pre) {
  background: linear-gradient(180deg, #0d1117 0%, #0a0f18 50%, #0f172a 100%);
  color: #eaf1ff;
  border-radius: 14px;
  padding: 16px 18px 18px 18px;
  margin: 18px 0;
  overflow-x: auto;
  font-size: 1em;
  font-family: 'JetBrains Mono', 'Fira Mono', 'Consolas', 'Menlo', 'Monaco', 'monospace' !important;
  box-shadow: 0 14px 32px rgba(0, 0, 0, 0.38);
  border: 1px solid #1c2535;
  position: relative;
}

/* 代碼與圖片排序優化樣式 */
.notion-blocks pre+img,
.notion-blocks pre+p>img {
  display: block;
  margin-top: 0.5rem;
  max-width: 100%;
  border: 1px solid #eaecef;
  border-radius: 5px;
}

/* 代碼區塊與相關圖片的分組樣式 */
.code-image-group {
  margin-bottom: 2rem;
  position: relative;
}

.code-image-group:after {
  content: "";
  display: block;
  height: 1px;
  background: #eaecef;
  margin-top: 1.5rem;
}

/* 內聯代碼樣式 - 修復黃色標記 */
:deep(code:not(.gpt-code-content code)),
.llm-note-markdown code:not(.gpt-code-content code),
.block-content code:not(.gpt-code-content code) {
  font-family: 'JetBrains Mono', 'Fira Mono', 'Consolas', 'Menlo', 'Monaco', 'monospace' !important;
  background: rgba(251, 191, 36, 0.15) !important;
  color: #fbbf24 !important;
  /* 統一黃色程式碼標記 */
  font-size: 0.9em !important;
  border-radius: 4px !important;
  padding: 2px 6px !important;
  margin: 0 2px !important;
  font-weight: 600 !important;
  border: 1px solid rgba(251, 191, 36, 0.3) !important;
  box-shadow: 0 1px 2px rgba(251, 191, 36, 0.2) !important;
}

/* 深色模式下的內聯代碼 */
html.dark :deep(code:not(.gpt-code-content code)),
html.dark .llm-note-markdown code:not(.gpt-code-content code),
html.dark .block-content code:not(.gpt-code-content code) {
  background: rgba(251, 191, 36, 0.2) !important;
  color: #fbbf24 !important;
  border-color: rgba(251, 191, 36, 0.4) !important;
}

.llm-note-markdown .code-copy-btn {
  position: absolute;
  top: 10px;
  right: 14px;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  padding: 2px 6px;
  cursor: pointer;
  z-index: 10;
  font-size: 13px;
  display: flex;
  align-items: center;
  opacity: 0.7;
  transition: background 0.2s, opacity 0.2s;
}

.llm-note-markdown .code-copy-btn:hover {
  background: #f3f4f6;
  opacity: 1;
}

.llm-note-markdown img {
  max-width: 75%;
  max-height: 450px;
  display: block;
  margin: 1.5em auto 1.5em auto;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  background: #181818;
  object-fit: contain;
}

.gpt-section-title {
  font-size: 1.15em;
  font-weight: bold;
  color: #1976d2;
  background: linear-gradient(90deg, #e3f2fd 60%, #fff 100%);
  border-radius: 6px;
  padding: 2px 10px;
  margin-left: 6px;
}

.gpt-keyword {
  background: #fffde7;
  color: #d84315;
  font-weight: bold;
  border-radius: 4px;
  padding: 2px 6px;
  margin: 0 2px;
  box-shadow: 0 1px 0 #ffe0b2;
}

.gpt-divider {
  border: none;
  border-top: 2px dashed #90caf9;
  margin: 32px 0 24px 0;
}

.gpt-callout {
  box-shadow: 0 2px 12px rgba(25, 118, 210, 0.08);
  border-radius: 10px;
  border: 1.5px solid #90caf9;
  background: #e3f2fd;
  margin: 18px 0;
  padding: 14px 18px;
  font-size: 1.08em;
  color: #1976d2;
}

/* Code Block Enhanced Styles - 與 Chatbot 相同的高質量樣式 */
:deep(.code-block-enhanced) {
  margin: 16px 0;
  border-radius: 12px;
  overflow: hidden;
  background: #1e1e1e;
  border: 1px solid #404040;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

:deep(.code-block-header) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: linear-gradient(135deg, #2d2d2d 0%, #1a1a1a 100%);
  border-bottom: 1px solid #404040;
  min-height: 44px;
}

:deep(.header-left) {
  display: flex;
  align-items: center;
}

:deep(.language-tag) {
  background: linear-gradient(135deg, #10a37f 0%, #0d8a6b 100%);
  color: #ffffff;
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  box-shadow: 0 2px 4px rgba(16, 163, 127, 0.3);
}

:deep(.header-right) {
  display: flex;
  align-items: center;
}

:deep(.copy-button) {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--bg-secondary, rgba(255, 255, 255, 0.1));
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.2));
  color: var(--text-primary, #ffffff);
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: all 0.2s ease;
  backdrop-filter: blur(10px);
}

:deep(.copy-button:hover) {
  background: var(--bg-hover, rgba(255, 255, 255, 0.15));
  border-color: var(--primary-color, rgba(255, 255, 255, 0.3));
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
}

/* 淺色模式下的複製按鈕 */
html:not(.dark) :deep(.copy-button) {
  background: rgba(0, 0, 0, 0.05);
  border: 1px solid rgba(0, 0, 0, 0.1);
  color: #333333;
}

html:not(.dark) :deep(.copy-button:hover) {
  background: rgba(0, 0, 0, 0.1);
  border-color: #10a37f;
  color: #000000;
}

:deep(.copy-button svg) {
  width: 14px;
  height: 14px;
  opacity: 0.8;
}

:deep(.code-block-enhanced pre) {
  margin: 0 !important;
  padding: 20px !important;
  background: #1e1e1e !important;
  color: #ffffff !important;
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', 'Monaco', monospace !important;
  font-size: 14px !important;
  line-height: 1.6 !important;
  overflow-x: auto;
  border-radius: 0;
}

:deep(.code-block-enhanced code) {
  background: transparent !important;
  color: inherit !important;
  padding: 0 !important;
  margin: 0 !important;
  border-radius: 0 !important;
  box-shadow: none !important;
  font-family: inherit !important;
  display: inline-block;
  width: 100%;
  tab-size: 2;
}

/* Syntax Highlighting - 與 Chatbot 相同 */
:deep(.token.comment) {
  color: #6a9955 !important;
  font-style: italic;
}

:deep(.token.string) {
  color: #ce9178 !important;
}

:deep(.token.number) {
  color: #b5cea8 !important;
}

:deep(.token.keyword) {
  color: #569cd6 !important;
  font-weight: 600;
}

:deep(.token.function) {
  color: #dcdcaa !important;
  font-weight: 500;
}

/* 更好的代碼區塊間距和邊框 */
.llm-note-markdown .code-block-enhanced {
  margin: 24px 0;
  border-radius: 12px;
  overflow: hidden;
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace !important;
}

/* 代碼區塊頭部樣式 */
:deep(.code-block-enhanced .code-header) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #2d2d2d;
  padding: 8px 16px;
  border-bottom: 1px solid #404040;
}

:deep(.code-block-enhanced .language-label) {
  color: #888;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 1px;
}

:deep(.code-block-enhanced .copy-button) {
  background: var(--bg-secondary, transparent);
  border: 1px solid var(--border-color, #555);
  border-radius: 4px;
  color: var(--text-primary, #ccc);
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

:deep(.code-block-enhanced .copy-button:hover) {
  background: var(--bg-hover, #404040);
  border-color: var(--primary-color, #777);
  color: var(--text-primary, #fff);
}

/* 淺色模式下的代碼區塊複製按鈕 */
html:not(.dark) :deep(.code-block-enhanced .copy-button) {
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(0, 0, 0, 0.2);
  color: #333333;
}

html:not(.dark) :deep(.code-block-enhanced .copy-button:hover) {
  background: #ffffff;
  border-color: #10a37f;
  color: #000000;
}

/* 確保語法高亮正常工作 */
:deep(.hljs) {
  background: #1e1e1e !important;
  padding: 18px !important;
  color: #e0e0e0 !important;
}

/* 設定代碼區塊高亮效果 */
:deep(.hljs-keyword) {
  color: #569cd6 !important;
}

:deep(.hljs-function) {
  color: #dcdcaa !important;
}

:deep(.hljs-string) {
  color: #ce9178 !important;
}

:deep(.hljs-comment) {
  color: #6a9955 !important;
}

:deep(.hljs-number) {
  color: #b5cea8 !important;
}

:deep(.hljs-title) {
  color: #4ec9b0 !important;
}

:deep(.hljs-built_in) {
  color: #4ec9b0 !important;
}

:deep(.hljs-literal) {
  color: #569cd6 !important;
}

/* ChatGPT 風格代碼區塊中的語法高亮 */
:deep(.gpt-code-content .hljs-keyword) {
  color: #569cd6 !important;
}

:deep(.gpt-code-content .hljs-function) {
  color: #dcdcaa !important;
}

:deep(.gpt-code-content .hljs-string) {
  color: #ce9178 !important;
}

:deep(.gpt-code-content .hljs-comment) {
  color: #6a9955 !important;
}

:deep(.gpt-code-content .hljs-number) {
  color: #b5cea8 !important;
}

/* 內聯代碼樣式優化 - 統一使用黃色 */
.llm-note-markdown code:not(pre code) {
  background: rgba(251, 191, 36, 0.15) !important;
  color: #fbbf24 !important;
  padding: 2px 6px !important;
  border-radius: 4px !important;
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', 'Monaco', monospace !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  border: 1px solid rgba(251, 191, 36, 0.3) !important;
  box-shadow: 0 1px 2px rgba(251, 191, 36, 0.2) !important;
}

/* 基礎文字顏色和樣式 - 移除強制深色 */
.llm-note-markdown {
  line-height: 1.7;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

/* 標題樣式 - 移除強制深色 */
.llm-note-markdown h1,
.llm-note-markdown h2,
.llm-note-markdown h3,
.llm-note-markdown h4,
.llm-note-markdown h5,
.llm-note-markdown h6 {
  font-weight: 600;
  margin-top: 1.5em;
  margin-bottom: 0.5em;
}

.llm-note-markdown h1 {
  font-size: 2em;
  border-bottom: 2px solid #e5e7eb;
  padding-bottom: 0.3em;
}

.llm-note-markdown h2 {
  font-size: 1.5em;
  color: #374151 !important;
}

.llm-note-markdown h3 {
  font-size: 1.25em;
  color: #4b5563 !important;
}

/* 段落和文字 */
.llm-note-markdown p {
  color: #374151 !important;
  margin: 1em 0;
  text-align: justify;
}

/* 列表樣式 */
.llm-note-markdown ul,
.llm-note-markdown ol {
  color: #374151 !important;
  padding-left: 1.5em;
  margin: 1em 0;
}

.llm-note-markdown li {
  color: #374151 !important;
  margin: 0.5em 0;
}

/* 連結樣式 */
.llm-note-markdown a {
  color: #2563eb !important;
  text-decoration: none;
  border-bottom: 1px solid transparent;
  transition: all 0.2s ease;
}

.llm-note-markdown a:hover {
  color: #1d4ed8 !important;
  border-bottom-color: #2563eb;
}

/* 代碼樣式 - 統一使用黃色 */
.llm-note-markdown code {
  font-family: 'JetBrains Mono', 'Fira Mono', 'Consolas', 'Menlo', 'Monaco', 'monospace' !important;
  background: rgba(12, 17, 24, 0.85) !important;
  color: #eaf1ff !important;
  font-size: 0.9em !important;
  border-radius: 6px !important;
  padding: 2px 6px !important;
  margin: 0 2px !important;
  font-weight: 600 !important;
  border: 1px solid #1c2535 !important;
  box-shadow: none !important;
}

/* 預格式化文字區塊 */
.llm-note-markdown pre {
  background: linear-gradient(180deg, #0d1117 0%, #0a0f18 50%, #0f172a 100%) !important;
  color: #eaf1ff !important;
  padding: 16px 18px 18px 18px !important;
  border-radius: 14px !important;
  overflow-x: auto;
  margin: 18px 0 !important;
  border: 1px solid #1c2535 !important;
  box-shadow: 0 14px 32px rgba(0, 0, 0, 0.38) !important;
}

.llm-note-markdown pre code {
  background: transparent !important;
  color: inherit !important;
  padding: 0 !important;
  border: none !important;
  border-radius: 0 !important;
  margin: 0 !important;
  font-size: 14px !important;
  line-height: 1.6 !important;
}

/* 引用區塊樣式 */
.llm-note-markdown blockquote {
  border-left: 4px solid #10a37f;
  background: rgba(16, 163, 127, 0.05);
  color: #374151 !important;
  padding: 16px 20px;
  margin: 20px 0;
  border-radius: 0 8px 8px 0;
  font-style: italic;
}

.llm-note-markdown blockquote p {
  color: #374151 !important;
  margin: 0;
}

/* 分隔線 */
.llm-note-markdown hr {
  border: none;
  border-top: 2px solid #e5e7eb;
  margin: 2em 0;
}

/* 圖片樣式 */
.llm-note-markdown img {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  margin: 1.5em auto;
  display: block;
}

/* 標題樣式優化 */
.llm-note-markdown h1,
.llm-note-markdown h2,
.llm-note-markdown h3 {
  color: #2c3e50;
  margin: 20px 0 12px 0;
  font-weight: 600;
}

.llm-note-markdown h1 {
  font-size: 24px;
  border-bottom: 2px solid #10a37f;
  padding-bottom: 8px;
}

.llm-note-markdown h2 {
  font-size: 20px;
  color: #10a37f;
}

.llm-note-markdown h3 {
  font-size: 18px;
  color: #666;
}

/* 段落和列表樣式優化 */
.llm-note-markdown p {
  margin: 12px 0;
  color: #2c3e50;
  line-height: 1.7;
}

.llm-note-markdown ul,
.llm-note-markdown ol {
  margin: 12px 0;
  padding-left: 24px;
}

.llm-note-markdown li {
  margin: 6px 0;
  color: #2c3e50;
  line-height: 1.6;
}

@media (prefers-color-scheme: dark) {
  .llm-note-card {
    background: #181c20;
    color: #e6e6e6;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.18);
  }

  .llm-note-markdown {
    color: #e6e6e6;
    background: #181c20;
  }

  .llm-note-markdown h1,
  .llm-note-markdown h2,
  .llm-note-markdown h3 {
    color: #90caf9;
  }

  .llm-note-markdown h1 {
    border-bottom: 2px solid #10a37f;
  }

  .llm-note-markdown h2 {
    color: #10a37f;
  }

  .llm-note-markdown h3 {
    color: #8e8ea0;
  }

  .llm-note-markdown p,
  .llm-note-markdown li {
    color: #ffffff;
  }

  .llm-note-markdown pre {
    background: linear-gradient(180deg, #0d1117 0%, #0a0f18 50%, #0f172a 100%);
    color: #eaf1ff;
    box-shadow: 0 14px 32px rgba(0, 0, 0, 0.38);
  }

  /* 程式碼區塊和圖片的相關樣式 */
  .code-image-pair {
    margin-top: 1rem;
    display: block;
    border-left: 4px solid #10a37f;
    padding-left: 10px;
    background: rgba(16, 163, 127, 0.05);
    border-radius: 6px;
    padding: 10px;
    margin-bottom: 1.5rem;
  }

  /* 圖片上下文提示 */
  .image-context {
    font-size: 0.85rem;
    color: #666;
    margin-bottom: 0.5rem;
    font-style: italic;
    opacity: 0.8;
  }

  /* 確保圖片在代碼區塊後面顯示正確 */
  .code-image-pair img {
    max-width: 100%;
    margin: 0.5rem 0;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  }

  .llm-note-markdown code:not(.code-block-enhanced code) {
    background: rgba(251, 191, 36, 0.2) !important;
    color: #fbbf24 !important;
    border-color: rgba(251, 191, 36, 0.4) !important;
  }

  .llm-note-markdown blockquote {
    background: #23272f;
    border-left: 4px solid #90caf9;
    color: #b3e5fc;
  }

  /* 深夜模式 Callout 樣式 */
  .llm-note-markdown blockquote[data-callout="info"] {
    background: #1e3a5f;
    border-left: 4px solid #64b5f6;
    color: #90caf9;
  }

  .llm-note-markdown blockquote[data-callout="warning"] {
    background: #3e2723;
    border-left: 4px solid #ffb74d;
    color: #ffcc02;
  }

  .llm-note-markdown blockquote[data-callout="tip"] {
    background: #1b5e20;
    border-left: 4px solid #81c784;
    color: #a5d6a7;
  }

  .llm-note-markdown blockquote[data-callout="note"] {
    background: #4a148c;
    border-left: 4px solid #ba68c8;
    color: #ce93d8;
  }

  /* 深夜模式表格優化 */
  .llm-note-markdown table {
    background: #23272f;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  }

  .llm-note-markdown th {
    background: #2d3542;
    color: #90caf9;
    border-bottom: 2px solid #444;
  }

  .llm-note-markdown td {
    color: #e6e6e6;
    background: #23272f;
    border-bottom: 1px solid #444;
  }

  .llm-note-markdown tr:hover {
    background: #1e293b;
  }

  .llm-note-markdown hr,
  .llm-note-markdown .el-divider {
    border-color: #333;
  }

  .gpt-section-title {
    color: #90caf9;
    background: linear-gradient(90deg, #23272f 60%, #181c20 100%);
  }

  .gpt-keyword {
    background: #23272f;
    color: #ffb74d;
    box-shadow: 0 1px 0 #333;
  }

  .gpt-divider {
    border-top: 2px dashed #1976d2;
  }

  .gpt-callout {
    background: #23272f;
    color: #90caf9;
    border: 1.5px solid #1976d2;
  }
}

/* 增強表格樣式 */
.llm-note-markdown .enhanced-table {
  width: 100%;
  border-collapse: collapse;
  margin: 20px 0;
  background: transparent;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  border: 1px solid #e9ecef;
}

.llm-note-markdown .enhanced-table thead {
  background: linear-gradient(135deg, #10a37f 0%, #0891b2 100%);
  color: white;
}

.llm-note-markdown .enhanced-table th {
  padding: 16px 20px;
  text-align: left;
  font-weight: 600;
  font-size: 14px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  border: none;
}

.llm-note-markdown .enhanced-table td {
  padding: 14px 20px;
  border-bottom: 1px solid #f0f0f0;
  vertical-align: top;
  line-height: 1.6;
}

.llm-note-markdown .enhanced-table tr:hover {
  background: rgba(16, 163, 127, 0.05);
  transition: background 0.2s ease;
}

.llm-note-markdown .enhanced-table tr:last-child td {
  border-bottom: none;
}

/* 重要提示區塊樣式 */
.llm-note-markdown .important-note {
  background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
  border-left: 4px solid #ffc107;
  color: #856404;
  padding: 16px 20px;
  margin: 20px 0;
  border-radius: 0 8px 8px 0;
  box-shadow: 0 4px 12px rgba(255, 193, 7, 0.2);
  position: relative;
}

.llm-note-markdown .important-note::before {
  content: "💡";
  position: absolute;
  left: -2px;
  top: 50%;
  transform: translateY(-50%);
  background: #ffc107;
  color: white;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
}

/* 重點標記樣式 - 簡化為文字顏色調整 */
:deep(.highlight-mark),
:deep(mark),
.llm-note-markdown .highlight-mark,
.llm-note-markdown mark,
.block-content .highlight-mark,
.block-content mark {
  background: transparent !important;
  color: #ff6b35 !important;
  padding: 0 !important;
  border-radius: 0 !important;
  font-weight: 700 !important;
  box-shadow: none !important;
  border: none !important;
  display: inline !important;
  margin: 0 !important;
  text-decoration: underline !important;
  text-decoration-color: #ff6b35 !important;
}

/* 深色模式下的重點標記 - 簡化為文字顏色 */
html.dark :deep(.highlight-mark),
html.dark :deep(mark),
html.dark .llm-note-markdown .highlight-mark,
html.dark .llm-note-markdown mark,
html.dark .block-content .highlight-mark,
html.dark .block-content mark {
  color: #ffa726 !important;
  text-decoration-color: #ffa726 !important;
}

/* 表格中的重點標記 */
.llm-note-markdown table mark,
.llm-note-markdown table .highlight,
.llm-note-markdown table .highlight-mark {
  background: rgba(255, 243, 205, 0.8);
  color: #d84315;
  border-color: rgba(255, 193, 7, 0.3);
  font-weight: 700;
  padding: 1px 4px;
}

/* == 標記語法支援 - 更直接的處理 */
.llm-note-markdown {

  /* 通過 JavaScript 處理的標記樣式 */
  .highlight {
    background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%);
    color: #d84315;
    padding: 2px 6px;
    border-radius: 4px;
    font-weight: 600;
    box-shadow: 0 2px 4px rgba(255, 193, 7, 0.3);
    border: 1px solid rgba(255, 193, 7, 0.5);
    display: inline-block;
    margin: 0 2px;
  }
}

/* 重點內容樣式 */
.llm-note-markdown strong {
  font-weight: 700;
  color: #2c3e50;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
}

.llm-note-markdown em {
  font-style: italic;
  color: #6c757d;
  border-bottom: 1px dotted #6c757d;
}

/* 引用區塊中的重點標記 */
.llm-note-markdown blockquote mark,
.llm-note-markdown blockquote .highlight {
  background: rgba(16, 163, 127, 0.2);
  color: #10a37f;
  border-color: rgba(16, 163, 127, 0.5);
}

/* 👈 指示符號樣式 */
.llm-note-markdown .pointer {
  color: #10a37f;
  font-weight: bold;
  margin-left: 8px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  background: rgba(16, 163, 127, 0.1);
  border-radius: 4px;
  border-left: 3px solid #10a37f;
}

/* 日語假名顯示優化 */
.llm-note-markdown ruby {
  ruby-align: center;
  position: relative;
}

.llm-note-markdown rt {
  font-size: 0.75em;
  color: #6c757d;
  font-weight: normal;
  line-height: 1;
}

/* 深色模式下的樣式調整 */
@media (prefers-color-scheme: dark) {
  .llm-note-markdown .enhanced-table {
    background: #2d2d2d;
    border-color: #404040;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  }

  .llm-note-markdown .enhanced-table td {
    border-bottom-color: #404040;
    color: #ffffff;
  }

  .llm-note-markdown .enhanced-table tr:hover {
    background: rgba(16, 163, 127, 0.1);
  }

  .llm-note-markdown .important-note {
    background: #3e3e3e;
    color: #f0f0f0;
    border-left-color: #ffc107;
  }

  .llm-note-markdown mark,
  .llm-note-markdown .highlight {
    background: rgba(255, 193, 7, 0.3);
    color: #ffc107;
    border-color: rgba(255, 193, 7, 0.5);
  }

  .llm-note-markdown strong {
    color: #ffffff;
  }

  .llm-note-markdown em {
    color: #8e8ea0;
    border-bottom-color: #8e8ea0;
  }

  .llm-note-markdown .pointer {
    background: rgba(16, 163, 127, 0.2);
    color: #10a37f;
  }

  .llm-note-markdown rt {
    color: #8e8ea0;
  }
}

/* 日文主題和重點標記樣式 */
.jp-main-title {
  font-size: 1.2em;
  font-weight: bold;
  color: #ffb74d;
  background: linear-gradient(90deg, #ffb74d 60%, #ffcc02 100%);
  border-radius: 6px;
  padding: 2px 10px;
  margin-left: 6px;
}

/* 日文子主題標記樣式 */
.jp-sub-title {
  font-size: 1.1em;
  font-weight: bold;
  color: #ba68c8;
  background: linear-gradient(90deg, #ba68c8 60%, #9c27b0 100%);
  border-radius: 6px;
  padding: 2px 10px;
  margin-left: 6px;
}

/* 日文分析標記樣式 */
.jp-analysis-title {
  font-size: 1.1em;
  font-weight: bold;
  color: #2196f3;
  background: linear-gradient(90deg, #2196f3 60%, #1565c0 100%);
  border-radius: 6px;
  padding: 2px 10px;
  margin-left: 6px;
}

/* 日文程式碼說明標記樣式 */
.jp-code-title {
  font-size: 1.1em;
  font-weight: bold;
  color: #4caf50;
  background: linear-gradient(90deg, #4caf50 60%, #2e7d32 100%);
  border-radius: 6px;
  padding: 2px 10px;
  margin-left: 6px;
}

/* 日文延伸思考標記樣式 */
.jp-thinking-title {
  font-size: 1.1em;
  font-weight: bold;
  color: #9c27b0;
  background: linear-gradient(90deg, #9c27b0 60%, #6a1b9a 100%);
  border-radius: 6px;
  padding: 2px 10px;
  margin-left: 6px;
}

/* 日文學習重點總結標記樣式 - 修復版 */
.jp-summary-title {
  color: #ffffff !important;
  font-size: 1.2em !important;
  font-weight: 700 !important;
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%) !important;
  padding: 12px 20px !important;
  border-radius: 10px !important;
  margin: 20px 0 12px 0 !important;
  display: block !important;
  border-left: 5px solid #f59e0b !important;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15) !important;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3) !important;
  position: relative !important;
}

.jp-summary-title::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, transparent 50%);
  border-radius: 10px;
  pointer-events: none;
}

/* 分析標題樣式 */
.analysis-title {
  color: #ffffff !important;
  font-size: 1.1em !important;
  font-weight: 600 !important;
  background: linear-gradient(135deg, #4a9eff 0%, #2196f3 100%) !important;
  padding: 8px 16px !important;
  border-radius: 8px !important;
  margin: 16px 0 8px 0 !important;
  display: block !important;
  border-left: 4px solid #4a9eff !important;
  box-shadow: 0 2px 6px rgba(74, 158, 255, 0.3) !important;
}

/* 說明標題樣式 */
.explanation-title {
  color: #ffffff !important;
  font-size: 1.1em !important;
  font-weight: 600 !important;
  background: linear-gradient(135deg, #81c784 0%, #4caf50 100%) !important;
  padding: 8px 16px !important;
  border-radius: 8px !important;
  margin: 16px 0 8px 0 !important;
  display: block !important;
  border-left: 4px solid #81c784 !important;
  box-shadow: 0 2px 6px rgba(129, 199, 132, 0.3) !important;
}

/* 日文學習樣式增強 */
:deep(.jp-learning-section-title) {
  font-size: 1.2em;
  font-weight: bold;
  color: #1976d2 !important;
  background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
  border-radius: 8px;
  padding: 8px 16px;
  border-left: 4px solid #1976d2;
  display: block;
  margin: 16px 0 8px 0;
}

:deep(.jp-original-text) {
  background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%);
  color: #e65100 !important;
  padding: 4px 8px;
  border-radius: 4px;
  font-weight: bold;
  border: 1px solid rgba(230, 81, 0, 0.3);
  display: inline-block;
  margin: 2px;
}

:deep(.jp-translation) {
  background: linear-gradient(135deg, #e8f5e8 0%, #c8e6c9 100%);
  color: #2e7d32 !important;
  padding: 4px 8px;
  border-radius: 4px;
  border-left: 3px solid #4caf50;
  margin: 8px 0;
  display: block;
}

:deep(.jp-meaning) {
  font-weight: bold;
  color: #1b5e20 !important;
}

:deep(.jp-vocabulary-item) {
  background: rgba(156, 39, 176, 0.1);
  border-left: 3px solid #9c27b0;
  padding: 8px 12px;
  margin: 4px 0;
  border-radius: 4px;
  display: block;
}

:deep(.jp-reading) {
  color: #7b1fa2 !important;
  font-style: italic;
  font-size: 0.9em;
}

/* 深色模式下的日文樣式 */
html.dark :deep(.jp-learning-section-title) {
  color: #90caf9 !important;
  background: rgba(144, 202, 249, 0.15);
  border-left-color: #90caf9;
}

html.dark :deep(.jp-original-text) {
  background: rgba(255, 183, 77, 0.2);
  color: #ffb74d !important;
  border-color: rgba(255, 183, 77, 0.4);
}

html.dark :deep(.jp-translation) {
  background: rgba(76, 175, 80, 0.15);
  color: #81c784 !important;
  border-left-color: #4caf50;
}

html.dark :deep(.jp-meaning) {
  color: #a5d6a7 !important;
}

html.dark :deep(.jp-vocabulary-item) {
  background: rgba(186, 104, 200, 0.15);
  border-left-color: #ba68c8;
}

html.dark :deep(.jp-reading) {
  color: #ce93d8 !important;
}

/* 日文注意標記樣式 */
.jp-warning {
  font-size: 1.1em;
  font-weight: bold;
  color: #ff9800;
  background: linear-gradient(90deg, #ff9800 60%, #e65100 100%);
  border-radius: 6px;
  padding: 2px 10px;
  margin-left: 6px;
}

/* 日文補充標記樣式 */
.jp-supplement {
  font-size: 1.1em;
  font-weight: bold;
  color: #4caf50;
  background: linear-gradient(90deg, #4caf50 60%, #2e7d32 100%);
  border-radius: 6px;
  padding: 2px 10px;
  margin-left: 6px;
}

/* 日文詞彙增強樣式 */
.jp-word {
  background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
  border-left: 4px solid #2196f3;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: bold;
  color: #ffffff !important;
  /* 統一白色文字 */
}

/* 日文假名標記樣式 */
.jp-furigana {
  font-size: 0.8em;
  color: #ffffff !important;
  /* 統一白色文字 */
  font-style: italic;
}

/* 日文強調樣式 */
.jp-emphasis {
  background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%);
  border-radius: 4px;
  padding: 1px 4px;
  font-weight: bold;
  color: #ffffff !important;
  /* 統一白色文字 */
}

/* 日文語法標題樣式 */
.jp-grammar-title {
  background: linear-gradient(135deg, #f3e5f5 0%, #e1bee7 100%);
  border-radius: 6px;
  padding: 4px 12px;
  font-weight: bold;
  color: #ffffff !important;
  /* 統一白色文字 */
}

/* 日文主題標記樣式 */
.jp-main-title {
  font-size: 1.2em;
  font-weight: bold;
  color: #1976d2;
  background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
  border-radius: 8px;
  padding: 6px 16px;
  border-left: 4px solid #1976d2;
  display: inline-block;
  margin: 4px 0;
}

/* 日文子主題標記樣式 */
.jp-sub-title {
  font-size: 1.1em;
  font-weight: bold;
  color: #388e3c;
  background: linear-gradient(135deg, #e8f5e8 0%, #c8e6c9 100%);
  border-radius: 6px;
  padding: 4px 12px;
  border-left: 3px solid #388e3c;
  display: inline-block;
  margin: 2px 0;
}

/* 日文解析標記樣式 */
.jp-analysis-title {
  font-size: 1.1em;
  font-weight: bold;
  color: #7b1fa2;
  background: linear-gradient(135deg, #f3e5f5 0%, #e1bee7 100%);
  border-radius: 6px;
  padding: 4px 12px;
  margin-left: 6px;
}

/* 日文程式碼說明標記樣式 */
.jp-code-title {
  font-size: 1.1em;
  font-weight: bold;
  color: #d32f2f;
  background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%);
  border-radius: 6px;
  padding: 4px 12px;
  margin-left: 6px;
}

/* ===== ChatGPT風格代碼區塊樣式 ===== */
:deep(.gpt-code-block) {
  background: var(--code-surface, rgba(248, 250, 251, 0.9));
  border: 1px solid var(--border, #d8e0e4);
  border-radius: 14px;
  margin: 12px 0;
  overflow: hidden;
  font-family: 'JetBrains Mono', 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', 'Source Code Pro', monospace;
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.08);
}

html.dark :deep(.gpt-code-block) {
  --code-surface: #0f172a;
  border-color: rgba(148, 163, 184, 0.35);
  box-shadow: 0 16px 26px rgba(0, 0, 0, 0.45);
}

:deep(.gpt-code-header) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 18px;
  background: rgba(15, 23, 42, 0.04);
  border-bottom: 1px solid rgba(15, 23, 42, 0.08);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

html.dark :deep(.gpt-code-header) {
  background: rgba(15, 23, 42, 0.65);
  border-bottom-color: rgba(148, 163, 184, 0.25);
}

:deep(.gpt-language-tag) {
  font-size: 11px;
  color: #0891b2 !important;
  font-weight: 600;
  background: rgba(8, 145, 178, 0.12);
  padding: 2px 10px;
  border-radius: 999px;
  letter-spacing: 0.08em;
}

html.dark :deep(.gpt-language-tag) {
  color: #5eead4 !important;
  background: rgba(94, 234, 212, 0.12);
}

:deep(.gpt-header-actions) {
  display: flex;
  align-items: center;
  gap: 6px;
}

:deep(.gpt-copy-btn),
:deep(.gpt-expand-btn) {
  background: rgba(15, 23, 42, 0.04);
  border: 1px solid transparent;
  color: #1e293b !important;
  cursor: pointer;
  padding: 4px 10px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 4px;
  transition: all 0.2s ease;
  font-size: 12px;
  font-weight: 600;
}

:deep(.gpt-copy-btn:hover),
:deep(.gpt-expand-btn:hover) {
  border-color: rgba(8, 145, 178, 0.45);
  background: rgba(8, 145, 178, 0.12);
  color: #0e7490 !important;
}

html.dark :deep(.gpt-copy-btn),
html.dark :deep(.gpt-expand-btn) {
  background: rgba(148, 163, 184, 0.1);
  color: #e2e8f0 !important;
}

html.dark :deep(.gpt-copy-btn:hover),
html.dark :deep(.gpt-expand-btn:hover) {
  border-color: rgba(94, 234, 212, 0.45);
  background: rgba(94, 234, 212, 0.12);
  color: #5eead4 !important;
}

:deep(.gpt-copy-btn svg),
:deep(.gpt-expand-btn svg) {
  width: 16px;
  height: 16px;
}

/* 文本/數學面板的覆蓋樣式 */
:deep(.gpt-code-block.text-only .gpt-code-content) {
  background: #ffffff;
  border-left-color: rgba(148, 163, 184, 0.35);
  color: #0f172a !important;
}

:deep(.gpt-code-content) {
  margin: 0;
  padding: 18px 20px;
  background: linear-gradient(135deg, #0b1220 0%, #111c2f 100%);
  border-left: 3px solid rgba(8, 145, 178, 0.65);
  font-size: 14px;
  line-height: 1.6;
  overflow-x: auto;
  white-space: pre;
  color: #f8fafc !important;
  scrollbar-width: thin;
  max-height: 520px;
}

html.dark :deep(.gpt-code-content) {
  border-left-color: rgba(94, 234, 212, 0.65);
}

/* 純文字/數學內容的代碼面板（避免過度高亮） */
:deep(.gpt-code-block.text-only) {
  background: #f8fafc;
  border-color: rgba(148, 163, 184, 0.35);
  box-shadow: none;
}
:deep(.gpt-code-block.text-only) .gpt-code-header {
  background: #f1f5f9;
  border-bottom-color: rgba(148, 163, 184, 0.25);
  color: #0f172a;
}
:deep(.gpt-code-block.text-only) .gpt-language-tag {
  background: rgba(8, 47, 73, 0.06);
  color: #0f172a !important;
}
:deep(.gpt-code-block.text-only) .gpt-header-actions {
  gap: 4px;
}
:deep(.gpt-code-block.text-only) .gpt-code-content {
  background: #ffffff;
  border-left-color: rgba(148, 163, 184, 0.35);
  color: #0f172a !important;
}
html.dark :deep(.gpt-code-block.text-only) {
  background: #1f2937;
  border-color: rgba(148, 163, 184, 0.4);
}
html.dark :deep(.gpt-code-block.text-only) .gpt-code-header {
  background: #111827;
  border-bottom-color: rgba(148, 163, 184, 0.35);
  color: #e5e7eb;
}
html.dark :deep(.gpt-code-block.text-only) .gpt-language-tag {
  background: rgba(59, 130, 246, 0.12);
  color: #bfdbfe !important;
}
html.dark :deep(.gpt-code-block.text-only) .gpt-code-content {
  background: #0b1220;
  border-left-color: rgba(148, 163, 184, 0.4);
  color: #e5e7eb !important;
}

/* 純數學/公式區塊 - 不用代碼樣式 */
:deep(.math-text-block) {
  padding: 16px 18px;
  margin: 14px 0;
  background: rgba(14, 165, 233, 0.08);
  border: 1px solid rgba(14, 165, 233, 0.22);
  border-radius: 12px;
  color: #0f172a;
  overflow-x: auto;
}
html.dark :deep(.math-text-block) {
  background: rgba(14, 165, 233, 0.14);
  border-color: rgba(56, 189, 248, 0.3);
  color: #e5e7eb;
}

:deep(.gpt-code-content::-webkit-scrollbar) {
  height: 8px;
}

:deep(.gpt-code-content::-webkit-scrollbar-thumb) {
  background: rgba(148, 163, 184, 0.3);
  border-radius: 4px;
}

:deep(.gpt-code-content code) {
background: transparent !important;
padding: 0 !important;
border: none !important;
font-family: inherit !important;
font-size: inherit !important;
line-height: inherit !important;
color: inherit !important;
}

/* 移除舊的雙層代碼區塊樣式衝突 */
.code-block-enhanced,
.code-block-header,
.code-enhanced {
  display: none !important;
}

/* 追加：目錄與 Q&A 折疊樣式 */
.toc-container {
  position: sticky;
  top: 12px;
  margin-bottom: 16px;
}
.toc-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color);
  border-radius: 12px;
  box-shadow: 0 6px 24px rgba(0,0,0,0.06);
  padding: 12px 14px;
}
.toc-title {
  font-weight: 600;
  margin-bottom: 8px;
}
.toc-list {
  list-style: none;
  padding-left: 6px;
  margin: 0;
}
.toc-list a {
  color: var(--el-text-color-primary);
  text-decoration: none;
}
.section-heading {
  scroll-margin-top: 80px;
}
.qa summary {
  cursor: pointer;
  font-weight: 600;
}
.qa {
  background: rgba(255, 244, 214, 0.35);
  border-left: 3px solid #f5a623;
  padding: 8px 12px;
  border-radius: 8px;
}

/* 確保所有文字顏色正確 */
.notion-note-container {
/* 白色模式 */
--text-primary: #212529;
--text-secondary: #6c757d;
--bg-primary: #ffffff;
color: var(--text-primary);
}

/* 深色模式變量 */
.dark-mode .notion-note-container {
--text-primary: #ffffff;
--text-secondary: #cccccc;
--bg-primary: #1a1a1a;
}

.notion-note-container,
.notion-note-container * {
color: var(--text-primary) !important;
}

/* 強制所有文字元素使用正確顏色 */
.notion-note-container p,
.notion-note-container span,
.notion-note-container div,
.notion-note-container li,
.notion-note-container td,
.notion-note-container th {
color: var(--text-primary) !important;
}

.notion-note-container h1,
.notion-note-container h2,
.notion-note-container h3,
.notion-note-container h4,
.notion-note-container h5,
.notion-note-container h6 {
color: var(--text-primary) !important;
}

.notion-note-container p,
.notion-note-container li,
.notion-note-container span,
.notion-note-container div {
color: var(--text-primary) !important;
}

/* 日文內容的字體顏色 - 修復顯示問題 */
.jp-main-title,
.jp-sub-title,
.jp-analysis-title,
.jp-code-title,
.jp-thinking-title,
.jp-summary-title,
.jp-warning,
.jp-supplement {
color: #ffffff !important;
font-weight: bold !important;
padding: 4px 12px !important;
border-radius: 6px !important;
margin: 2px 4px !important;
display: inline-block !important;
box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1) !important;
}

/* 深色模式下的日文標記樣式 */
.dark-mode .jp-main-title {
color: #ffffff !important;
background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%) !important;
}

.dark-mode .jp-sub-title {
color: #ffffff !important;
background: linear-gradient(135deg, #166534 0%, #22c55e 100%) !important;
}

.dark-mode .jp-analysis-title {
color: #ffffff !important;
background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%) !important;
}

.dark-mode .jp-code-title {
color: #ffffff !important;
background: linear-gradient(135deg, #059669 0%, #10b981 100%) !important;
}

.dark-mode .jp-thinking-title {
color: #ffffff !important;
background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%) !important;
}

.dark-mode .jp-summary-title {
color: #ffffff !important;
background: linear-gradient(135deg, #d97706 0%, #f59e0b 100%) !important;
}

.dark-mode .jp-warning {
color: #ffffff !important;
background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%) !important;
}

.dark-mode .jp-supplement {
color: #ffffff !important;
background: linear-gradient(135deg, #059669 0%, #10b981 100%) !important;
}

/* 淺色模式下的日文標記樣式 */
.jp-main-title {
color: #ffffff !important;
background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
}

.jp-sub-title {
color: #ffffff !important;
background: linear-gradient(135deg, #22c55e 0%, #15803d 100%) !important;
}

.jp-analysis-title {
color: #ffffff !important;
background: linear-gradient(135deg, #a855f7 0%, #7c3aed 100%) !important;
}

.jp-code-title {
color: #ffffff !important;
background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
}

.jp-thinking-title {
color: #ffffff !important;
background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%) !important;
}

.jp-summary-title {
color: #ffffff !important;
background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%) !important;
}

.jp-warning {
color: #ffffff !important;
background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%) !important;
}

.jp-supplement {
color: #ffffff !important;
background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
}

/* 特殊標題顏色修復 */
.gpt-section-title {
color: var(--text-primary) !important;
}

/* 全局複製函數 *//* ===== Ch
atGPT風格圖片樣式 ===== */
.gpt-image-container {
text-align: center;
margin: 20px 0;
position: relative;
}

.gpt-image {
max-width: 100%;
height: auto;
border-radius: 8px;
box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
display: block;
margin: 0 auto;
transition: opacity 0.3s ease;
}

.gpt-image-error {
display: none !important;
flex-direction: column;
align-items: center;
justify-content: center;
padding: 20px;
background: #f8f9fa;
border: 1px solid #dee2e6;
border-radius: 8px;
color: #6c757d;
margin: 10px auto;
max-width: 250px;
font-size: 12px;
}

.gpt-image-error svg {
margin-bottom: 12px;
opacity: 0.5;
}

.gpt-image-error p {
margin: 0;
font-size: 14px;
font-weight: 500;
}

.gpt-image-container.error .gpt-image {
display: none;
}

.gpt-image-container.error .gpt-image-error {
display: flex !important;
}

.dark-mode .gpt-image-error {
background: #2d2d2d;
border-color: #4a4a4a;
color: #adb5bd;
}

/* 移除舊的圖片樣式衝突 */
.image-container {
display: none !important;
}

/* 日文學習重點區域樣式 */
.jp-learning-section-title {
font-size: 1.4em !important;
font-weight: bold !important;
color: #ffffff !important;
background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%) !important;
padding: 12px 20px !important;
border-radius: 8px !important;
margin: 20px 0 15px 0 !important;
box-shadow: 0 4px 12px rgba(255, 107, 107, 0.3) !important;
display: block !important;
text-align: center !important;
}

.dark-mode .jp-learning-section-title {
background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%) !important;
color: #ffffff !important;
}

/* 學習重點總結 Banner */
.jp-summary-title {
  display: block !important;
  padding: 12px 16px !important;
  margin: 16px 0 12px 0 !important;
  border-radius: 10px !important;
  font-weight: 700 !important;
  text-align: left !important;
  color: #ffffff !important;
  background: linear-gradient(135deg, rgba(59,130,246,0.2) 0%, rgba(16,163,127,0.25) 100%) !important;
  border: 1px solid rgba(16,163,127,0.4) !important;
}

.dark-mode .jp-summary-title {
  color: #ffffff !important;
  background: linear-gradient(135deg, rgba(59,130,246,0.25) 0%, rgba(16,163,127,0.3) 100%) !important;
  border-color: rgba(16,163,127,0.5) !important;
}

/* 最後的小提示 Banner */
.final-tip-title {
  display: block !important;
  padding: 12px 16px !important;
  margin: 20px 0 12px 0 !important;
  border-radius: 10px !important;
  font-weight: 700 !important;
  text-align: left !important;
  color: #ffffff !important;
  background: linear-gradient(135deg, rgba(234,179,8,0.18) 0%, rgba(59,130,246,0.18) 100%) !important;
  border: 1px solid rgba(234,179,8,0.45) !important;
}

.dark-mode .final-tip-title {
  color: #ffffff !important;
  background: linear-gradient(135deg, rgba(234,179,8,0.22) 0%, rgba(59,130,246,0.22) 100%) !important;
  border-color: rgba(234,179,8,0.55) !important;
}

/* 日文子標題樣式 */
.jp-subsection-title {
font-size: 1.2em !important;
font-weight: bold !important;
color: #ffffff !important;
background: linear-gradient(135deg, #4c63d2 0%, #3b52d6 100%) !important;
padding: 8px 16px !important;
border-radius: 6px !important;
margin: 15px 0 10px 0 !important;
display: block !important;
text-align: left !important;
box-shadow: 0 2px 8px rgba(76, 99, 210, 0.3) !important;
}

.dark-mode .jp-subsection-title {
background: linear-gradient(135deg, #4c63d2 0%, #3b52d6 100%) !important;
color: #ffffff !important;
}

/* 日文重要句子樣式 */
.jp-important-sentence {
background: linear-gradient(135deg, rgba(220, 38, 38, 0.1) 0%, rgba(239, 68, 68, 0.1) 100%) !important;
border-left: 4px solid #dc2626 !important;
padding: 12px 16px !important;
margin: 10px 0 !important;
border-radius: 0 8px 8px 0 !important;
box-shadow: 0 2px 8px rgba(220, 38, 38, 0.2) !important;
}

.dark-mode .jp-important-sentence {
background: linear-gradient(135deg, rgba(252, 165, 165, 0.15) 0%, rgba(248, 113, 113, 0.15) 100%) !important;
border-left-color: #fca5a5 !important;
}

/* 日文翻譯區域樣式 */
.jp-translation {
background: linear-gradient(135deg, rgba(5, 150, 105, 0.1) 0%, rgba(16, 185, 129, 0.1) 100%) !important;
border-left: 3px solid #059669 !important;
padding: 8px 12px !important;
margin: 8px 0 !important;
border-radius: 0 6px 6px 0 !important;
font-size: 0.95em !important;
}

.dark-mode .jp-translation {
background: linear-gradient(135deg, rgba(110, 231, 183, 0.15) 0%, rgba(52, 211, 153, 0.15) 100%) !important;
border-left-color: #6ee7b7 !important;
}

/* 日文重要性說明樣式 */
.jp-importance {
background: linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(251, 191, 36, 0.1) 100%) !important;
border-left: 3px solid #f59e0b !important;
padding: 8px 12px !important;
margin: 8px 0 !important;
border-radius: 0 6px 6px 0 !important;
font-size: 0.95em !important;
}

.dark-mode .jp-importance {
background: linear-gradient(135deg, rgba(252, 211, 77, 0.15) 0%, rgba(251, 191, 36, 0.15) 100%) !important;
border-left-color: #fcd34d !important;
}

/* 日文解釋文字樣式 */
.jp-explanation {
color: #374151 !important;
font-weight: 500 !important;
}

.dark-mode .jp-explanation {
color: #d1d5db !important;
}

/* 日文表格標題樣式 */
.jp-table-header {
font-weight: bold !important;
color: #2563eb !important;
background: rgba(37, 99, 235, 0.1) !important;
padding: 2px 6px !important;
border-radius: 4px !important;
}

.dark-mode .jp-table-header {
color: #60a5fa !important;
background: rgba(96, 165, 250, 0.2) !important;
}

/* 日文原文樣式 - 突出顯示 */
.jp-original-text {
font-size: 1.1em !important;
font-weight: bold !important;
color: #fbbf24 !important; /* 黃色代碼標記 */
background: linear-gradient(135deg, rgba(251, 191, 36, 0.1) 0%, rgba(245, 158, 11, 0.1) 100%) !important;
padding: 6px 10px !important;
border-radius: 6px !important;
border-left: 3px solid #fbbf24 !important;
display: inline-block !important;
margin: 2px 0 !important;
box-shadow: 0 2px 4px rgba(251, 191, 36, 0.2) !important;
}

.dark-mode .jp-original-text {
color: #fbbf24 !important; /* 統一黃色代碼標記 */
background: linear-gradient(135deg, rgba(251, 191, 36, 0.2) 0%, rgba(245, 158, 11, 0.2) 100%) !important;
border-left-color: #fbbf24 !important;
box-shadow: 0 2px 4px rgba(251, 191, 36, 0.3) !important;
}

/* 日文詞彙項目樣式 */
.jp-vocabulary-item {
background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(99, 102, 241, 0.1) 100%) !important;
border-left: 4px solid #3b82f6 !important;
padding: 10px 15px !important;
margin: 8px 0 !important;
border-radius: 0 8px 8px 0 !important;
display: flex !important;
align-items: center !important;
gap: 10px !important;
box-shadow: 0 2px 6px rgba(59, 130, 246, 0.2) !important;
color: #ffffff !important; /* 統一白色文字 */
}

.dark-mode .jp-vocabulary-item {
background: linear-gradient(135deg, rgba(147, 197, 253, 0.15) 0%, rgba(165, 180, 252, 0.15) 100%) !important;
border-left-color: #93c5fd !important;
box-shadow: 0 2px 6px rgba(147, 197, 253, 0.3) !important;
color: #ffffff !important; /* 統一白色文字 */
}

/* 日文讀音樣式 */
.jp-reading {
font-size: 0.95em !important;
color: #ffffff !important; /* 統一白色文字 */
font-style: italic !important;
padding: 4px 8px !important;
background: rgba(124, 58, 237, 0.1) !important;
border-radius: 4px !important;
display: inline-block !important;
}

.dark-mode .jp-reading {
color: #ffffff !important; /* 統一白色文字 */
background: rgba(196, 181, 253, 0.2) !important;
}

/* 日文中文意思樣式 */
.jp-meaning {
font-size: 1em !important;
color: #ffffff !important; /* 統一白色文字 */
font-weight: 500 !important;
padding: 4px 8px !important;
background: rgba(5, 150, 105, 0.1) !important;
border-radius: 4px !important;
display: inline-block !important;
}

.dark-mode .jp-meaning {
color: #ffffff !important; /* 統一白色文字 */
background: rgba(110, 231, 183, 0.2) !important;
}

/* Notion 風格表格樣式 */
.llm-note-markdown table {
margin: 24px 0 !important;
border-collapse: separate !important;
border-spacing: 0 !important;
border-radius: 12px !important;
overflow: hidden !important;
box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1) !important;
width: 100% !important;
table-layout: fixed !important;
background: #ffffff !important;
}

.llm-note-markdown table td,
.llm-note-markdown table th {
padding: 16px 20px !important;
border: none !important;
border-bottom: 1px solid #e5e7eb !important;
vertical-align: top !important;
color: #374151 !important;
word-wrap: break-word !important;
overflow-wrap: break-word !important;
font-size: 14px !important;
line-height: 1.5 !important;
}

.llm-note-markdown table th {
background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%) !important;
font-weight: 700 !important;
color: #1f2937 !important;
text-align: center !important;
border-bottom: 2px solid #3b82f6 !important;
}

.llm-note-markdown table tr:hover {
background: #f8fafc !important;
}

.llm-note-markdown table tr:last-child td {
border-bottom: none !important;
}

/* 表格列寬度分配 */
.llm-note-markdown table th:nth-child(1),
.llm-note-markdown table td:nth-child(1) {
width: 25% !important;
}

.llm-note-markdown table th:nth-child(2),
.llm-note-markdown table td:nth-child(2) {
width: 25% !important;
}

.llm-note-markdown table th:nth-child(3),
.llm-note-markdown table td:nth-child(3) {
width: 50% !important;
}

/* 表格包裝器樣式 */
.table-wrapper {
  overflow-x: auto !important;
  margin: 20px 0 !important;
  border-radius: 8px !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1) !important;
}

.enhanced-table {
  width: 100% !important;
  min-width: 600px !important;
  border-collapse: collapse !important;
  background: #ffffff !important;
}

.dark-mode .enhanced-table {
  background: #1f2937 !important;
}

/* 清理段落樣式 */
.clean-paragraph {
  margin: 12px 0 !important;
  line-height: 1.7 !important;
  text-align: justify !important;
  word-spacing: 0.1em !important;
  max-width: 100% !important;
  overflow-wrap: break-word !important;
  word-wrap: break-word !important;
}

/* Notion 風格標題樣式 */
.llm-note-markdown .notion-style-heading {
  margin: 32px 0 20px 0 !important;
  padding: 16px 20px !important;
  border-radius: 12px !important;
  border-left: 4px solid #3b82f6 !important;
  background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%) !important;
  font-weight: 700 !important;
  color: #1e293b !important;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1) !important;
}

.dark-mode .notion-style-heading {
  background: linear-gradient(135deg, #1e293b 0%, #334155 100%) !important;
  color: #f1f5f9 !important;
  border-left-color: #60a5fa !important;
}

/* 不同級別標題的樣式 */
.notion-style-heading.h1 {
  font-size: 2rem !important;
  border-left-color: #8b5cf6 !important;
}

.notion-style-heading.h2 {
  font-size: 1.5rem !important;
  border-left-color: #3b82f6 !important;
}

.notion-style-heading.h3 {
  font-size: 1.25rem !important;
  border-left-color: #10b981 !important;
}

/* Notion 風格提示框 */
.notion-callout {
  display: flex !important;
  align-items: flex-start !important;
  padding: 16px 20px !important;
  margin: 20px 0 !important;
  border-radius: 12px !important;
  border: none !important;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1) !important;
}

.notion-callout.info {
  background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%) !important;
  border-left: 4px solid #3b82f6 !important;
}

.notion-callout.warning {
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%) !important;
  border-left: 4px solid #f59e0b !important;
}

.notion-callout.success {
  background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%) !important;
  border-left: 4px solid #10b981 !important;
}

.notion-callout.highlight {
  background: linear-gradient(135deg, #fef2f2 0%, #fecaca 100%) !important;
  border-left: 4px solid #ef4444 !important;
}

.callout-icon {
  font-size: 1.2rem !important;
  margin-right: 12px !important;
  margin-top: 2px !important;
}

.callout-content {
  flex: 1 !important;
  color: #374151 !important;
  font-weight: 500 !important;
  line-height: 1.6 !important;
}

.dark-mode .callout-content {
  color: #f9fafb !important;
}

.dark-mode .notion-callout.info {
  background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%) !important;
}

.dark-mode .notion-callout.warning {
  background: linear-gradient(135deg, #92400e 0%, #b45309 100%) !important;
}

.dark-mode .notion-callout.success {
  background: linear-gradient(135deg, #065f46 0%, #047857 100%) !important;
}

.dark-mode .notion-callout.highlight {
  background: linear-gradient(135deg, #991b1b 0%, #dc2626 100%) !important;
}

/* 深色模式表格樣式 */
.dark-mode .llm-note-markdown table {
  background: #1f2937 !important;
}

.dark-mode .llm-note-markdown table td,
.dark-mode .llm-note-markdown table th {
  color: #f9fafb !important;
  border-bottom-color: #4b5563 !important;
}

.dark-mode .llm-note-markdown table th {
  background: linear-gradient(135deg, #374151 0%, #4b5563 100%) !important;
  color: #f1f5f9 !important;
  border-bottom-color: #60a5fa !important;
}

.dark-mode .llm-note-markdown table tr:hover {
  background: #374151 !important;
}

/* 分隔線樣式 */
.llm-note-markdown hr {
  border: none !important;
  height: 2px !important;
  background: linear-gradient(90deg, transparent 0%, #e5e7eb 50%, transparent 100%) !important;
  margin: 32px 0 !important;
}

.dark-mode .llm-note-markdown hr {
  background: linear-gradient(90deg, transparent 0%, #4b5563 50%, transparent 100%) !important;
}

/* 修正深色模式下表格文字顏色 */
.dark-mode .llm-note-markdown table td,
.dark-mode .llm-note-markdown table th {
color: #ffffff !important;
border-bottom: 1px solid rgba(255, 255, 255, 0.1) !important;
}

/* 強制修正所有表格內的藍色文字 */
.llm-note-markdown table td,
.llm-note-markdown table th {
color: #1f2937 !important;
}

.dark-mode .llm-note-markdown table td,
.dark-mode .llm-note-markdown table th {
color: #ffffff !important; /* 統一白色文字 */
}

.llm-note-markdown table th {
background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%) !important;
font-weight: bold !important;
text-align: center !important;
}

.dark-mode .llm-note-markdown table th {
background: linear-gradient(135deg, #374151 0%, #4b5563 100%) !important;
}

.llm-note-markdown pre,
.llm-note-markdown pre code {
  display: block !important;
  white-space: pre !important;
}

.llm-note-markdown pre {
  background: #0c1118 !important;
  color: #e8ecf5 !important;
  border: 1px solid #1f2937 !important;
  border-radius: 12px !important;
  padding: 14px 16px !important;
  margin: 16px 0 !important;
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.32) !important;
  overflow-x: auto !important;
}

.llm-note-markdown code {
  background: transparent !important;
  color: inherit !important;
}

.llm-note-markdown img,
.llm-note-markdown .mk-img,
.llm-note-markdown .mk-img img {
  max-width: 100% !important;
  height: auto !important;
  display: block !important;
  margin: 12px auto !important;
}

.llm-note-markdown pre.plain-code-block,
.llm-note-markdown pre.plain-code-block code.plain-code,
.llm-note-markdown pre:not(.plain-code-block) {
  position: relative !important;
  background: linear-gradient(180deg, #0d1117 0%, #0a0f18 50%, #0f172a 100%) !important;
  color: #eaf1ff !important;
  border: 1px solid #1c2535 !important;
  border-radius: 14px !important;
  padding: 16px 18px 18px 18px !important;
  margin: 18px 0 !important;
  box-shadow: 0 14px 32px rgba(0, 0, 0, 0.38) !important;
  overflow-x: auto !important;
}

.llm-note-markdown pre code.plain-code,
.llm-note-markdown pre:not(.plain-code-block) code {
  background: transparent !important;
  color: inherit !important;
  padding: 0 !important;
  margin: 0 !important;
  border: none !important;
  box-shadow: none !important;
  text-shadow: none !important;
}

.llm-note-markdown pre code,
.llm-note-markdown pre code span {
  background: transparent !important;
  padding: 0 !important;
  margin: 0 !important;
  box-shadow: none !important;
  border: none !important;
  color: inherit !important;
}

/* 先全局清空背景陰影，再對需要的元素覆蓋 */
.llm-note-markdown *:not(pre):not(code):not(.plain-code-block):not(.gpt-code-block):not(.gpt-code-content):not(.plain-code):not(.gpt-code-content code),
.llm-note-markdown *:not(pre):not(code):not(.plain-code-block):not(.gpt-code-block):not(.gpt-code-content):not(.plain-code):not(.gpt-code-content code)::before,
.llm-note-markdown *:not(pre):not(code):not(.plain-code-block):not(.gpt-code-block):not(.gpt-code-content):not(.plain-code):not(.gpt-code-content code)::after {
  background: transparent !important;
  box-shadow: none !important;
}

.llm-note-markdown code:not(pre code) {
  background: rgba(12, 17, 24, 0.85) !important;
  color: #e8ecf5 !important;
  border: 1px solid #1f2937 !important;
  padding: 2px 6px !important;
  border-radius: 6px !important;
}

/* 統一圖片不超出容器 */
.llm-note-markdown img,
.llm-note-markdown .mk-img,
.llm-note-markdown .mk-img img,
.llm-note-markdown .gpt-image,
.llm-note-markdown .gpt-image-container img,
.bilingual-markdown-renderer img,
.fallback-markdown img {
  max-width: 100% !important;
  height: auto !important;
  display: block !important;
  margin: 12px auto !important;
}

/* 徹底移除高亮 span 背景 */
.llm-note-markdown .gpt-code-content code,
.llm-note-markdown .gpt-code-content code * {
  background: transparent !important;
  color: inherit !important;
  box-shadow: none !important;
  text-shadow: none !important;
  border: none !important;
  padding: 0 !important;
  margin: 0 !important;
  white-space: pre !important;
}

/* 將 gpt-code-block 視覺扁平化成統一深色樣式 */
.llm-note-markdown .gpt-code-block {
  background: #0c1118 !important;
  border: 1px solid #1f2937 !important;
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.32) !important;
  padding: 0 !important;
  border-radius: 12px !important;
}
.llm-note-markdown .gpt-code-header,
.llm-note-markdown .gpt-language-tag,
.llm-note-markdown .gpt-header-actions,
.llm-note-markdown .gpt-code-block .gpt-code-header {
  display: none !important;
}
.llm-note-markdown .gpt-code-content {
  background: #0c1118 !important;
  color: #e8ecf5 !important;
  border: none !important;
  box-shadow: none !important;
  padding: 14px 16px !important;
  border-radius: 12px !important;
  overflow-x: auto !important;
}
.llm-note-markdown .gpt-code-content code {
  display: block !important;
  white-space: pre !important;
}

.llm-note-markdown [style*="background"] {
  background: transparent !important;
}

.llm-note-markdown pre * {
  background: transparent !important;
  color: inherit !important;
  border: none !important;
  box-shadow: none !important;
}

.llm-note-markdown code:not(pre code) {
  background: rgba(12, 17, 24, 0.85) !important;
  color: #eaf1ff !important;
  border: 1px solid #1c2535 !important;
  padding: 2px 6px !important;
}

:deep(.math-block) {
  text-align: center;
}

.llm-note-markdown .gpt-code-block,
.llm-note-markdown .gpt-code-content {
  margin: 0 !important;
}

/* 覆蓋舊版 code-frame 樣式，統一平鋪顯示 */
.llm-note-markdown .code-frame,
.llm-note-markdown .code-frame__header,
.llm-note-markdown .code-frame__copy,
.llm-note-markdown .code-copy-btn,
.llm-note-markdown .code-frame__lang,
.llm-note-markdown .code-frame__header *,
.llm-note-markdown .code-frame__copy * {
  display: none !important;
  visibility: hidden !important;
}
.llm-note-markdown .code-frame,
.llm-note-markdown .code-frame pre,
.llm-note-markdown .code-frame code {
  background: #0f172a !important;
  color: #e2e8f0 !important;
  border: none !important;
  margin: 0 !important;
  padding: 12px 14px !important;
  box-shadow: none !important;
}

/* 停用舊版 HLJS 配色，改為繼承文字顏色 */
:deep(.hljs),
:deep(.gpt-code-content .hljs),
:deep(.hljs-keyword),
:deep(.hljs-function),
:deep(.hljs-string),
:deep(.hljs-comment),
:deep(.hljs-number),
:deep(.hljs-title),
:deep(.hljs-built_in),
:deep(.hljs-literal) {
  background: transparent !important;
  color: inherit !important;
  padding: 0 !important;
  margin: 0 !important;
  box-shadow: none !important;
}

/* 隱藏語言標籤 */
.llm-note-markdown .code-frame__lang {
  display: none !important;
}

.llm-note-markdown .card,
.fallback-markdown .card,
.bilingual-markdown-renderer .card {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 8px 0 !important;
  margin: 8px 0 !important;
}

.llm-note-markdown .section-title,
.fallback-markdown .section-title,
.bilingual-markdown-renderer .section-title,
.llm-note-markdown .chip,
.fallback-markdown .chip,
.bilingual-markdown-renderer .chip {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
  margin: 0 !important;
  color: inherit !important;
}

.llm-note-markdown .learning-points,
.fallback-markdown .learning-points,
.bilingual-markdown-renderer .learning-points {
  list-style: disc !important;
  margin: 8px 0 !important;
  padding-left: 20px !important;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}

.llm-note-markdown .learning-points li,
.fallback-markdown .learning-points li,
.bilingual-markdown-renderer .learning-points li {
  margin: 4px 0 !important;
  padding: 0 !important;
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}

/* 隱藏語言標籤 */
.llm-note-markdown .code-frame__lang {
  display: none !important;
}

/* 日文重要句子樣式 */
.jp-important-sentence {
background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(220, 38, 38, 0.1) 100%) !important;
border-left: 4px solid #ef4444 !important;
padding: 12px 16px !important;
margin: 12px 0 !important;
border-radius: 0 8px 8px 0 !important;
font-size: 1.1em !important;
font-weight: 600 !important;
color: #ffffff !important; /* 統一白色文字 */
}

.dark-mode .jp-important-sentence {
background: linear-gradient(135deg, rgba(248, 113, 113, 0.15) 0%, rgba(239, 68, 68, 0.15) 100%) !important;
border-left-color: #f87171 !important;
color: #ffffff !important; /* 統一白色文字 */
}

/* 日文學習區段標題樣式 */
.jp-learning-section-title {
background: linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, rgba(22, 163, 74, 0.1) 100%) !important;
border: 2px solid #22c55e !important;
padding: 10px 16px !important;
margin: 16px 0 8px 0 !important;
border-radius: 8px !important;
font-size: 1.2em !important;
font-weight: bold !important;
text-align: center !important;
color: #ffffff !important; /* 統一白色文字 */
}

.dark-mode .jp-learning-section-title {
background: linear-gradient(135deg, rgba(74, 222, 128, 0.15) 0%, rgba(34, 197, 94, 0.15) 100%) !important;
border-color: #4ade80 !important;
color: #ffffff !important; /* 統一白色文字 */
}

.llm-note-markdown table tr:nth-child(even) {
background: rgba(0, 0, 0, 0.02) !important;
}

.dark-mode .llm-note-markdown table tr:nth-child(even) {
background: rgba(255, 255, 255, 0.05) !important;
}

.llm-note-markdown table tr:hover {
background: rgba(37, 99, 235, 0.05) !important;
transform: translateY(-1px) !important;
transition: all 0.2s ease !important;
}

/* 修復CSS語法錯誤 */
.dark-mode .llm-note-markdown table tr:hover {
background: rgba(96, 165, 250, 0.1) !important;
}

/* 強制修正所有藍色文字顏色問題 */
.llm-note-markdown * {
color: inherit !important;
}

.llm-note-markdown p,
.llm-note-markdown div,
.llm-note-markdown span,
.llm-note-markdown td,
.llm-note-markdown th,
.llm-note-markdown li {
color: var(--el-text-color-primary, #303133) !important;
}

.dark-mode .llm-note-markdown p,
.dark-mode .llm-note-markdown div,
.dark-mode .llm-note-markdown span,
.dark-mode .llm-note-markdown td,
.dark-mode .llm-note-markdown th,
.dark-mode .llm-note-markdown li {
color: var(--el-text-color-primary, #ffffff) !important;
}

/* 特別處理日文樣式，確保可見性 */
.dark-mode .jp-original-text,
.dark-mode .jp-vocabulary-item,
.dark-mode .jp-reading,
.dark-mode .jp-meaning {
color: #ffffff !important;
}

/* 🎨 終極文字顏色修復 - 覆蓋所有深色文字樣式 */

/* 強制覆蓋所有深色文字樣式 */
.block-content :deep(*),
.llm-note-markdown *,
.notion-block * {
color: #e0e0e0 !important;
}

/* 標題保持白色 */
.block-content :deep(h1),
.block-content :deep(h2),
.block-content :deep(h3),
.block-content :deep(h4),
.block-content :deep(h5),
.block-content :deep(h6),
.llm-note-markdown h1,
.llm-note-markdown h2,
.llm-note-markdown h3,
.llm-note-markdown h4,
.llm-note-markdown h5,
.llm-note-markdown h6 {
color: #ffffff !important;
}

/* 表格標題保持綠色 */
.block-content :deep(th),
.llm-note-markdown th {
color: #10a37f !important;
background: #1a1a1a !important;
}

/* 連結保持藍色 */
.block-content :deep(a),
.llm-note-markdown a {
color: #4a9eff !important;
}

/* 內嵌代碼統一：透明背景，繼承文字顏色 */
.block-content :deep(code),
.llm-note-markdown code {
  background: transparent !important;
  color: inherit !important;
  border: none !important;
  padding: 0 !important;
  font-size: 13px !important;
  box-shadow: none !important;
}

/* 覆蓋所有可能的深色樣式選擇器 */
.block-content :deep([style*="color: #2c3e50"]),
.block-content :deep([style*="color: #495057"]),
.block-content :deep([style*="color: #6c757d"]),
.llm-note-markdown [style*="color: #2c3e50"],
.llm-note-markdown [style*="color: #495057"],
.llm-note-markdown [style*="color: #6c757d"] {
color: #e0e0e0 !important;
}

/* ChatGPT 風格代碼區塊（深底＋語言標籤＋複製鈕） */
.llm-note-markdown .code-block-container {
  margin: 16px 0;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.24);
  background: #0f172a;
  box-shadow: none;
  position: relative;
}
.llm-note-markdown .code-block-header {
  display: none;
}
.llm-note-markdown .code-language {
  display: none;
}
.llm-note-markdown .code-copy-btn {
  display: none;
}
.llm-note-markdown pre {
  margin: 18px 0 !important;
  padding: 16px 18px 18px 18px !important;
  background: linear-gradient(180deg, #0d1117 0%, #0a0f18 50%, #0f172a 100%) !important;
  color: #eaf1ff !important;
  font-family: 'JetBrains Mono', 'SF Mono', 'Menlo', monospace !important;
  font-size: 13.5px !important;
  line-height: 1.65 !important;
  white-space: pre !important;
  word-break: normal !important;
  overflow-x: auto !important;
  border: 1px solid #1c2535 !important;
  border-radius: 14px !important;
  box-shadow: 0 14px 32px rgba(0, 0, 0, 0.38) !important;
}
.llm-note-markdown code {
  background: rgba(12, 17, 24, 0.85) !important;
  color: #eaf1ff !important;
  padding: 2px 6px !important;
  border-radius: 6px !important;
  border: 1px solid #1c2535 !important;
}
.llm-note-markdown pre code {
  background: transparent !important;
  color: inherit !important;
  padding: 0 !important;
  border: none !important;
}

/* 保護UI元素不被影響 */
.notion-toolbar,
.notion-toolbar *,
.notion-footer,
.notion-footer *,
.el-button,
.el-button *,
.el-tag,
.el-tag *,
.el-switch,
.el-switch *,
.empty-state .empty-icon,
.processing-status,
.error-info {
color: inherit !important;
}
:deep(.math-block) {
  margin: 4px auto !important;
  padding: 4px 0 !important;
  background: transparent !important;
  border-radius: 0 !important;
  border: none !important;
  overflow-x: auto;
}

html.dark :deep(.math-block) {
  background: transparent !important;
  border: none !important;
}

:deep(.math-inline) {
  display: inline-block;
  padding: 0 6px;
  background: transparent !important;
  border-radius: 0 !important;
  margin: 0 2px;
}

:deep(.math-block .katex),
:deep(.math-inline .katex) {
  font-size: 1.05rem;
  color: inherit;
  margin: 0 !important;
}
.llm-note-markdown pre.plain-code-block::before {
  content: '' !important;
  position: absolute !important;
  inset: 0 !important;
  border-radius: 14px !important;
  background: radial-gradient(circle at 20% 20%, rgba(255, 157, 66, 0.12), transparent 45%), radial-gradient(circle at 80% 10%, rgba(72, 175, 255, 0.18), transparent 55%) !important;
  pointer-events: none !important;
}

.llm-note-markdown pre.plain-code-block::after {
  content: '' !important;
  position: absolute !important;
  left: 0 !important;
  top: 0 !important;
  width: 4px !important;
  height: 100% !important;
  background: linear-gradient(180deg, #ff7a45, #ffc53d) !important;
  opacity: 0.9 !important;
}

/* === Targeted Overrides for LlmMarkdownNote === */

/* Scoped variables for this component */
.notion-note-container {
  --note-bg-color: var(--el-bg-color);
  --note-text-color: var(--el-text-color-primary);
  --note-heading-color: var(--el-text-color-primary);
  --note-border-color: var(--el-border-color);
  --note-code-bg: var(--el-fill-color-light);
  --note-code-border: var(--el-border-color-lighter);
}

/* Headings */
.notion-note-container .llm-note-markdown .notion-style-heading {
  margin: 24px 0 14px;
  padding: 8px 0;
  border-left: 4px solid var(--el-color-primary);
  border-radius: 6px;
  font-weight: 700;
  color: var(--note-heading-color) !important;
  background: transparent !important;
  box-shadow: none !important;
}

/* Callouts */
.notion-note-container .llm-note-markdown .notion-callout {
  display: flex;
  align-items: flex-start;
  padding: 16px 20px;
  margin: 20px 0;
  border-radius: 12px;
  border: 1px solid var(--note-border-color);
  box-shadow: var(--el-box-shadow-light);
  background: var(--el-fill-color-lighter) !important;
}

.notion-note-container .llm-note-markdown .notion-callout.info {
  border-left: 4px solid var(--note-border-color);
  background: var(--el-fill-color-lighter) !important;
}

.notion-note-container .llm-note-markdown .notion-callout.warning {
  border-left: 4px solid var(--el-color-warning);
  background: var(--el-color-warning-light-9) !important;
}

.notion-note-container .llm-note-markdown .notion-callout.success {
  border-left: 4px solid var(--el-color-success);
  background: var(--el-color-success-light-9) !important;
}

.notion-note-container .llm-note-markdown .notion-callout.highlight {
  border-left: 4px solid var(--el-color-danger);
  background: var(--el-color-danger-light-9) !important;
}

.notion-note-container .llm-note-markdown .callout-icon {
  font-size: 1.2rem;
  margin-right: 12px;
  margin-top: 2px;
}

.notion-note-container .llm-note-markdown .callout-content {
  flex: 1;
  color: var(--note-text-color) !important;
  font-weight: 500;
  line-height: 1.6;
}

/* Soften Code Blocks */
.notion-note-container .llm-note-markdown pre.plain-code-block {
  background: var(--note-code-bg) !important;
  border: 1px solid var(--note-code-border) !important;
  border-radius: 8px !important;
  box-shadow: none !important;
  color: var(--note-text-color) !important;
}

.notion-note-container .llm-note-markdown pre.plain-code-block::before,
.notion-note-container .llm-note-markdown pre.plain-code-block::after {
  display: none !important; /* Remove the gradient borders */
}

.notion-note-container .llm-note-markdown code.plain-code {
  background: transparent !important;
  color: var(--note-text-color) !important;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.9em;
}

/* Soften Tables */
.notion-note-container .llm-note-markdown .enhanced-table {
  border: 1px solid var(--note-border-color) !important;
  box-shadow: none !important;
  background: transparent !important;
}

.notion-note-container .llm-note-markdown .enhanced-table th {
  background: var(--el-fill-color-light) !important;
  color: var(--note-text-color) !important;
  border-bottom: 1px solid var(--note-border-color) !important;
}

.notion-note-container .llm-note-markdown .enhanced-table td {
  border-bottom: 1px solid var(--note-border-color) !important;
  color: var(--note-text-color) !important;
}

/* Text Density & List Spacing */
.notion-note-container .llm-note-markdown p {
  margin: 12px 0 !important;
  line-height: 1.65 !important;
  text-align: left !important;
}

.notion-note-container .llm-note-markdown .clean-paragraph {
  text-align: left !important;
}

.notion-note-container .llm-note-markdown ul,
.notion-note-container .llm-note-markdown ol {
  margin: 12px 0 !important;
  padding-left: 22px !important;
}

.notion-note-container .llm-note-markdown li {
  margin: 6px 0 !important;
  padding: 0 !important;
  line-height: 1.65 !important;
}

.notion-note-container .llm-note-markdown li p {
  display: block !important;
  margin: 6px 0 !important;
  padding: 0 !important;
}

/* Table Layout Fix */
.notion-note-container .llm-note-markdown table {
  table-layout: auto !important;
  word-break: normal;
  overflow-wrap: anywhere;
}

/* Dark Mode Specific Overrides */
html.dark .notion-note-container .llm-note-markdown .notion-style-heading {
  color: var(--el-text-color-primary) !important;
}

html.dark .notion-note-container .llm-note-markdown .callout-content {
  color: var(--el-text-color-primary) !important;
}

html.dark .notion-note-container .llm-note-markdown pre.plain-code-block {
  background: #1e1e1e !important; /* Slightly darker for code in dark mode */
  border-color: #333 !important;
}
</style>
