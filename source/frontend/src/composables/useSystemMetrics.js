import { computed, ref } from 'vue'

const snapshot = ref(null)
const lastError = ref(null)
const status = ref('idle')
let pollTimer = null
let pollIntervalMs = 5000
let activeSubscribers = 0
let fetchInFlight = null

function normalizeSummary(data) {
  if (!data) {
    return {
      cpuPercent: null,
      ramPercent: null,
      gpuUtilPercent: null,
      gpuMemUsedMb: null,
      gpuMemTotalMb: null,
      gpuTempC: null,
      timestamp: null,
      status: null
    }
  }

  const cpuPercent = data?.host?.cpu?.percent ?? null
  const ramPercent = data?.host?.ram?.percent ?? null
  const firstGpu = Array.isArray(data?.gpu) ? data.gpu[0] : null
  const gpuUtilPercent = firstGpu?.util_percent ?? null
  const gpuMemUsedMb = firstGpu?.mem_mb?.used ?? null
  const gpuMemTotalMb = firstGpu?.mem_mb?.total ?? null
  const gpuTempC = firstGpu?.temp_c ?? null

  return {
    cpuPercent,
    ramPercent,
    gpuUtilPercent,
    gpuMemUsedMb,
    gpuMemTotalMb,
    gpuTempC,
    timestamp: data?.collected_at || data?.timestamp || null,
    status: data?.status ?? 'ok',
    missing: data?.missing ?? []
  }
}

async function fetchSnapshot(force = false) {
  if (fetchInFlight) {
    return fetchInFlight
  }

  status.value = 'loading'
  fetchInFlight = fetch('/api/system/metrics', {
    headers: { Accept: 'application/json' }
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`system metrics request failed: ${response.status}`)
      }
      const payload = await response.json()
      const metricsPayload = payload?.metrics ?? payload?.snapshot ?? null
      snapshot.value = metricsPayload
      lastError.value = null
      status.value = activeSubscribers > 0 ? 'polling' : 'idle'
      return snapshot.value
    })
    .catch((error) => {
      lastError.value = error
      status.value = 'error'
      console.warn('[system-metrics] failed to fetch metrics', error)
      return null
    })
    .finally(() => {
      fetchInFlight = null
    })

  return fetchInFlight
}

function startPolling(intervalMs = 10000) {
  activeSubscribers += 1
  pollIntervalMs = intervalMs

  if (pollTimer) {
    return
  }

  status.value = 'polling'
  fetchSnapshot(true).catch(() => {})

  pollTimer = setInterval(() => {
    fetchSnapshot().catch(() => {})
  }, pollIntervalMs)
}

function stopPolling() {
  activeSubscribers = Math.max(0, activeSubscribers - 1)
  if (activeSubscribers === 0 && pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
    if (status.value !== 'error') {
      status.value = 'idle'
    }
  }
}

export function useSystemMetrics() {
  return {
    snapshot,
    summary: computed(() => normalizeSummary(snapshot.value)),
    status: computed(() => status.value),
    lastError: computed(() => lastError.value),
    startPolling,
    stopPolling,
    refresh: () => fetchSnapshot(true)
  }
}
