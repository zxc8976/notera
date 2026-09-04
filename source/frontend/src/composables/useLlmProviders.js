import { ref, computed } from 'vue'

const providersState = ref([])
const activeName = ref(null)
const status = ref('idle')
const error = ref(null)
let inflight = null

async function fetchProviders(force = false) {
  if (inflight) {
    return inflight
  }
  if (status.value === 'success' && !force) {
    return { providers: providersState.value, active: activeName.value }
  }

  status.value = 'loading'
  inflight = fetch('/api/llm/providers', {
    headers: { Accept: 'application/json' }
  })
    .then(async (resp) => {
      if (!resp.ok) {
        throw new Error(`llm providers request failed: ${resp.status}`)
      }
      const payload = await resp.json()
      providersState.value = Array.isArray(payload?.providers) ? payload.providers : []
      activeName.value = payload?.active || null
      status.value = 'success'
      error.value = null
      return payload
    })
    .catch((err) => {
      status.value = 'error'
      error.value = err
      return null
    })
    .finally(() => {
      inflight = null
    })

  return inflight
}

export function useLlmProviders() {
  if (status.value === 'idle') {
    fetchProviders().catch(() => {})
  }

  return {
    providers: computed(() => providersState.value),
    activeProvider: computed(() =>
      providersState.value.find((item) => item.name === activeName.value) || null
    ),
    status: computed(() => status.value),
    error: computed(() => error.value),
    refresh: (force = false) => fetchProviders(force)
  }
}
