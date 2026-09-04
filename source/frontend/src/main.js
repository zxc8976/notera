import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
// Enable Element Plus dark variables support
import 'element-plus/theme-chalk/dark/css-vars.css'
import { ElMessage } from 'element-plus'
// highlight.js / Prism 全域高亮暫停使用，避免干擾自訂渲染
import './styles/theme-unified.css'
// import './styles/code-highlight.css'
import './styles/chatbot.css'
import './styles/modern-ui-enhancement.css'
// import './styles/note-compact.css' // 停用含 hljs 樣式的共用樣式以防程式碼被拆色塊
import 'katex/dist/katex.min.css'

// 主題系統將由 useTheme composable 統一管理

// 全域高亮已停用，避免拆分代碼 token

const app = createApp(App)

// 全局錯誤處理
app.config.errorHandler = (err, vm, info) => {
  // 忽略WebSocket相關錯誤
  if (err.message && (
    err.message.includes('WebSocket') ||
    err.message.includes('ws://') ||
    err.message.includes('0.0.0.0:5173')
  )) {
    return
  }
  
  console.error('Vue Error:', err)
  console.log('Error Info:', info)
  console.error('Error Stack:', err.stack)
  
  // 顯示用戶友好的錯誤提示
  let errorMessage = '系統發生錯誤'
  if (err.message) {
    if (err.message.includes('Failed to fetch')) {
      errorMessage = '網絡連接失敗，請檢查網絡狀態'
    } else if (err.message.includes('timeout')) {
      errorMessage = '請求超時，請稍後重試'
    } else if (err.message.includes('JSON')) {
      errorMessage = '數據格式錯誤，請重新嘗試'
    } else {
      errorMessage = `系統錯誤: ${err.message}`
    }
  }
  
  ElMessage.error(errorMessage)
}

// 全局警告處理
app.config.warnHandler = (msg, vm, trace) => {
  // 忽略特定警告
  if (
    msg.includes('Navigation cancelled') || 
    msg.includes('avoided redundant navigation') ||
    msg.includes('WebSocket') ||
    msg.includes('ws://') ||
    msg.includes('0.0.0.0:5173')
  ) {
    return
  }
  console.warn('Vue Warning:', msg)
  if (trace) console.log('Warning Trace:', trace)
}

// 路由錯誤處理
router.onError((error) => {
  // 忽略WebSocket相關錯誤
  if (error.message && (
    error.message.includes('WebSocket') ||
    error.message.includes('ws://') ||
    error.message.includes('0.0.0.0:5173')
  )) {
    return
  }
  console.error('Router Error:', error)
})

// 處理未捕獲的Promise錯誤
window.addEventListener('unhandledrejection', (event) => {
  const error = event.reason
  
  // 忽略WebSocket相關錯誤
  if (error && error.message && (
    error.message.includes('WebSocket') ||
    error.message.includes('ws://') ||
    error.message.includes('0.0.0.0:5173')
  )) {
    event.preventDefault()
    return
  }
  
  console.error('Unhandled Promise Rejection:', error)
  
  // 顯示用戶友好的錯誤提示
  let errorMessage = '處理過程中發生錯誤'
  if (error && error.message) {
    if (error.message.includes('Failed to fetch')) {
      errorMessage = '網絡連接失敗，請檢查網絡狀態'
    } else if (error.message.includes('timeout')) {
      errorMessage = '請求超時，請稍後重試'
    } else if (error.message.includes('JSON')) {
      errorMessage = '數據格式錯誤，請重新嘗試'
    } else {
      errorMessage = `處理錯誤: ${error.message}`
    }
  }
  
  ElMessage.error(errorMessage)
  event.preventDefault() // 防止錯誤在控制台顯示
})

app.use(router)
app.use(ElementPlus)
app.mount('#app') 
