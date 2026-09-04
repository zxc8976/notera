import { computed, ref } from 'vue'

const DEFAULT_DISPLAY_VERSION = '3.0.7-enhanced'
const RAW_DISPLAY_VERSION = (import.meta.env?.VITE_APP_VERSION ?? '').toString().trim()
const DISPLAY_VERSION = RAW_DISPLAY_VERSION || DEFAULT_DISPLAY_VERSION
const NORMALIZED_DISPLAY = normalize(DISPLAY_VERSION)

const backendVersion = ref(null)
const lastFetchedAt = ref(null)
const fetchInFlight = ref(false)
const mismatchNotified = ref(false)

function normalize(version) {
  if (!version) return ''
  return String(version).trim().replace(/^v/i, '').toLowerCase()
}

async function fetchBackendVersion({ force = false } = {}) {
  if (fetchInFlight.value) {
    return backendVersion.value
  }
  if (!force && backendVersion.value) {
    return backendVersion.value
  }

  fetchInFlight.value = true
  try {
    const response = await fetch('/api/diagnose', {
      headers: { 'Accept': 'application/json' }
    })
    if (!response.ok) {
      throw new Error(`diagnose request failed: ${response.status}`)
    }
    const payload = await response.json()
    backendVersion.value = payload?.version ?? null
    lastFetchedAt.value = Date.now()

    const normalizedBackend = normalize(backendVersion.value)
    if (
      normalizedBackend &&
      normalizedBackend !== NORMALIZED_DISPLAY &&
      !mismatchNotified.value
    ) {
      mismatchNotified.value = true
      console.info('[app-version] Display version differs from backend version', {
        display: `v${DISPLAY_VERSION}`,
        backend: backendVersion.value
      })
      if (typeof window !== 'undefined') {
        window.dispatchEvent(
          new CustomEvent('appVersionMismatch', {
            detail: {
              displayVersion: `v${DISPLAY_VERSION}`,
              backendVersion: backendVersion.value,
              fetchedAt: lastFetchedAt.value
            }
          })
        )
      }
    }
  } catch (error) {
    console.warn('[app-version] Failed to fetch backend version', error)
  } finally {
    fetchInFlight.value = false
  }

  return backendVersion.value
}

export function useAppVersion() {
  return {
    displayVersion: computed(() => DISPLAY_VERSION),
    backendVersion: computed(() => backendVersion.value),
    lastFetchedAt: computed(() => lastFetchedAt.value),
    fetchBackendVersion
  }
}
