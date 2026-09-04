// 全局狀態管理 - 解決切換分頁後資料消失的問題
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAppStateStore = defineStore('appState', () => {
  // 處理狀態
  const isProcessing = ref(false)
  const currentProcessingVideo = ref(null)
  const processingProgress = ref({
    status: '',
    progress: 0,
    detail: '',
    elapsed_time: 0,
    estimated_remaining: null,
    current_scene: 0,
    total_scenes: 0,
    steps: []
  })
  
  // 處理結果
  const summaryResult = ref('')
  const processedScenes = ref([])
  const lastProcessedVideo = ref(null)
  
  // 暫存管理
  const tmpDataCache = ref(new Map())
  
  // 影片列表
  const videoList = ref([])
  const selectedFolder = ref('')
  
  // 計算屬性
  const hasActiveProcess = computed(() => {
    return isProcessing.value && currentProcessingVideo.value
  })
  
  const totalKeywords = computed(() => {
    return processedScenes.value.reduce((total, scene) => {
      const keywordMatches = scene.content.match(/\|[^|]*\*\*[^*]+\*\*[^|]*\|/g) || []
      return total + keywordMatches.length
    }, 0)
  })
  
  // Actions
  function startProcessing(videoPath) {
    isProcessing.value = true
    currentProcessingVideo.value = videoPath
    processingProgress.value = {
      status: '啟動中',
      progress: 0,
      detail: '正在初始化...',
      elapsed_time: 0,
      estimated_remaining: null,
      current_scene: 0,
      total_scenes: 0,
      steps: []
    }
  }
  
  function updateProgress(progressData) {
    processingProgress.value = { ...processingProgress.value, ...progressData }
  }
  
  function completeProcessing(result, scenes = []) {
    isProcessing.value = false
    summaryResult.value = result
    processedScenes.value = scenes
    lastProcessedVideo.value = currentProcessingVideo.value
    
    // 保存到 localStorage 以防頁面刷新
    localStorage.setItem('notegen_last_result', JSON.stringify({
      video: currentProcessingVideo.value,
      result: result,
      scenes: scenes,
      timestamp: Date.now()
    }))
  }
  
  function stopProcessing() {
    isProcessing.value = false
    currentProcessingVideo.value = null
    processingProgress.value = {
      status: '',
      progress: 0,
      detail: '',
      elapsed_time: 0,
      estimated_remaining: null,
      current_scene: 0,
      total_scenes: 0,
      steps: []
    }
  }
  
  function updateVideoList(videos) {
    videoList.value = videos
  }
  
  function updateTmpCache(filename, tmpInfo) {
    tmpDataCache.value.set(filename, tmpInfo)
  }
  
  function removeTmpCache(filename) {
    tmpDataCache.value.delete(filename)
  }
  
  function getTmpInfo(filename) {
    return tmpDataCache.value.get(filename)
  }
  
  // 恢復狀態（頁面刷新時）
  function restoreState() {
    try {
      const saved = localStorage.getItem('notegen_last_result')
      if (saved) {
        const data = JSON.parse(saved)
        // 只恢復 24 小時內的結果
        if (Date.now() - data.timestamp < 24 * 60 * 60 * 1000) {
          summaryResult.value = data.result
          processedScenes.value = data.scenes || []
          lastProcessedVideo.value = data.video
        } else {
          // 清理過期數據
          localStorage.removeItem('notegen_last_result')
        }
      }
    } catch (error) {
      console.warn('恢復狀態失敗:', error)
    }
  }
  
  // 清理狀態
  function clearState() {
    summaryResult.value = ''
    processedScenes.value = []
    lastProcessedVideo.value = null
    localStorage.removeItem('notegen_last_result')
  }
  
  return {
    // State
    isProcessing,
    currentProcessingVideo,
    processingProgress,
    summaryResult,
    processedScenes,
    lastProcessedVideo,
    tmpDataCache,
    videoList,
    selectedFolder,
    
    // Computed
    hasActiveProcess,
    totalKeywords,
    
    // Actions
    startProcessing,
    updateProgress,
    completeProcessing,
    stopProcessing,
    updateVideoList,
    updateTmpCache,
    removeTmpCache,
    getTmpInfo,
    restoreState,
    clearState
  }
})

// 自動恢復狀態
export function initializeAppState() {
  const store = useAppStateStore()
  store.restoreState()
  return store
}