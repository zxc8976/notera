<template>
  <div class="japanese-note-card">
    <!-- 場景圖片 -->
    <div v-if="sceneImage" class="scene-image-container">
      <img :src="sceneImage" :alt="`場景 ${sceneIndex} 截圖`" class="scene-image" />
      <div class="scene-badge">場景 {{ sceneIndex }}</div>
    </div>
    
    <!-- 筆記內容 -->
    <div class="note-content">
      <!-- 日文關鍵詞表格 -->
      <div v-if="japaneseKeywords.length" class="keywords-section">
        <h3 class="section-title">🎯 日文關鍵詞</h3>
        <div class="keywords-table">
          <div class="table-header">
            <div class="col-japanese">日文</div>
            <div class="col-reading">讀音</div>
            <div class="col-meaning">中文意思</div>
            <div class="col-importance">重要度</div>
          </div>
          <div v-for="(keyword, idx) in japaneseKeywords" :key="idx" class="table-row">
            <div class="col-japanese">
              <span class="japanese-text">{{ keyword.japanese }}</span>
            </div>
            <div class="col-reading">
              <span class="reading-text">{{ keyword.reading }}</span>
            </div>
            <div class="col-meaning">{{ keyword.meaning }}</div>
            <div class="col-importance">
              <span class="importance-stars">{{ getImportanceStars(keyword.importance) }}</span>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 重點說明 -->
      <div v-if="keyPoints.length" class="key-points-section">
        <h3 class="section-title">📝 重點說明</h3>
        <div class="key-points-list">
          <div v-for="(point, idx) in keyPoints" :key="idx" class="key-point-item">
            <div v-if="point.japanese" class="japanese-original">
              <span class="label">日文原文：</span>
              <span class="japanese-text">{{ point.japanese }}</span>
            </div>
            <div v-if="point.chinese" class="chinese-explanation">
              <span class="label">中文解釋：</span>
              <span class="explanation-text">{{ point.chinese }}</span>
            </div>
            <div v-if="point.examPoint" class="exam-point">
              <span class="exam-badge">🔥 考試重點</span>
              <span class="exam-text">{{ point.examPoint }}</span>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 理解要點 -->
      <div v-if="understandingPoints.length" class="understanding-section">
        <h3 class="section-title">💡 理解要點</h3>
        <ul class="understanding-list">
          <li v-for="(point, idx) in understandingPoints" :key="idx" class="understanding-item">
            {{ point }}
          </li>
        </ul>
      </div>
      
      <!-- 程式碼區塊 -->
      <div v-if="codeBlocks.length" class="code-section">
        <h3 class="section-title">💻 程式碼</h3>
        <div v-for="(code, idx) in codeBlocks" :key="idx" class="code-block-container">
          <div class="code-header">
            <span class="language-tag">{{ code.language || 'Code' }}</span>
            <button class="copy-btn" @click="copyCode(code.content)">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2" stroke="currentColor" stroke-width="2" fill="none"/>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" stroke="currentColor" stroke-width="2" fill="none"/>
              </svg>
              {{ t('copy') }}
            </button>
          </div>
          <pre class="code-content"><code>{{ code.content }}</code></pre>
        </div>
      </div>
      
      <!-- 補充資料 -->
      <div v-if="supplementaryData.length" class="supplementary-section">
        <h3 class="section-title">📚 補充資料</h3>
        <div class="supplementary-list">
          <div v-for="(item, idx) in supplementaryData" :key="idx" class="supplementary-item">
            <div class="supplementary-label">{{ item.label }}</div>
            <div class="supplementary-content">{{ item.content }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useLanguage } from '../composables/useLanguage.js'

// 翻譯函數
const { t } = useLanguage()

const props = defineProps({
  sceneIndex: {
    type: Number,
    required: true
  },
  sceneImage: {
    type: String,
    default: ''
  },
  noteContent: {
    type: String,
    required: true
  }
})

// 解析筆記內容
const parsedContent = computed(() => {
  return parseNoteContent(props.noteContent)
})

const japaneseKeywords = computed(() => parsedContent.value.keywords)
const keyPoints = computed(() => parsedContent.value.keyPoints)
const understandingPoints = computed(() => parsedContent.value.understanding)
const codeBlocks = computed(() => parsedContent.value.codeBlocks)
const supplementaryData = computed(() => parsedContent.value.supplementary)

function parseNoteContent(content) {
  const result = {
    keywords: [],
    keyPoints: [],
    understanding: [],
    codeBlocks: [],
    supplementary: []
  }
  
  // 解析日文關鍵詞表格 - 改進的正則表達式
  const keywordTableRegex = /\|[^|]*日文[^|]*\|[^|]*讀音[^|]*\|[^|]*中文意思[^|]*\|[^|]*重要度[^|]*\|([\s\S]*?)(?=\n\n|\n###|\n##|\n\|(?![^|]*日文)|$)/
  const keywordMatch = content.match(keywordTableRegex)
  if (keywordMatch) {
    const tableContent = keywordMatch[1]
    const rows = tableContent.split('\n').filter(row => row.trim() && !row.includes('---') && row.includes('|'))
    rows.forEach(row => {
      const cols = row.split('|').map(col => col.trim()).filter(col => col)
      if (cols.length >= 4) {
        result.keywords.push({
          japanese: cols[0].replace(/\*\*/g, '').trim(),
          reading: cols[1].trim(),
          meaning: cols[2].trim(),
          importance: cols[3].trim()
        })
      }
    })
  }
  
  // 備用解析：如果沒有找到表格，嘗試解析其他格式的關鍵詞
  if (result.keywords.length === 0) {
    // 解析 **日文詞彙** (讀音) - 中文意思 格式
    const altKeywordRegex = /\*\*([^*]+)\*\*\s*\(([^)]+)\)\s*[-–—]\s*([^\n]+)/g
    let altMatch
    while ((altMatch = altKeywordRegex.exec(content)) !== null) {
      result.keywords.push({
        japanese: altMatch[1].trim(),
        reading: altMatch[2].trim(),
        meaning: altMatch[3].trim(),
        importance: '⭐⭐⭐' // 預設重要度
      })
    }
  }
  
  // 解析重點說明 - 改進的解析邏輯
  const keyPointsPatterns = [
    /### 📝 重點說明([\s\S]*?)(?=\n###|\n##|$)/,
    /## 重點說明([\s\S]*?)(?=\n###|\n##|$)/,
    /### 重點([\s\S]*?)(?=\n###|\n##|$)/,
    /## 📋 場景重點([\s\S]*?)(?=\n###|\n##|$)/
  ]
  
  let keyPointsContent = null
  for (const pattern of keyPointsPatterns) {
    const match = content.match(pattern)
    if (match) {
      keyPointsContent = match[1]
      break
    }
  }
  
  if (keyPointsContent) {
    // 方法1: 解析結構化的重點說明
    const structuredPoints = []
    const japaneseRegex = /\*\*日文原文\*\*:\s*([^\n]*)/g
    const chineseRegex = /\*\*中文解釋\*\*:\s*([^\n]*)/g
    const examRegex = /\*\*考試重點\*\*:\s*([^\n]*)/g
    
    let japaneseMatch, chineseMatch, examMatch
    const japaneseTexts = []
    const chineseTexts = []
    const examTexts = []
    
    while ((japaneseMatch = japaneseRegex.exec(keyPointsContent)) !== null) {
      japaneseTexts.push(japaneseMatch[1].trim())
    }
    
    while ((chineseMatch = chineseRegex.exec(keyPointsContent)) !== null) {
      chineseTexts.push(chineseMatch[1].trim())
    }
    
    while ((examMatch = examRegex.exec(keyPointsContent)) !== null) {
      examTexts.push(examMatch[1].trim())
    }
    
    // 組合結構化重點
    const maxLength = Math.max(japaneseTexts.length, chineseTexts.length, examTexts.length)
    for (let i = 0; i < maxLength; i++) {
      const point = {}
      if (japaneseTexts[i]) point.japanese = japaneseTexts[i]
      if (chineseTexts[i]) point.chinese = chineseTexts[i]
      if (examTexts[i]) point.examPoint = examTexts[i]
      if (Object.keys(point).length > 0) {
        structuredPoints.push(point)
      }
    }
    
    // 方法2: 如果沒有結構化內容，解析列表項目
    if (structuredPoints.length === 0) {
      const listItems = keyPointsContent.split('\n').filter(line => {
        const trimmed = line.trim()
        return trimmed.startsWith('-') || trimmed.startsWith('*') || trimmed.startsWith('•')
      })
      
      listItems.forEach(item => {
        const cleanItem = item.replace(/^[-*•]\s*/, '').trim()
        if (cleanItem.length > 10) { // 過濾太短的項目
          // 嘗試分離日文和中文
          const japaneseMatch = cleanItem.match(/([ひらがなカタカナ漢字]+.*?)[-–—]\s*(.+)/)
          if (japaneseMatch) {
            structuredPoints.push({
              japanese: japaneseMatch[1].trim(),
              chinese: japaneseMatch[2].trim()
            })
          } else {
            structuredPoints.push({
              chinese: cleanItem
            })
          }
        }
      })
    }
    
    result.keyPoints = structuredPoints
  }
  
  // 解析理解要點 - 改進的解析邏輯
  const understandingPatterns = [
    /### 💡 理解要點([\s\S]*?)(?=\n###|\n##|$)/,
    /## 理解要點([\s\S]*?)(?=\n###|\n##|$)/,
    /### 💡 重要概念([\s\S]*?)(?=\n###|\n##|$)/,
    /## 💡 重要概念([\s\S]*?)(?=\n###|\n##|$)/,
    /### 學習重點([\s\S]*?)(?=\n###|\n##|$)/
  ]
  
  let understandingContent = null
  for (const pattern of understandingPatterns) {
    const match = content.match(pattern)
    if (match) {
      understandingContent = match[1]
      break
    }
  }
  
  if (understandingContent) {
    const points = understandingContent.split('\n').filter(line => {
      const trimmed = line.trim()
      return trimmed.startsWith('-') || trimmed.startsWith('*') || trimmed.startsWith('•') || 
             trimmed.match(/^\d+\./) // 支援數字列表
    })
    result.understanding = points.map(point => {
      return point.replace(/^[-*•]\s*/, '').replace(/^\d+\.\s*/, '').trim()
    }).filter(point => point.length > 5) // 過濾太短的項目
  }
  
  // 解析程式碼區塊 - 改進的解析邏輯
  const codeRegex = /```(\w+)?\n?([\s\S]*?)```/g
  let codeMatch
  while ((codeMatch = codeRegex.exec(content)) !== null) {
    const language = codeMatch[1] || 'text'
    const codeContent = codeMatch[2].trim()
    if (codeContent.length > 0) {
      result.codeBlocks.push({
        language: language,
        content: codeContent
      })
    }
  }
  
  // 解析補充資料 - 改進的解析邏輯
  const supplementaryPatterns = [
    /### 📚 補充資料([\s\S]*?)(?=\n###|\n##|$)/,
    /## 補充資料([\s\S]*?)(?=\n###|\n##|$)/,
    /### 📚 延伸閱讀([\s\S]*?)(?=\n###|\n##|$)/,
    /## 📚 延伸閱讀([\s\S]*?)(?=\n###|\n##|$)/,
    /### 參考資料([\s\S]*?)(?=\n###|\n##|$)/
  ]
  
  let supplementaryContent = null
  for (const pattern of supplementaryPatterns) {
    const match = content.match(pattern)
    if (match) {
      supplementaryContent = match[1]
      break
    }
  }
  
  if (supplementaryContent) {
    const items = supplementaryContent.split('\n').filter(line => {
      const trimmed = line.trim()
      return trimmed.startsWith('-') || trimmed.startsWith('*') || trimmed.startsWith('•') ||
             trimmed.match(/^\d+\./) // 支援數字列表
    })
    
    result.supplementary = items.map(item => {
      const cleanItem = item.replace(/^[-*•]\s*/, '').replace(/^\d+\.\s*/, '').trim()
      
      // 嘗試分離標籤和內容
      const colonIndex = cleanItem.indexOf('：')
      const colonIndexEn = cleanItem.indexOf(':')
      const separatorIndex = colonIndex > 0 ? colonIndex : (colonIndexEn > 0 ? colonIndexEn : -1)
      
      if (separatorIndex > 0 && separatorIndex < cleanItem.length - 1) {
        return {
          label: cleanItem.substring(0, separatorIndex).trim(),
          content: cleanItem.substring(separatorIndex + 1).trim()
        }
      }
      
      // 如果沒有分隔符，整個作為內容
      return { 
        label: '說明', 
        content: cleanItem 
      }
    }).filter(item => item.content.length > 0) // 過濾空內容
  }
  
  return result
}

function getImportanceStars(importance) {
  const starCount = (importance.match(/⭐/g) || []).length
  return '⭐'.repeat(Math.max(1, starCount))
}

function copyCode(code) {
  navigator.clipboard.writeText(code).then(() => {
    ElMessage.success(t('codeCopied'))
  }).catch(() => {
    ElMessage.error(t('copyFailed'))
  })
}
</script>

<style scoped>
.japanese-note-card {
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  overflow: hidden;
  margin-bottom: 24px;
  transition: all 0.3s ease;
}

.japanese-note-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
}

.scene-image-container {
  position: relative;
  width: 100%;
  height: 200px;
  overflow: hidden;
}

.scene-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease;
}

.scene-image:hover {
  transform: scale(1.05);
}

.scene-badge {
  position: absolute;
  top: 12px;
  right: 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

.note-content {
  padding: 24px;
}

.section-title {
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 16px 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 關鍵詞表格樣式 */
.keywords-section {
  margin-bottom: 24px;
}

.keywords-table {
  background: #f8fafc;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
}

.table-header {
  display: grid;
  grid-template-columns: 2fr 1.5fr 2fr 1fr;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-weight: 600;
  font-size: 14px;
}

.table-header > div {
  padding: 12px 16px;
  text-align: center;
}

.table-row {
  display: grid;
  grid-template-columns: 2fr 1.5fr 2fr 1fr;
  border-bottom: 1px solid #e2e8f0;
  transition: background-color 0.2s ease;
}

.table-row:hover {
  background: #f1f5f9;
}

.table-row:last-child {
  border-bottom: none;
}

.table-row > div {
  padding: 12px 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.japanese-text {
  font-size: 16px;
  font-weight: 700;
  color: #dc2626;
  font-family: 'Noto Sans JP', sans-serif;
}

.reading-text {
  font-size: 14px;
  color: #059669;
  font-family: 'Noto Sans JP', sans-serif;
}

.importance-stars {
  font-size: 16px;
}

/* 重點說明樣式 */
.key-points-section {
  margin-bottom: 24px;
}

.key-points-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.key-point-item {
  background: #f8fafc;
  border-radius: 12px;
  padding: 16px;
  border-left: 4px solid #3b82f6;
}

.japanese-original {
  margin-bottom: 8px;
}

.chinese-explanation {
  margin-bottom: 8px;
}

.exam-point {
  display: flex;
  align-items: center;
  gap: 8px;
}

.label {
  font-weight: 600;
  color: #374151;
}

.explanation-text {
  color: #1f2937;
  line-height: 1.6;
}

.exam-badge {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  color: white;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
}

.exam-text {
  color: #dc2626;
  font-weight: 600;
}

/* 理解要點樣式 */
.understanding-section {
  margin-bottom: 24px;
}

.understanding-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.understanding-item {
  background: #ecfdf5;
  border-left: 4px solid #10b981;
  padding: 12px 16px;
  margin-bottom: 8px;
  border-radius: 0 8px 8px 0;
  color: #065f46;
  line-height: 1.6;
}

/* 程式碼區塊樣式 */
.code-section {
  margin-bottom: 24px;
}

.code-block-container {
  background: #1e293b;
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 16px;
}

.code-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #334155;
  border-bottom: 1px solid #475569;
}

.language-tag {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
}

.copy-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  color: white;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s ease;
}

.copy-btn:hover {
  background: rgba(255, 255, 255, 0.2);
  transform: translateY(-1px);
}

.code-content {
  padding: 16px;
  margin: 0;
  background: #1e293b;
  color: #e2e8f0;
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 14px;
  line-height: 1.6;
  overflow-x: auto;
}

/* 補充資料樣式 */
.supplementary-section {
  margin-bottom: 24px;
}

.supplementary-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.supplementary-item {
  background: #fef3c7;
  border-left: 4px solid #f59e0b;
  padding: 12px 16px;
  border-radius: 0 8px 8px 0;
}

.supplementary-label {
  font-weight: 600;
  color: #92400e;
  margin-bottom: 4px;
}

.supplementary-content {
  color: #78350f;
  line-height: 1.6;
}

/* 深色模式 */
@media (prefers-color-scheme: dark) {
  .japanese-note-card {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #334155;
  }
  
  .section-title {
    color: #f1f5f9;
  }
  
  .keywords-table {
    background: #334155;
    border: 1px solid #475569;
  }
  
  .table-row:hover {
    background: #475569;
  }
  
  .key-point-item {
    background: #334155;
    border-left-color: #60a5fa;
  }
  
  .label {
    color: #e2e8f0;
  }
  
  .explanation-text {
    color: #cbd5e1;
  }
  
  .understanding-item {
    background: #064e3b;
    border-left-color: #34d399;
    color: #a7f3d0;
  }
  
  .supplementary-item {
    background: #451a03;
    border-left-color: #fbbf24;
  }
  
  .supplementary-label {
    color: #fcd34d;
  }
  
  .supplementary-content {
    color: #fde68a;
  }
}
</style>