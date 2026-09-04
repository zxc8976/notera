/**
 * 統一主題管理系統
 * 解決多個組件重複主題邏輯的問題
 */
import { ref, computed } from 'vue'

// 全局主題狀態
const isDark = ref(false)
const isInitialized = ref(false)

// 主題配置
const THEME_CONFIG = {
  STORAGE_KEY: 'pref-theme',
  LEGACY_KEY: 'theme',
  DEFAULT_THEME: 'light'
}

/**
 * 初始化主題系統
 * 只在應用啟動時調用一次
 */
function initializeTheme() {
  if (isInitialized.value) return
  
  try {
    const saved = localStorage.getItem(THEME_CONFIG.STORAGE_KEY)
    const theme = (saved === 'dark' || saved === 'light') ? saved : THEME_CONFIG.DEFAULT_THEME
    const isDarkMode = theme === 'dark'

    isDark.value = isDarkMode
    applyTheme(theme)

    // 遷移舊鍵值
    const legacy = localStorage.getItem(THEME_CONFIG.LEGACY_KEY)
    if (legacy && legacy !== saved) {
      const legacyTheme = (legacy === 'dark' || legacy === 'light') ? legacy : theme
      localStorage.setItem(THEME_CONFIG.STORAGE_KEY, legacyTheme)
      localStorage.removeItem(THEME_CONFIG.LEGACY_KEY)
      applyTheme(legacyTheme)
    }

    isInitialized.value = true
    console.log('🎨 主題系統初始化完成:', theme)
  } catch (error) {
    console.error('主題初始化失敗:', error)
    applyTheme(THEME_CONFIG.DEFAULT_THEME)
    isInitialized.value = true
  }
}

/**
 * 應用主題到DOM
 */
function applyTheme(theme) {
  const html = document.documentElement
  const isDarkMode = theme === 'dark'
  
  // 統一使用 data-theme 屬性
  html.setAttribute('data-theme', theme)
  
  // 保持兼容性：同時設置 class
  html.classList.toggle('dark', isDarkMode)
  document.body.classList.toggle('dark-mode', isDarkMode)
}

/**
 * 切換主題
 */
function toggleTheme() {
  const nextTheme = isDark.value ? 'light' : 'dark'
  isDark.value = !isDark.value
  
  try {
    localStorage.setItem(THEME_CONFIG.STORAGE_KEY, nextTheme)
    // 保持兼容性：同時寫入舊鍵
    localStorage.setItem(THEME_CONFIG.LEGACY_KEY, nextTheme)
  } catch (error) {
    console.error('保存主題設置失敗:', error)
  }
  
  applyTheme(nextTheme)
  console.log('🎨 主題已切換至:', nextTheme)
}

/**
 * 設置特定主題
 */
function setTheme(theme) {
  if (theme !== 'dark' && theme !== 'light') {
    console.warn('無效的主題值:', theme)
    return
  }
  
  const isDarkMode = theme === 'dark'
  isDark.value = isDarkMode
  
  try {
    localStorage.setItem(THEME_CONFIG.STORAGE_KEY, theme)
    localStorage.setItem(THEME_CONFIG.LEGACY_KEY, theme)
  } catch (error) {
    console.error('保存主題設置失敗:', error)
  }
  
  applyTheme(theme)
  console.log('🎨 主題已設置為:', theme)
}

/**
 * 獲取當前主題
 */
function getCurrentTheme() {
  return isDark.value ? 'dark' : 'light'
}

/**
 * 主題組合式函數
 */
export function useTheme() {
  return {
    // 狀態
    isDark: computed(() => isDark.value),
    currentTheme: computed(() => getCurrentTheme()),
    isInitialized: computed(() => isInitialized.value),
    
    // 方法
    initializeTheme,
    toggleTheme,
    setTheme,
    getCurrentTheme
  }
}

// 自動初始化（僅在瀏覽器環境）
if (typeof window !== 'undefined') {
  initializeTheme()
}
