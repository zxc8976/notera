<template>
  <DefaultLayout>
    <el-tabs v-model="activeTab">
      <el-tab-pane :label="t('formalNotes')" name="notes">
        <el-card class="notes-header">
          <template #header>
            <div class="card-header">
              <span>{{ t('noteManagement') }}</span>
            </div>
          </template>
          <el-row :gutter="20">
            <el-col :span="8">
              <el-select v-model="selectedCategory" :placeholder="t('selectCategory')" @change="loadNotes">
                <el-option :label="t('all')" value="" />
                <el-option v-for="cat in categories" :key="cat" :label="cat" :value="cat" />
              </el-select>
            </el-col>
            <el-col :span="8">
              <el-input v-model="search" :placeholder="t('searchTitleContent')" clearable @input="filterNotes" />
            </el-col>
            <el-col :span="8" style="text-align:right">
              <el-button @click="loadNotes">刷新</el-button>
              <el-button type="primary" @click="openBiliNoteDialog">BiliNote 檢視</el-button>
              <el-button type="danger" :disabled="selectedNotes.length===0" @click="batchDeleteNotes">
                批次刪除 ({{ selectedNotes.length }})
              </el-button>
            </el-col>
          </el-row>
        </el-card>
        <el-table :data="filteredNotes" style="width: 100%; margin-top: 20px;" @selection-change="onSelectionChange" row-class-name="dark-row">
          <el-table-column type="selection" width="48" />
          <el-table-column prop="title" :label="t('title')" />
          <el-table-column prop="category" :label="t('category')" />
          <el-table-column prop="created_at" :label="t('createdTime')" />
          <el-table-column :label="t('actions')">
            <template #default="scope">
              <el-button size="small" @click="previewNote(scope.row)">{{ t('preview') }}</el-button>
              <el-button size="small" @click="downloadNote(scope.row)">{{ t('download') }}</el-button>
              <el-button size="small" type="danger" @click="deleteNote(scope.row)">{{ t('delete') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-card v-if="summaryResult" class="note-markdown" style="margin-top:32px;">
          <div class="zero-hallucination-notice">
            <h3>⚠️ 零幻覺模式</h3>
            <p>此內容已過濾，只顯示有來源標記的內容。要檢視完整筆記，請使用「BiliNote 檢視」功能。</p>
            <div class="action-buttons">
              <el-button type="primary" @click="openBiliNoteDialog">前往 BiliNote 檢視</el-button>
            </div>
          </div>
          <div style="text-align:right;margin-top:18px;">
            <el-button type="success" @click="openSaveDialog">{{ t('saveNote') }}</el-button>
          </div>
        </el-card>
        <el-dialog v-model="showSaveDialog" :title="t('saveNote')" width="400px">
          <el-form :model="saveForm">
            <el-form-item :label="t('category')">
              <el-select v-model="saveForm.category" :placeholder="t('selectCategory')">
                <el-option v-for="cat in categories" :key="cat" :label="cat" :value="cat" />
              </el-select>
            </el-form-item>
            <el-form-item :label="t('title')">
              <el-input v-model="saveForm.title" :placeholder="t('enterTitle')" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="showSaveDialog=false">{{ t('cancel') }}</el-button>
            <el-button type="primary" @click="saveSummary">{{ t('confirm') }}</el-button>
          </template>
        </el-dialog>
        <el-dialog v-model="showPreview" :title="t('notePreview')" width="85%">
          <el-scrollbar height="70vh">
            <LlmMarkdownNote :markdown="previewContent" />
          </el-scrollbar>
          <template #footer>
            <el-button @click="showPreview = false">{{ t('close') }}</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>
      <el-tab-pane :label="t('tempData')" name="tmp">
        <el-card class="notes-header">
          <template #header>
            <div class="card-header">
              <span>{{ t('tempDataManagement') }}</span>
            </div>
          </template>
          <el-table :data="tmpList" style="width: 100%; margin-top: 20px;">
            <el-table-column prop="path" :label="t('file')" />
            <el-table-column prop="scene_count" :label="t('sceneCount')" />
            <el-table-column prop="created" :label="t('createdTime')" :formatter="formatTime" />
            <el-table-column prop="has_scenes" :label="t('hasAnalysis')" :formatter="v => v ? '✔' : ''" />
            <el-table-column :label="t('actions')">
              <template #default="scope">
                <el-button size="small" @click="previewTmp(scope.row)">{{ t('preview') }}</el-button>
                <el-button size="small" type="success" @click="saveTmp(scope.row)">{{ t('saveNote') }}</el-button>
                <el-button size="small" type="danger" @click="deleteTmp(scope.row)">{{ t('delete') }}</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
        <el-dialog v-model="showTmpPreview" :title="t('tempPreview')" width="85%">
          <el-scrollbar height="70vh">
            <div v-if="tmpImages.length">
              <el-image v-for="img in tmpImages" :key="img" :src="img" style="max-width:200px; margin:8px;" />
            </div>
            <LlmMarkdownNote v-if="tmpJson" :markdown="tmpJson" />
          </el-scrollbar>
          <template #footer>
            <el-button @click="showTmpPreview = false">{{ t('close') }}</el-button>
          </template>
        </el-dialog>
        <el-dialog v-model="showBiliNoteDialog" title="BiliNote 檢視" width="400px">
          <el-form>
            <el-form-item label="Doc ID">
              <el-input v-model="biliNoteId" placeholder="輸入 doc_id" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="showBiliNoteDialog = false">取消</el-button>
            <el-button type="primary" @click="goToBiliNote">前往檢視</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>
    </el-tabs>
  </DefaultLayout>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import axios from 'axios'
import { marked } from 'marked'
import { ElMessageBox, ElMessage } from 'element-plus' // 新增 Element Plus 彈窗
import DefaultLayout from '../layouts/DefaultLayout.vue'
import LlmMarkdownNote from '../components/LlmMarkdownNote.vue'
import { useLanguage } from '../composables/useLanguage.js'

// 使用語言系統
const { currentLanguage, t, switchLanguage } = useLanguage()

// 深色模式由DefaultLayout管理，這裡不需要單獨處理

const notes = ref([])
const filteredNotes = ref([])
const selectedNotes = ref([])
const categories = ref([])
const selectedCategory = ref('')
const search = ref('')
const showPreview = ref(false)
const showSaveDialog = ref(false)
const previewContent = ref('')
const activeTab = ref('notes')
const tmpList = ref([])
const showTmpPreview = ref(false)
const tmpImages = ref([])
const tmpJson = ref('')
const summaryResult = ref(localStorage.getItem('summaryResult') || '')
const showBiliNoteDialog = ref(false)
const biliNoteId = ref('')
const saveForm = ref({
  category: '',
  title: ''
})

onMounted(async () => {
  await loadCategories()
  await loadNotes()
  await loadTmpList()
})

async function loadCategories() {
  const res = await axios.get('/api/notes/categories')
  categories.value = res.data.categories || []
}

async function loadNotes() {
  try {
    const params = selectedCategory.value ? { category: selectedCategory.value } : {}
    const res = await axios.get('/api/notes/list', { params })
    
    // 處理筆記數據，確保每個筆記都有必要的屬性
    notes.value = (res.data.notes || []).map(notePath => {
      const fileName = notePath.split('/').pop()
      const category = notePath.split('/').slice(0, -1).join('/')
      const title = fileName.replace('.md', '').replace(/^\d{8}_\d{6}_/, '')
      
      return {
        path: notePath,
        title: title || fileName,
        category: category || '未分類',
        created_at: new Date().toISOString(), // 暫時使用當前時間
        raw_markdown: '' // 將在預覽時載入
      }
    })
    
    filterNotes()
  } catch (error) {
    console.error('載入筆記失敗:', error)
    ElMessage.error('載入筆記失敗')
    notes.value = []
  }
}

function filterNotes() {
  const q = search.value.trim().toLowerCase()
  filteredNotes.value = notes.value.filter(n =>
    (!q || n.title.toLowerCase().includes(q) || (n.raw_markdown && n.raw_markdown.toLowerCase().includes(q)))
  )
}

function onSelectionChange(selection) {
  selectedNotes.value = selection
}

async function batchDeleteNotes() {
  try {
    if (!selectedNotes.value.length) return
    await ElMessageBox.confirm(`確定要刪除已選擇的 ${selectedNotes.value.length} 筆筆記嗎？此操作無法復原。`, '批次刪除筆記', {
      confirmButtonText: '確定刪除',
      cancelButtonText: t('cancel'),
      type: 'warning'
    })

    // 逐一呼叫後端刪除現有端點
    for (const row of selectedNotes.value) {
      try {
        await axios.delete(`/api/notes/delete/${encodeURIComponent(row.path)}`)
      } catch (e) {
        console.error('刪除失敗', row.path, e)
      }
    }
    ElMessage.success('已完成批次刪除')
    selectedNotes.value = []
    await loadNotes()
  } catch (e) {
    ElMessage.info(t('deleteCancelled'))
  }
}

async function previewNote(note) {
  try {
    // 載入筆記內容
    const res = await axios.get(`/api/notes/content/${encodeURIComponent(note.path)}`)
    const content = res.data.content || '筆記內容載入失敗'
    previewContent.value = content
    showPreview.value = true
  } catch (error) {
    console.error('載入筆記內容失敗:', error)
    ElMessage.error('載入筆記內容失敗')
    previewContent.value = '無法載入筆記內容'
    showPreview.value = true
  }
}

function downloadNote(note) {
  const blob = new Blob([note.raw_markdown], { type: 'text/markdown' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${note.title || 'note'}.md`
  a.click()
  URL.revokeObjectURL(url)
}

function formatTime(row, col, val) {
  if (!val) return ''
  const d = new Date(val * 1000)
  return d.toLocaleString()
}

async function loadTmpList() {
  const res = await axios.get('/api/tmp/list')
  tmpList.value = res.data.tmp || []
}

async function previewTmp(row) {
  // 載入圖片
  tmpImages.value = []
  tmpJson.value = ''
  const imgRes = await axios.get(`/images/${row.filename}/`, { responseType: 'json' }).catch(()=>({data:[]}))
  if (imgRes.data && Array.isArray(imgRes.data)) {
    tmpImages.value = imgRes.data.map(f=>`/images/${row.filename}/${f}`)
  }
  // 載入 JSON
  const jsonRes = await axios.get(`/output/tmp/${row.filename}/scenes.json`).catch(()=>({data:''}))
  tmpJson.value = typeof jsonRes.data === 'string' ? jsonRes.data : JSON.stringify(jsonRes.data, null, 2)
  showTmpPreview.value = true
}

async function saveTmp(row) {
  // 這裡可彈窗選分類與標題，簡化先用預設
  const form = new FormData()
  form.append('category', '暫存')
  form.append('title', row.filename)
  form.append('content', '（請手動補上內容）')
  form.append('tmp_filename', row.filename)
  await axios.post('/api/notes/save', form)
  await loadTmpList()
  // 存檔後彈窗詢問是否刪除暫存
  ElMessageBox.confirm(
    '存檔成功！是否要刪除暫存資料？<br>（選擇保留可供下次測試，亦可隨時手動刪除）',
    '刪除暫存資料',
    {
      confirmButtonText: '刪除',
      cancelButtonText: '保留',
      dangerouslyUseHTMLString: true,
      type: 'warning',
    }
  ).then(async () => {
    // 選擇刪除
    await deleteTmp(row)
    ElMessage.success('暫存資料已刪除')
  }).catch(() => {
    // 選擇保留
    ElMessage.info('暫存資料已保留，可於暫存管理手動刪除')
  })
}

async function deleteTmp(row) {
  const form = new FormData()
  form.append('filename', row.filename)
  await axios.post('/api/tmp/delete', form)
  await loadTmpList()
}

async function deleteNote(note) {
  try {
    await ElMessageBox.confirm(
      `確定要刪除筆記「${note.title}」嗎？此操作無法復原。`,
      '刪除筆記',
      {
        confirmButtonText: '確定刪除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    // 調用刪除API
    await axios.delete(`/api/notes/delete/${encodeURIComponent(note.path)}`)
    ElMessage.success('筆記已刪除')
    await loadNotes() // 重新載入筆記列表
  } catch (error) {
    if (error !== 'cancel') {
      console.error('刪除筆記失敗:', error)
      ElMessage.error('刪除筆記失敗')
    }
  }
}

function openBiliNoteDialog() {
  // 先嘗試從 localStorage 帶入上一個 doc_id
  let lastId = ''
  try { lastId = localStorage.getItem('last_doc_id') || '' } catch(_) {}
  if (lastId && lastId.trim()) {
    window.location.href = `/bili/${lastId.trim()}`
    return
  }
  // 其次嘗試從筆記列表第一筆帶入 doc_id
  const recent = notes.value?.[0]
  const autoId = recent?.doc_id || recent?.id
  if (autoId && String(autoId).trim()) {
    window.location.href = `/bili/${String(autoId).trim()}`
    return
  }
  // 否則顯示輸入框
  showBiliNoteDialog.value = true
  biliNoteId.value = ''
}

function goToBiliNote() {
  if (!biliNoteId.value.trim()) {
    ElMessage.error('請輸入 doc_id')
    return
  }
  showBiliNoteDialog.value = false
  // 跳轉到新的 BiliNote 頁面
  window.location.href = `/bili/${biliNoteId.value.trim()}`
}

function openSaveDialog() {
  showSaveDialog.value = true
}

async function saveSummary() {
  if (!saveForm.value.category || !saveForm.value.title) {
    ElMessage.error('請填寫分類與標題')
    return
  }
  const form = new FormData()
  form.append('category', saveForm.value.category)
  form.append('title', saveForm.value.title)
  form.append('content', summaryResult.value)
  await axios.post('/api/notes/save', form)
  ElMessage.success('存檔成功！')
  showSaveDialog.value = false
  await loadNotes()
}

watch(activeTab, async (val) => {
  if (val === 'tmp') await loadTmpList()
})

// 當摘要完成時自動暫存
watch(summaryResult, (val) => {
  if (val) localStorage.setItem('summaryResult', val)
})
</script>

<style scoped>
.notes-container {
  padding: 32px 8vw 32px 8vw;
  background: var(--el-bg-color, #f6f8fa);
  min-height: 100vh;
}
.notes-header {
  margin-bottom: 24px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.card-header {
  font-size: 1.2em;
  font-weight: bold;
}
.note-markdown {
  font-family: 'Segoe UI', 'Noto Sans TC', 'Noto Sans JP', 'Helvetica Neue', Arial, 'Microsoft JhengHei', 'Meiryo', sans-serif;
  font-size: 18px;
  line-height: 1.9;
  color: #23272f;
  background: #fff;
  border-radius: 12px;
  padding: 32px 20px 32px 32px;
  margin: 32px auto 32px auto;
  max-width: 900px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.06);
  word-break: break-word;
}
.note-markdown h1, .note-markdown h2 {
  color: #2c3e50;
  font-weight: bold;
  background: #e3eefd;
  padding: 4px 12px;
  border-radius: 6px;
  margin-bottom: 0.5em;
}
.note-markdown h3 {
  color: #1976d2;
  font-weight: bold;
  background: #e3f2fd;
  padding: 2px 10px;
  border-radius: 5px;
  margin-bottom: 0.5em;
}
.note-markdown p,
.note-markdown ul > li,
.note-markdown li {
  color: #23272f !important;
  background: none !important;
  font-weight: 500;
  letter-spacing: 0.01em;
}
.note-markdown ul > li {
  background: #e3f2fd !important;
  border-left: 5px solid #1976d2;
  color: #2c3e50 !important;
  font-weight: 600;
  margin-bottom: 0.7em;
  padding: 0.3em 1em;
}
.note-markdown strong {
  color: #d32f2f !important;
  background: #fff0f0 !important;
  padding: 0 6px;
  border-radius: 4px;
  font-weight: 900;
  font-size: 1.08em;
  box-shadow: 0 1px 0 #fbb;
}
.note-markdown em {
  color: #1565c0 !important;
  background: #e3f2fd !important;
  padding: 0 6px;
  border-radius: 4px;
  font-style: normal;
  font-weight: 700;
  font-size: 1.05em;
  box-shadow: 0 1px 0 #b3e5fc;
}
.note-markdown table {
  background: #f8fafc;
  color: #23272f;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px #e3eefd;
}
.note-markdown th {
  background: #e3eefd;
  color: #2c3e50;
  font-weight: bold;
}
.note-markdown td {
  color: #374151;
  background: #f8fafc;
}
.note-markdown blockquote {
  background: #f3f4f6;
  border-left: 5px solid #90caf9;
  color: #374151;
  margin: 1em 0;
  padding: 0.7em 1.2em;
  border-radius: 8px;
  font-style: italic;
  font-size: 1.05em;
}
.note-markdown a {
  color: #1976d2;
  text-decoration: underline;
  background: #e3f2fd;
  border-radius: 2px;
  padding: 0 2px;
}
.note-markdown .error-message {
  background: #ffeaea;
  color: #d32f2f;
  border: 1px solid #ffcdd2;
}
.el-table {
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
/* 深夜模式樣式 */
.notes-container.dark-mode {
  background: #181c20;
  color: #e6e6e6;
}

.notes-container.dark-mode .note-markdown {
  background: #23272f;
  color: #e6e6e6;
}

.notes-container.dark-mode .note-markdown p,
.notes-container.dark-mode .note-markdown ul > li,
.notes-container.dark-mode .note-markdown li {
  color: #e6e6e6 !important;
  background: none !important;
}

.notes-container.dark-mode .note-markdown ul > li {
  background: #1e293b !important;
  color: #e0eaff !important;
}

.notes-container.dark-mode .note-markdown h1,
.notes-container.dark-mode .note-markdown h2 {
  color: #90caf9;
  background: #1e293b;
}

.notes-container.dark-mode .note-markdown h3 {
  color: #64b5f6;
  background: #1a2332;
}

.notes-container.dark-mode .note-markdown table {
  background: #23272f;
  color: #e6e6e6;
}

.notes-container.dark-mode .note-markdown th {
  background: #2d3542;
  color: #90caf9;
}

.notes-container.dark-mode .note-markdown td {
  color: #e6e6e6;
  background: #1e2329;
}

.notes-container.dark-mode .notes-header {
  background: #23272f;
  border: 1px solid #3a3f47;
}

.notes-container.dark-mode .el-card {
  background: #23272f;
  border: 1px solid #3a3f47;
}

.zero-hallucination-notice {
  padding: 1rem;
  background: #fef3cd;
  border: 1px solid #f6d55c;
  border-radius: 0.5rem;
  margin-bottom: 1rem;
}

.zero-hallucination-notice h3 {
  margin: 0 0 0.5rem 0;
  color: #856404;
}

.zero-hallucination-notice p {
  margin: 0 0 1rem 0;
  color: #856404;
}

.filtered-content {
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 0.25rem;
  padding: 1rem;
  max-height: 300px;
  overflow-y: auto;
}

.filtered-content pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.9rem;
  line-height: 1.4;
}

/* 自動檢測系統深夜模式 */
@media (prefers-color-scheme: dark) {
  .notes-container {
    background: #181c20;
    color: #e6e6e6;
  }
  .note-markdown {
    background: #23272f;
    color: #e6e6e6;
  }
  .note-markdown p,
  .note-markdown ul > li,
  .note-markdown li {
    color: #e6e6e6 !important;
    background: none !important;
  }
  .note-markdown ul > li {
    background: #1e293b !important;
    color: #e0eaff !important;
  }
  .note-markdown table {
    background: #23272f;
    color: #e6e6e6;
  }
  .note-markdown th {
    background: #2d3542;
    color: #90caf9;
  }
  .note-markdown td {
    color: #e6e6e6;
  }
}
</style> 