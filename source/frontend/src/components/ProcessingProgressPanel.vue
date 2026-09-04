<template>
  <div class="progress-panel">
    <div class="progress-panel__header">
      <div class="progress-panel__title">
        <span>📡 即時進度</span>
        <span class="progress-panel__job" v-if="jobId">#{{ jobId }}</span>
      </div>
      <div class="progress-panel__status">
        <span :class="[{ online: isStreaming }, { offline: !isStreaming }]">
          {{ isStreaming ? '串流連線中' : fallbackActive ? '使用輪詢回退' : '等待更新' }}
        </span>
      </div>
    </div>
    <div class="progress-panel__body" v-if="orderedEvents.length">
      <ul class="progress-timeline">
        <li
          v-for="event in orderedEvents"
          :key="eventKey(event)"
          class="progress-timeline__item"
          :class="['status-' + (event.status || 'running')]"
        >
          <div class="timeline-item__header">
            <span class="timeline-item__stage">{{ stageLabel(event.stage) }}</span>
            <span class="timeline-item__progress">{{ formatProgress(event.progress) }}</span>
          </div>
          <div class="timeline-item__message">
            {{ event.message || '（無訊息）' }}
          </div>
          <div class="timeline-item__meta">
            <span class="timeline-item__status">{{ formatStatus(event.status) }}</span>
            <span class="timeline-item__time">{{ formatTimestamp(event.timestamp) }}</span>
          </div>
          <div
            v-if="showErrorDetails(event)"
            class="timeline-item__error"
          >
            <span class="timeline-item__error-code">#{{ event.error_code }}</span>
            <span class="timeline-item__action">{{ event.recommended_action }}</span>
          </div>
        </li>
      </ul>
    </div>
    <div class="progress-panel__empty" v-else>
      <span>暫無進度事件</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  events: {
    type: Array,
    default: () => []
  },
  jobId: {
    type: String,
    required: true
  },
  isStreaming: {
    type: Boolean,
    default: false
  },
  fallbackActive: {
    type: Boolean,
    default: false
  }
})

const stageMap = {
  ingest: '準備資源',
  'scene-detection': '場景偵測',
  'scene-processing': '場景處理',
  ocr: 'OCR 文字擷取',
  vlm: '多模態分析',
  formatting: '筆記格式化',
  saving: '寫入與同步',
  completed: '完成',
  error: '錯誤',
  processing: '處理中',
  queued: '待執行',
  removed: '已清除',
  finished: '已結束',
  starting: '初始化'
}

const statusMap = {
  running: '執行中',
  starting: '啟動中',
  queued: '排隊中',
  retrying: '重試中',
  warning: '警告',
  failed: '失敗',
  completed: '完成',
  removed: '已清除'
}

const orderedEvents = computed(() => {
  const items = Array.isArray(props.events) ? [...props.events] : []
  return items
    .filter(event => event && event.timestamp !== undefined)
    .sort((a, b) => {
      const ta = Number(a.timestamp) || 0
      const tb = Number(b.timestamp) || 0
      return ta - tb
    })
})

const stageLabel = (stage) => {
  return stageMap[stage] || stage || '未分類'
}

const formatStatus = (status) => {
  if (!status) return '執行中'
  return statusMap[status] || status
}

const formatTimestamp = (ts) => {
  if (!ts && ts !== 0) return '--:--'
  const value = Number(ts)
  const date = Number.isNaN(value) ? new Date(ts) : new Date(value * 1000)
  if (Number.isNaN(date.getTime())) {
    return '--:--'
  }
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

const formatProgress = (progress) => {
  if (progress === null || progress === undefined) return '--'
  return `${Math.round(progress)}%`
}

const showErrorDetails = (event) => {
  if (!event) return false
  const status = event.status || ''
  return (status === 'failed' || status === 'retrying') && event.error_code
}

const eventKey = (event) => {
  const ts = event.timestamp || Date.now()
  return `${event.job_id || props.jobId}-${event.stage || 'unknown'}-${ts}-${event.status || 'running'}`
}
</script>

<style scoped>
.progress-panel {
  margin-top: 12px;
  padding: 12px;
  border-radius: 12px;
  background: rgba(17, 24, 39, 0.9);
  border: 1px solid rgba(59, 130, 246, 0.2);
  color: #e2e8f0;
}

.progress-panel__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.progress-panel__title {
  font-weight: 600;
  display: flex;
  gap: 8px;
  align-items: center;
}

.progress-panel__job {
  font-size: 12px;
  padding: 2px 6px;
  background: rgba(59, 130, 246, 0.15);
  border-radius: 6px;
  color: #bfdbfe;
}

.progress-panel__status span {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.progress-panel__status span.online {
  background: rgba(16, 185, 129, 0.15);
  border-color: rgba(16, 185, 129, 0.3);
  color: #6ee7b7;
}

.progress-panel__status span.offline {
  background: rgba(251, 191, 36, 0.15);
  border-color: rgba(251, 191, 36, 0.3);
  color: #fcd34d;
}

.progress-panel__body {
  max-height: 220px;
  overflow-y: auto;
  padding-right: 4px;
}

.progress-panel__empty {
  padding: 12px;
  text-align: center;
  color: rgba(148, 163, 184, 0.9);
  font-size: 13px;
}

.progress-timeline {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.progress-timeline__item {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(30, 41, 59, 0.65);
  font-size: 13px;
  line-height: 1.5;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.progress-timeline__item.status-completed {
  border-color: rgba(16, 185, 129, 0.35);
  background: rgba(16, 185, 129, 0.12);
}

.progress-timeline__item.status-failed {
  border-color: rgba(239, 68, 68, 0.35);
  background: rgba(239, 68, 68, 0.12);
}

.progress-timeline__item.status-warning,
.progress-timeline__item.status-retrying {
  border-color: rgba(251, 191, 36, 0.35);
  background: rgba(251, 191, 36, 0.12);
}

.timeline-item__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  color: #bfdbfe;
}

.timeline-item__stage {
  font-size: 13px;
}

.timeline-item__progress {
  font-size: 12px;
  color: #93c5fd;
}

.timeline-item__message {
  color: #e2e8f0;
}

.timeline-item__meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #94a3b8;
}

.timeline-item__error {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: #fca5a5;
  background: rgba(239, 68, 68, 0.08);
  border-left: 2px solid rgba(239, 68, 68, 0.6);
  padding: 6px 8px;
  border-radius: 6px;
}

.timeline-item__error-code {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.timeline-item__action {
  color: #f87171;
}

.progress-panel__body::-webkit-scrollbar {
  width: 6px;
}

.progress-panel__body::-webkit-scrollbar-track {
  background: transparent;
}

.progress-panel__body::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.3);
  border-radius: 999px;
}
</style>
