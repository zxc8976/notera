import { computed, ref } from 'vue'

const manifestRef = ref(null)
const statusRef = ref('idle')
const mismatchRef = ref(false)
const errorRef = ref(null)
let inflight = null
let hasLoaded = false

function evaluateMismatch(hash) {
  try {
    if (!hash) {
      mismatchRef.value = false
      return
    }
    const stored = window.localStorage.getItem('promptManifestHash')
    mismatchRef.value = Boolean(stored && stored !== hash)
    window.localStorage.setItem('promptManifestHash', hash)
  } catch (err) {
    console.warn('[prompt-manifest] unable to read localStorage', err)
    mismatchRef.value = false
  }
}

async function fetchManifest(force = false) {
  if (inflight) {
    return inflight
  }
  if (hasLoaded && !force) {
    return manifestRef.value
  }

  statusRef.value = 'loading'
  inflight = fetch('/api/prompts/manifest', {
    headers: { Accept: 'application/json' },
  })
    .then(async (resp) => {
      if (!resp.ok) {
        throw new Error(`prompt manifest request failed: ${resp.status}`)
      }
      const data = await resp.json()
      manifestRef.value = data
      evaluateMismatch(data?.hash)
      errorRef.value = null
      statusRef.value = 'success'
      hasLoaded = true
      return manifestRef.value
    })
    .catch((err) => {
      errorRef.value = err
      statusRef.value = 'error'
      console.warn('[prompt-manifest] failed to load', err)
      return null
    })
    .finally(() => {
      inflight = null
    })

  return inflight
}

export function usePromptManifest() {
  if (!hasLoaded) {
    fetchManifest().catch(() => {})
  }

  return {
    manifest: computed(() => manifestRef.value),
    status: computed(() => statusRef.value),
    mismatch: computed(() => mismatchRef.value),
    error: computed(() => errorRef.value),
    refresh: () => fetchManifest(true),
  }
}
