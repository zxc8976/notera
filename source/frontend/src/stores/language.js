// 全局語言狀態管理
import { ref, computed } from 'vue'
import { getTranslation } from '../i18n/index.js'

// 全局語言狀態
const currentLanguage = ref(localStorage.getItem('notegen-language') || 'zh-TW')

// 響應式翻譯函數
const t = computed(() => (key) => getTranslation(key, currentLanguage.value))

// 切換語言函數
const switchLanguage = (langCode) => {
  console.log('全局語言切換:', langCode)
  currentLanguage.value = langCode
  localStorage.setItem('notegen-language', langCode)
  
  // 觸發全局語言變更事件
  window.dispatchEvent(new CustomEvent('languageChanged', { detail: langCode }))
  window.dispatchEvent(new StorageEvent('storage', {
    key: 'notegen-language',
    newValue: langCode,
    oldValue: localStorage.getItem('notegen-language')
  }))
}

// 監聽語言變化
const useLanguage = () => {
  const handleLanguageChange = (event) => {
    const newLang = event.detail || localStorage.getItem('notegen-language') || 'zh-TW'
    if (newLang !== currentLanguage.value) {
      currentLanguage.value = newLang
    }
  }
  
  const handleStorageChange = (event) => {
    if (event.key === 'notegen-language') {
      const newLang = event.newValue || 'zh-TW'
      if (newLang !== currentLanguage.value) {
        currentLanguage.value = newLang
      }
    }
  }
  
  // 添加事件監聽器
  window.addEventListener('languageChanged', handleLanguageChange)
  window.addEventListener('storage', handleStorageChange)
  
  // 返回清理函數
  return () => {
    window.removeEventListener('languageChanged', handleLanguageChange)
    window.removeEventListener('storage', handleStorageChange)
  }
}

export {
  currentLanguage,
  t,
  switchLanguage,
  useLanguage
}