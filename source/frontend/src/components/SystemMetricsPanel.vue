<template>
  <div class="settings-panel system-metrics-compact" :class="{ 'panel-warning': summary.status !== 'ok' }">
    <h3 class="panel-title">
      <svg class="title-icon-small" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 6v6l3 3" />
      </svg>
      {{ t('systemMetricsPanel') }}
    </h3>

    <div class="setting-group">
      <div class="metrics-grid">
        <div class="metric-item">
          <div class="metric-label">{{ t('cpu') }}</div>
          <div class="metric-value">{{ formatPercent(summary.cpuPercent) }}</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">{{ t('ram') }}</div>
          <div class="metric-value">{{ formatPercent(summary.ramPercent) }}</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">{{ t('gpu') }}</div>
          <div class="metric-value">{{ formatPercent(summary.gpuUtilPercent) }}</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">{{ t('vram') }}</div>
          <div class="metric-value">
            <template v-if="summary.gpuMemUsedMb !== null && summary.gpuMemTotalMb !== null">
              {{ summary.gpuMemUsedMb }} / {{ summary.gpuMemTotalMb }} MB
            </template>
            <template v-else>-</template>
          </div>
        </div>
        <div class="metric-item">
          <div class="metric-label">{{ t('gpuTemp') }}</div>
          <div class="metric-value">
            <template v-if="summary.gpuTempC !== null">
              {{ summary.gpuTempC }}°C
            </template>
            <template v-else>-</template>
          </div>
        </div>
        <div class="metric-item">
          <div class="metric-label">{{ t('updatedAt') }}</div>
          <div class="metric-value ts">{{ timestampLabel }}</div>
        </div>
      </div>

      <div class="metrics-actions">
        <button class="btn btn-secondary" @click="handleRefresh" :disabled="status === 'loading'">
          🔄 {{ t('metricsRefreshNow') }}
        </button>
        <button class="btn btn-secondary" @click="emit('diagnose')" :title="t('systemDiagnosis') || 'System diagnose'">
          🩺 {{ t('systemDiagnosis') || '系統診斷' }}
        </button>
        <span class="metrics-hint" v-if="!processingFilename">
          {{ t('metricsHintNoProcessing') }}
        </span>
      </div>

      <p v-if="summary.missing && summary.missing.length" class="metrics-warning">
        {{ t('metricsPartialUnavailable') || '部分指標目前無法取得' }}:
        {{ summary.missing.join(', ') }}
      </p>
      <p v-else-if="status === 'error'" class="metrics-warning">
        {{ t('metricsUnavailable') || '無法取得系統指標，請稍後再試。' }}
      </p>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useSystemMetrics } from '../composables/useSystemMetrics.js'

const props = defineProps({
  t: {
    type: Function,
    default: (key) => key
  },
  processingFilename: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['diagnose'])

const { summary, status, startPolling, stopPolling, refresh } = useSystemMetrics()

const timestampLabel = computed(() => {
  const value = summary.value.timestamp
  if (!value) return '-'
  if (typeof value === 'number') {
    return new Date(value * 1000).toLocaleTimeString()
  }
  const parsed = Date.parse(value)
  return Number.isNaN(parsed) ? value : new Date(parsed).toLocaleTimeString()
})

const formatPercent = (value) => {
  if (value === null || value === undefined) {
    return '-'
  }
  const rounded = Math.round(value * 10) / 10
  return `${rounded}%`
}

const handleRefresh = () => {
  refresh().catch(() => {})
}

onMounted(() => {
  startPolling()
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<style scoped>
/* 緊湊型系統監控面板樣式 */
.system-metrics-compact .metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.system-metrics-compact .metric-item {
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.system-metrics-compact .metric-label {
  font-size: 12px;
  color: var(--text-secondary);
  letter-spacing: 0.4px;
  text-transform: uppercase;
  opacity: 0.85;
}

.system-metrics-compact .metric-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-color);
}

/* 小型標題圖示 */
.title-icon-small {
  width: 16px;
  height: 16px;
  margin-right: 8px;
  opacity: 0.8;
}

.system-metrics-compact .metric-value.ts {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 400;
}

.system-metrics-compact .metrics-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}

.system-metrics-compact .metrics-actions .btn {
  padding: 6px 12px;
  font-size: 13px;
}

.system-metrics-compact .metrics-hint {
  font-size: 11px;
  color: var(--text-secondary);
  opacity: 0.7;
}

.system-metrics-compact .metrics-warning {
  margin-top: 8px;
  font-size: 12px;
  color: #f59e0b;
  padding: 6px 10px;
  background: rgba(245, 158, 11, 0.1);
  border-radius: 6px;
}

@media (max-width: 768px) {
  .system-metrics-compact .metrics-grid {
    grid-template-columns: repeat(1, minmax(0, 1fr));
  }
}

/* 確保面板整體不過於突兀 */
.system-metrics-compact .panel-title {
  font-size: 14px;
  margin-bottom: 12px;
}
</style>
