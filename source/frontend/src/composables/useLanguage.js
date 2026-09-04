// 簡化的語言管理系統
import { ref, computed, watch } from 'vue'
import { getTranslation } from '../i18n/index.js'

// 全局語言狀態 - 確保正確初始化
const getInitialLanguage = () => {
  const saved = localStorage.getItem('notegen-language') || localStorage.getItem('selected-language')
  return saved || 'zh-TW'
}

const currentLanguage = ref(getInitialLanguage())

// 切換語言函數
const switchLanguage = (langCode) => {
  currentLanguage.value = langCode
  localStorage.setItem('notegen-language', langCode)
  
  // 觸發全局事件
  window.dispatchEvent(new CustomEvent('languageChanged', { detail: langCode }))
}

// 監聽語言變化
watch(currentLanguage, (newLang) => {
  localStorage.setItem('notegen-language', newLang)
})

// 組合式函數
export function useLanguage() {
  // 創建響應式翻譯函數
  const t = (key, params = {}) => {
    try {
      // 確保使用當前語言狀態
      const lang = currentLanguage.value
      const translation = getTranslation(key, lang)
      
      // 處理參數替換
      if (typeof translation === 'string' && Object.keys(params).length > 0) {
        const result = translation.replace(/\{(\w+)\}/g, (match, paramKey) => {
          return params[paramKey] !== undefined ? params[paramKey] : match
        })
        return result
      }
      
      return translation || key // 如果翻譯不存在，返回key作為後備
    } catch (error) {
      console.error('Translation error:', error)
      return key // 錯誤時返回key
    }
  }
  
  return {
    currentLanguage,
    t,
    switchLanguage
  }
}

// 導出單獨的狀態和函數（向後兼容）
export { currentLanguage, switchLanguage }