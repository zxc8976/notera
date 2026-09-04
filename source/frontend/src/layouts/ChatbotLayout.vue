<template>
  <div class="app-container" :class="{ 'dark-mode': isDark }">
    <!-- 統一頂部導航 -->
    <AppHeader 
      :isDark="isDark" 
      :version="version" 
      @toggle-theme="handleToggleDark"
      @language-change="handleLanguageChange"
    />
    
    <!-- Chatbot專用工具欄 -->
    <div class="chatbot-toolbar">
      <div class="toolbar-content">
        <div class="toolbar-left">
          <h2 class="page-title">{{ t('chatbot') }}</h2>
        </div>
        <div class="toolbar-right">
          <button class="action-btn new-chat" @click="$emit('new-chat')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            {{ t('newChat') }}
          </button>
        </div>
      </div>
    </div>

    <!-- 聊天內容區域 -->
    <main class="app-main chatbot-main">
      <slot />
    </main>
  </div>
</template>

<script>
import { onMounted } from 'vue'
import AppHeader from '../components/AppHeader.vue'
import { useLanguage } from '../composables/useLanguage.js'
import { useTheme } from '../composables/useTheme.js'
import { useAppVersion } from '../composables/useAppVersion.js'

export default {
  name: 'ChatbotLayout',
  components: {
    AppHeader
  },
  emits: ['new-chat'],
  setup() {
    const { displayVersion, fetchBackendVersion } = useAppVersion()
    onMounted(() => {
      fetchBackendVersion().catch(() => {})
    })
    
    // 使用統一的主題系統
    const { isDark, toggleTheme } = useTheme()
    
    // 使用語言系統
    const { currentLanguage, t, switchLanguage } = useLanguage()

    const handleToggleDark = () => {
      toggleTheme()
    }

    const handleLanguageChange = (newLanguage) => {
      switchLanguage(newLanguage)
    }

    return {
      isDark,
      version: displayVersion,
      t,
      currentLanguage,
      handleToggleDark,
      handleLanguageChange
    }
  }
}
</script>

<style scoped>
.app-container {
  min-height: 100vh;
  background: var(--bg-color);
  color: var(--text-color);
  transition: all 0.3s ease;
}

/* Chatbot專用工具欄 */
.chatbot-toolbar {
  background: var(--card-bg);
  border-bottom: 1px solid var(--border-color);
  padding: 0.75rem 1.5rem;
}

.toolbar-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  max-width: 1200px;
  margin: 0 auto;
}

.toolbar-left {
  display: flex;
  align-items: center;
}

.page-title {
  font-size: 1.25rem;
  font-weight: 600;
  margin: 0;
  color: var(--text-color);
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 0.5rem;
  background: var(--primary-color);
  color: white;
  font-weight: 500;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.15s ease;
  font-size: 0.875rem;
}

.action-btn:hover {
  background: var(--primary-hover);
  transform: translateY(-1px);
}

.action-btn svg {
  width: 16px;
  height: 16px;
}

.app-main {
  min-height: calc(100vh - 64px - 56px); /* 減去header和toolbar的高度 */
}

.chatbot-main {
  background: var(--bg-color);
}

/* 確保變量正確定義 */
.app-container {
  --bg-color: #ffffff;
  --text-color: #333333;
  --border-color: #e0e0e0;
  --card-bg: #f5f5f5;
  --bg-secondary: #f8f9fa;
  --text-secondary: #6c757d;
  --primary-color: #0078d7;
  --primary-hover: #106ebe;
}

/* 深色模式 */
.app-container.dark-mode {
  --bg-color: #1a1a1a;
  --text-color: #ffffff;
  --border-color: #333;
  --card-bg: #2d2d2d;
  --bg-secondary: #404040;
  --text-secondary: #b3b3b3;
}
</style>
