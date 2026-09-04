<template>
  <div class="app-container" :class="{ 'dark-mode': isDark }">
    <!-- 統一頂部導航 -->
    <AppHeader 
      :isDark="isDark" 
      :version="version" 
      @toggle-theme="handleToggleDark"
      @language-change="handleLanguageChange"
    />

    <!-- 主要內容區域 -->
    <main class="app-main">
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
  name: 'DefaultLayout',
  components: {
    AppHeader
  },
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

.app-main {
  min-height: calc(100vh - 80px);
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
