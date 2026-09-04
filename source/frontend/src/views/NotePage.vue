<template>
  <div class="note-page">
    <!-- 警告條 -->
    <div v-if="validationWarnings.length > 0" class="warning-bar">
      <el-icon><Warning /></el-icon>
      <span>需要重跑或人工修訂：</span>
      <ul>
        <li v-for="warning in validationWarnings" :key="warning">{{ warning }}</li>
      </ul>
    </div>
    
    <!-- 主要內容區域 -->
    <div class="content">
      <!-- 筆記標題 -->
      <header class="note-header">
        <h1 class="note-title">
          {{ noteData.meta.title }}
          <a :href="`#${noteData.meta.title}`" class="anchor">#</a>
        </h1>
        <div class="note-meta">
          <span class="meta-item">📅 {{ formatDate(noteData.meta.analyzed_at) }}</span>
          <span class="meta-item">🌐 {{ noteData.meta.lang }}</span>
          <span class="meta-item">📚 {{ noteData.meta.source.length }} 個來源</span>
        </div>
      </header>
      
      <!-- 內容區塊 -->
      <main class="note-content">
        <!-- Legacy structured rendering disabled for image notes; fallback renderer handles ②–⑥ layout -->
        <section class="content-section">
          <div class="card">
            <p class="muted">這個頁面使用 fallbackHtml 渲染，已停用舊版區塊樣板（考點速覽 / 概念講解 / 範例程式等）。</p>
          </div>
        </section>
      </main>
      </div>
      
    <!-- 右側工具欄 -->
    <RightSidebar
      :toc="noteData.toc"
      :active-section="activeSection"
      @export="handleExport"
      @lang-change="handleLangChange"
      @view-change="handleViewChange"
      @collapse-all="handleCollapseAll"
      @expand-all="handleExpandAll"
      @search="handleSearch"
      @scroll-to-section="handleScrollToSection"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Warning } from '@element-plus/icons-vue'
import SuperCodeBlock from '../components/SuperCodeBlock.vue'
import SmartTextBlock from '../components/SmartTextBlock.vue'
import NoteSectionRenderer from '../components/NoteSectionRenderer.vue'
import RightSidebar from '../components/RightSidebar.vue'
// 主題樣式已由 main.js 統一導入

const props = defineProps({
  noteData: {
    type: Object,
    required: true
  }
})

// 響應式狀態
const activeSection = ref('')
const showLang = ref({ jp: true, tw: true })
const validationWarnings = ref([])

// 格式化日期
const formatDate = (dateString) => {
  return new Date(dateString).toLocaleDateString('zh-TW', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 獲取章節證據
const getSectionEvidence = (sectionId) => {
  const section = props.noteData.sections.find(s => s.id === sectionId)
  if (section && section.evidence) {
    return section.evidence
  }
  return []
}

// 驗證筆記數據
const validateNoteData = () => {
  const warnings = []
  
  // 檢查必含關鍵詞
  if (props.noteData.checks && props.noteData.checks.must_include) {
    const content = JSON.stringify(props.noteData)
    props.noteData.checks.must_include.forEach(keyword => {
      if (!content.includes(keyword)) {
        warnings.push(`缺少必含關鍵詞：${keyword}`)
      }
    })
  }
  
  // 檢查證據覆蓋率
  let totalItems = 0
  let itemsWithEvidence = 0
  
  props.noteData.sections.forEach(section => {
    if (section.items) {
      section.items.forEach(item => {
        totalItems++
        if (item.evidence && item.evidence.length > 0) {
          itemsWithEvidence++
        }
      })
    }
  })
  
  const coverageRate = totalItems > 0 ? (itemsWithEvidence / totalItems) * 100 : 0
  if (coverageRate < 80) {
    warnings.push(`證據覆蓋率不足：${coverageRate.toFixed(1)}% (要求 >= 80%)`)
  }
  
  validationWarnings.value = warnings
}

// 事件處理
const handleExport = (format) => {
  try {
    if (format === 'md') {
      const md = buildMarkdownFromNote(props.noteData)
      downloadBlob(md, 'text/markdown', `${safeTitle(props.noteData.meta.title)}.md`)
      return
    }
    if (format === 'html') {
      const html = buildHtmlFromNote(props.noteData)
      downloadBlob(html, 'text/html', `${safeTitle(props.noteData.meta.title)}.html`)
      return
    }
    if (format === 'pdf') {
      // 使用瀏覽器列印為 PDF：先切換列印樣式，再呼叫 print
      // 避免第三方依賴，保留一致性
      window.print()
      return
    }
  } catch (e) {
    console.error('導出失敗:', e)
  }
}

const handleLangChange = (lang) => {
  if (lang === 'jp') {
    showLang.value = { jp: true, tw: false }
  } else if (lang === 'tw') {
    showLang.value = { jp: false, tw: true }
  } else {
    showLang.value = { jp: true, tw: true }
  }
}

const handleViewChange = (mode) => {
  // 實現視圖模式切換
}

const handleCollapseAll = () => {
  // 實現折疊邏輯
}

const handleExpandAll = () => {
  // 實現展開邏輯
}

const handleSearch = (query) => {
  // 實現搜尋邏輯
}

const handleScrollToSection = (sectionId) => {
  const element = document.getElementById(sectionId)
  if (element) {
    element.scrollIntoView({ behavior: 'smooth' })
    activeSection.value = sectionId
  }
}

// ===== 導出工具 =====
function safeTitle(title) {
  if (!title) return 'note'
  return String(title).replace(/[\\/:*?"<>|\n\r\t]/g, '_').slice(0, 80)
}

function downloadBlob(content, mime, filename) {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

function buildMarkdownFromNote(note) {
  // 以 noteData 生成完整 Markdown
  const parts = []
  const title = note?.meta?.title || 'Untitled'
  parts.push(`# ${title}`)
  const meta = []
  if (note?.meta?.analyzed_at) meta.push(`- Date: ${new Date(note.meta.analyzed_at).toLocaleString()}`)
  if (note?.meta?.lang) meta.push(`- Lang: ${note.meta.lang}`)
  if (Array.isArray(note?.meta?.source)) meta.push(`- Sources: ${note.meta.source.length}`)
  if (meta.length) parts.push(meta.join('\n'))

  if (Array.isArray(note?.sections)) {
    for (const section of note.sections) {
      if (!section) continue
      const sectionTitle = section.title || section.id || ''
      if (sectionTitle) parts.push(`\n## ${sectionTitle}`)

      // bullets
      if (section.type === 'bullets' && Array.isArray(section.items)) {
        for (const item of section.items) {
          const jp = item?.jp ? `JP: ${item.jp}` : ''
          const tw = item?.tw ? `TW: ${item.tw}` : ''
          const lines = [jp, tw].filter(Boolean)
          if (lines.length) parts.push(`- ${lines.join(' | ')}`)
          if (item?.evidence?.length) parts.push(`  - Evidence: ${item.evidence.join(', ')}`)
        }
      }

      // paragraphs
      if (section.type === 'paragraphs' && Array.isArray(section.blocks)) {
        for (const block of section.blocks) {
          const text = block?.jp && block?.tw ? `${block.jp}\n\n${block.tw}` : (block?.tw || block?.jp || '')
          if (text) parts.push(text)
          if (block?.evidence?.length) parts.push(`> Evidence: ${block.evidence.join(', ')}`)
        }
      }

      // code-list
      if (section.type === 'code-list' && Array.isArray(section.items)) {
        for (const item of section.items) {
          if (item?.title) parts.push(`\n### ${item.title}`)
          if (item?.code) {
            const lang = section.language || 'text'
            parts.push('```' + lang)
            parts.push(item.code)
            parts.push('```')
          }
          const explain = item?.explain_tw || item?.explain_jp
          if (explain) parts.push(explain)
          if (item?.test?.[0]?.out) {
            parts.push('Expected Output:')
            parts.push('```')
            parts.push(String(item.test[0].out))
            parts.push('```')
          }
        }
      }

      // table / qa / problems 交給渲染器時通常有結構，導出以簡表表示
      if ((section.type === 'table' || section.type === 'qa' || section.type === 'problems') && Array.isArray(section.items)) {
        for (const item of section.items) {
          const left = item?.left || item?.q || ''
          const right = item?.right || item?.a || ''
          if (left || right) parts.push(`- ${left} -> ${right}`)
          if (item?.evidence?.length) parts.push(`  - Evidence: ${item.evidence.join(', ')}`)
        }
      }
    }
  }
  return parts.join('\n') + '\n'
}

function buildHtmlFromNote(note) {
  const md = buildMarkdownFromNote(note)
  const escaped = md
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  const theme = document.documentElement.getAttribute('data-theme') || 'light'
  // Inline CSS variables to make export self-contained
  const cssVars = theme === 'dark'
    ? `:root{--bg:#0f1216;--fg:#e9eef5}`
    : `:root{--bg:#ffffff;--fg:#121417}`
  return `<!doctype html><html data-theme="${theme}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"/><title>${safeTitle(note?.meta?.title || 'note')}</title>
  <style>
    ${cssVars}
    body{font-family: system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Cantarell,Noto Sans,sans-serif;line-height:1.6;margin:24px;background:var(--bg);color:var(--fg)}
    pre{background:${theme==='dark'?'#0f172a':'#f1f5f9'};color:${theme==='dark'?'#e5e7eb':'#0f172a'};padding:12px;border-radius:8px;overflow:auto}
    code{font-family: ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace}
    h1,h2,h3{color:var(--fg)}
  </style>
  </head><body><pre>${escaped}\n</pre></body></html>`
}

// 滾動監聽
const handleScroll = () => {
  const sections = props.noteData.toc.map(item => item.id)
  const scrollTop = window.pageYOffset
  
  for (let i = sections.length - 1; i >= 0; i--) {
    const element = document.getElementById(sections[i])
    if (element && element.offsetTop <= scrollTop + 100) {
      activeSection.value = sections[i]
      break
    }
  }
}

// 生命週期
onMounted(() => {
  validateNoteData()
  window.addEventListener('scroll', handleScroll)
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll)
})
</script>

<style scoped>
.note-page {
  min-height: 100vh;
  background: var(--bg);
  color: var(--fg);
}

.warning-bar {
  background: #fff3cd;
  border: 1px solid #ffeaa7;
  color: #856404;
  padding: var(--space-3);
  margin: var(--space-3);
  border-radius: 8px;
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
}

.warning-bar ul {
  margin: 0;
  padding-left: var(--space-4);
}

.content {
  max-width: 860px;
  margin: 0 auto;
  padding: var(--space-4);
}

.note-header {
  text-align: center;
  margin-bottom: var(--space-5);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--border);
}

.note-title {
  font-size: 32px;
  font-weight: 700;
  margin: 0 0 var(--space-3) 0;
  color: var(--fg);
}

.note-meta {
  display: flex;
  justify-content: center;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.meta-item {
  color: var(--muted);
  font-size: 14px;
}

.content-section {
  margin: var(--space-5) 0;
}

.keypoints-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.keypoint-item {
  margin: var(--space-3) 0;
  padding: var(--space-3);
  background: var(--card);
  border-radius: 8px;
  border-left: 4px solid var(--primary);
}

.keypoint-content {
  margin-bottom: var(--space-2);
}

.keypoint-jp,
.keypoint-tw {
  margin: var(--space-1) 0;
  line-height: 1.6;
}

.concept-block {
  margin: var(--space-4) 0;
  padding: var(--space-3);
  background: var(--card);
  border-radius: 8px;
}

.concept-label {
  font-weight: 600;
  margin-bottom: var(--space-1);
  color: var(--muted);
  font-size: 14px;
}

.concept-content {
  line-height: 1.7;
  margin-bottom: var(--space-2);
}

.code-example {
  margin: var(--space-4) 0;
}

/* 移除了重複的樣式，現在統一由 NoteSectionRenderer 處理 */

.evidence {
  font-size: 12px;
  color: var(--muted);
  margin-top: var(--space-1);
  font-style: italic;
}

.anchor {
  opacity: 0;
  margin-left: var(--space-1);
  color: var(--muted);
  text-decoration: none;
  transition: opacity 0.2s;
}

h1:hover .anchor,
h2:hover .anchor,
h3:hover .anchor {
  opacity: 1;
}

/* 響應式設計 */
@media (max-width: 768px) {
  .content {
    padding: var(--space-3);
  }
  
  .note-title {
    font-size: 24px;
  }
  
  .note-meta {
    flex-direction: column;
    gap: var(--space-2);
  }
}

/* 列印樣式 */
@media print {
  .note-page {
    background: white;
    color: black;
  }
  
  .warning-bar {
    background: #fff3cd;
    color: #856404;
  }
  
  .card {
    box-shadow: none;
    border: 1px solid #ccc;
    break-inside: avoid;
  }
  
  .anchor {
    display: none;
  }
}
</style>
