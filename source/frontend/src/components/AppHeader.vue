<template>
  <header class="app-header">
    <div class="header-left">
      <div class="app-logo">
        <svg class="logo-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
        </svg>
        <h1 class="app-title">{{ t('appTitle') }}</h1>
      </div>
      
      <!-- 導航菜單 -->
      <nav class="nav-menu">
        <router-link to="/" class="nav-item" :class="{ active: $route.path === '/' }">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
            <polyline points="9,22 9,12 15,12 15,22" />
          </svg>
          {{ t('home') }}
        </router-link>
        
        <router-link to="/notes" class="nav-item" :class="{ active: $route.path === '/notes' }">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14,2 14,8 20,8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10,9 9,9 8,9" />
          </svg>
          {{ t('noteManagement') }}
        </router-link>
        
        <router-link to="/chatbot" class="nav-item" :class="{ active: $route.path === '/chatbot' }">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
          {{ t('chatbot') }}
        </router-link>
      </nav>
    </div>
    <div class="header-right">
      <div class="version-info">v{{ version }}</div>
      <select class="lang-select" @change="handleLanguageChange($event.target.value)">
        <option value="zh-TW" :selected="currentLanguage==='zh-TW'">繁體中文</option>
        <option value="zh-CN" :selected="currentLanguage==='zh-CN'">简体中文</option>
        <option value="ja" :selected="currentLanguage==='ja'">日本語</option>
        <option value="en" :selected="currentLanguage==='en'">English</option>
        <option value="ko" :selected="currentLanguage==='ko'">한국어</option>
        <option value="vi" :selected="currentLanguage==='vi'">Tiếng Việt</option>
        <option value="my" :selected="currentLanguage==='my'">မြန်မာဘာသာ</option>
        <option value="mn" :selected="currentLanguage==='mn'">Монгол хэл</option>
      </select>
      <button 
        class="theme-toggle" 
        @click="toggleTheme" 
        :title="themeTooltip"
      >
        <svg v-if="currentTheme==='dark'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="5" />
          <line x1="12" y1="1" x2="12" y2="3" />
          <line x1="12" y1="21" x2="12" y2="23" />
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
          <line x1="1" y1="12" x2="3" y2="12" />
          <line x1="21" y1="12" x2="23" y2="12" />
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
        </svg>
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
      </button>
    </div>
  </header>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { useLanguage } from '../composables/useLanguage.js'
import { useTheme } from '../composables/useTheme.js'

const props = defineProps({
  isDark: { type: Boolean, default: false },
  version: { type: String, default: '3.0.1' }
})

const emit = defineEmits(['toggle-theme', 'language-change'])

// 使用統一的語言系統
const { currentLanguage, t, switchLanguage } = useLanguage()

// 使用統一的主題系統
const { currentTheme } = useTheme()
const themeTooltip = computed(() => currentTheme.value === 'dark' ? '切換為淺色' : '切換為深色')

function toggleTheme() {
  // 只發事件，讓外層做實際切換
  emit('toggle-theme')
}

function handleLanguageChange(langCode) {
  switchLanguage(langCode)
  emit('language-change', langCode)
}
</script>

<style scoped>
.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px;
  background: var(--card-bg);
  border-bottom: 1px solid var(--border-color);
  backdrop-filter: blur(10px);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 2rem;
}

.app-logo {
  display: flex;
  align-items: center;
  gap: 12px;
}

.nav-menu {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  color: var(--text-secondary);
  text-decoration: none;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  transition: all 0.2s ease;
}

.nav-item:hover {
  color: var(--text-color);
  background: var(--bg-secondary);
}

.nav-item.active {
  color: var(--primary-color);
  background: rgba(16, 163, 127, 0.1);
}

.nav-item svg {
  width: 16px;
  height: 16px;
}

.logo-icon {
  width: 32px;
  height: 32px;
  color: var(--primary-color);
}

.app-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-color);
  margin: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.lang-select { order: 1; }
.theme-toggle { order: 2; }
.version-info { order: 0; margin-right: 8px; }

.theme-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  padding: 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.theme-toggle:hover {
  background: var(--bg-hover);
  border-color: var(--primary-color);
  transform: scale(1.05);
}

.theme-toggle:active {
  transform: scale(0.95);
}

.theme-toggle svg {
  width: 20px;
  height: 20px;
  transition: transform 0.2s ease;
}

.theme-toggle:hover svg {
  transform: rotate(15deg);
}

.version-info {
  padding: 4px 8px;
  background: var(--primary-color);
  color: white;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
}

.lang-select {
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: var(--bg-secondary);
  color: var(--text-primary);
}
</style>
