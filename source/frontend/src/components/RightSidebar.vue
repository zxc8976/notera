<template>
  <div class="right-sidebar" v-show="!isMobile">
    <el-card class="sidebar-card">
      <template #header>
        <div class="sidebar-header">
          <span>⚙️ 工具</span>
        </div>
      </template>
      
      <div class="sidebar-content">
        <!-- 導出功能 -->
        <div class="tool-section">
          <h4>📤 導出</h4>
          <div class="tool-buttons">
            <el-button size="small" @click="exportTo('pdf')" :loading="exporting.pdf">
              📄 PDF
            </el-button>
            <el-button size="small" @click="exportTo('md')" :loading="exporting.md">
              📝 Markdown
            </el-button>
            <el-button size="small" @click="exportTo('html')" :loading="exporting.html">
              🌐 HTML
            </el-button>
          </div>
        </div>
        
        <!-- 語言切換 -->
        <div class="tool-section">
          <h4>🌐 語言</h4>
          <el-radio-group v-model="currentLang" @change="toggleLang" size="small">
            <el-radio-button label="jp">🇯🇵 日文</el-radio-button>
            <el-radio-button label="tw">🇹🇼 中文</el-radio-button>
          </el-radio-group>
        </div>
        
        <!-- 視圖模式 -->
        <div class="tool-section">
          <h4>👁️ 視圖</h4>
          <el-radio-group v-model="viewMode" size="small">
            <el-radio-button label="reading">📖 閱讀</el-radio-button>
            <el-radio-button label="print">🖨️ 列印</el-radio-button>
            <el-radio-button label="presentation">📺 演示</el-radio-button>
          </el-radio-group>
        </div>
        
        <!-- 章節控制 -->
        <div class="tool-section">
          <h4>📑 章節</h4>
          <div class="tool-buttons">
            <el-button size="small" @click="collapseAll">
              📁 全部折疊
            </el-button>
            <el-button size="small" @click="expandAll">
              📂 全部展開
            </el-button>
          </div>
        </div>
        
        <!-- 搜尋功能 -->
        <div class="tool-section">
          <h4>🔍 搜尋</h4>
          <el-input
            v-model="searchQuery"
            placeholder="搜尋內容..."
            size="small"
            clearable
            @input="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
        
        <!-- 目錄 -->
        <div class="tool-section">
          <h4>📋 目錄</h4>
          <div class="toc-list">
            <div
              v-for="item in toc"
              :key="item.id"
              class="toc-item"
              :class="{ active: activeSection === item.id }"
              @click="scrollToSection(item.id)"
            >
              {{ item.title }}
            </div>
          </div>
        </div>
      </div>
    </el-card>
  </div>
  
  <!-- 移動端 FAB 按鈕 -->
  <el-button
    v-show="isMobile"
    class="fab-button"
    type="primary"
    :icon="sidebarVisible ? 'Close' : 'Setting'"
    circle
    @click="toggleMobileSidebar"
  />
  
  <!-- 移動端側邊欄 -->
  <el-drawer
    v-model="sidebarVisible"
    title="工具欄"
    direction="rtl"
    size="280px"
    :with-header="false"
  >
    <div class="mobile-sidebar-content">
      <!-- 複製桌面端內容 -->
      <div class="sidebar-content">
        <!-- 導出功能 -->
        <div class="tool-section">
          <h4>📤 導出</h4>
          <div class="tool-buttons">
            <el-button size="small" @click="exportTo('pdf')" :loading="exporting.pdf">
              📄 PDF
            </el-button>
            <el-button size="small" @click="exportTo('md')" :loading="exporting.md">
              📝 Markdown
            </el-button>
            <el-button size="small" @click="exportTo('html')" :loading="exporting.html">
              🌐 HTML
            </el-button>
          </div>
        </div>
        
        <!-- 語言切換 -->
        <div class="tool-section">
          <h4>🌐 語言</h4>
          <el-radio-group v-model="currentLang" @change="toggleLang" size="small">
            <el-radio-button label="jp">🇯🇵 日文</el-radio-button>
            <el-radio-button label="tw">🇹🇼 中文</el-radio-button>
          </el-radio-group>
        </div>
        
        <!-- 視圖模式 -->
        <div class="tool-section">
          <h4>👁️ 視圖</h4>
          <el-radio-group v-model="viewMode" size="small">
            <el-radio-button label="reading">📖 閱讀</el-radio-button>
            <el-radio-button label="print">🖨️ 列印</el-radio-button>
            <el-radio-button label="presentation">📺 演示</el-radio-button>
          </el-radio-group>
        </div>
        
        <!-- 章節控制 -->
        <div class="tool-section">
          <h4>📑 章節</h4>
          <div class="tool-buttons">
            <el-button size="small" @click="collapseAll">
              📁 全部折疊
            </el-button>
            <el-button size="small" @click="expandAll">
              📂 全部展開
            </el-button>
          </div>
        </div>
        
        <!-- 搜尋功能 -->
        <div class="tool-section">
          <h4>🔍 搜尋</h4>
          <el-input
            v-model="searchQuery"
            placeholder="搜尋內容..."
            size="small"
            clearable
            @input="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
        
        <!-- 目錄 -->
        <div class="tool-section">
          <h4>📋 目錄</h4>
          <div class="toc-list">
            <div
              v-for="item in toc"
              :key="item.id"
              class="toc-item"
              :class="{ active: activeSection === item.id }"
              @click="scrollToSection(item.id)"
            >
              {{ item.title }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'

const props = defineProps({
  toc: {
    type: Array,
    default: () => []
  },
  activeSection: {
    type: String,
    default: ''
  }
})

const emit = defineEmits([
  'export',
  'lang-change',
  'view-change',
  'collapse-all',
  'expand-all',
  'search',
  'scroll-to-section'
])

// 響應式狀態
const isMobile = ref(false)
const sidebarVisible = ref(false)
const currentLang = ref('tw')
const viewMode = ref('reading')
const searchQuery = ref('')

// 導出狀態
const exporting = ref({
  pdf: false,
  md: false,
  html: false
})

// 檢查是否為移動端
const checkMobile = () => {
  isMobile.value = window.innerWidth < 1280
}

// 導出功能
const exportTo = async (format) => {
  exporting.value[format] = true
  
  try {
    emit('export', format)
    ElMessage.success(`正在導出 ${format.toUpperCase()}...`)
  } catch (error) {
    ElMessage.error(`導出 ${format.toUpperCase()} 失敗`)
  } finally {
    setTimeout(() => {
      exporting.value[format] = false
    }, 2000)
  }
}

// 語言切換
const toggleLang = (lang) => {
  emit('lang-change', lang)
}

// 視圖模式切換
const handleViewChange = (mode) => {
  emit('view-change', mode)
}

// 章節控制
const collapseAll = () => {
  emit('collapse-all')
}

const expandAll = () => {
  emit('expand-all')
}

// 搜尋功能
const handleSearch = (query) => {
  emit('search', query)
}

// 滾動到指定章節
const scrollToSection = (sectionId) => {
  emit('scroll-to-section', sectionId)
  if (isMobile.value) {
    sidebarVisible.value = false
  }
}

// 切換移動端側邊欄
const toggleMobileSidebar = () => {
  sidebarVisible.value = !sidebarVisible.value
}

// 生命週期
onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})
</script>

<style scoped>
.right-sidebar {
  position: fixed;
  top: 20px;
  right: 20px;
  width: 280px;
  z-index: 1000;
}

.sidebar-card {
  background: var(--card);
  border: 1px solid var(--border);
  box-shadow: var(--elevation-1);
}

.sidebar-header {
  font-weight: 600;
  color: var(--fg);
}

.sidebar-content {
  max-height: calc(100vh - 120px);
  overflow-y: auto;
}

.tool-section {
  margin-bottom: var(--space-4);
}

.tool-section h4 {
  margin: 0 0 var(--space-2) 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--fg);
}

.tool-buttons {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.tool-buttons .el-button {
  justify-content: flex-start;
}

.toc-list {
  max-height: 200px;
  overflow-y: auto;
}

.toc-item {
  padding: var(--space-1) var(--space-2);
  cursor: pointer;
  border-radius: 4px;
  font-size: 14px;
  color: var(--muted);
  transition: all 0.2s;
}

.toc-item:hover {
  background: var(--border);
  color: var(--fg);
}

.toc-item.active {
  background: var(--primary);
  color: white;
}

.fab-button {
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  z-index: 1001;
}

.mobile-sidebar-content {
  padding: var(--space-3);
  height: 100%;
  overflow-y: auto;
}

/* 響應式設計 */
@media (max-width: 1280px) {
  .right-sidebar {
    display: none;
  }
}

/* 列印樣式 */
@media print {
  .right-sidebar,
  .fab-button {
    display: none !important;
  }
}
</style>
