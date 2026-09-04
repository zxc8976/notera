<template>
  <div class="plain-text-block">
    <div v-if="ok" class="plain-text" v-html="renderedHtml"></div>
    <el-alert
      v-else
      type="warning"
      :closable="false"
      title="此區內容辨識度過低，已暫不顯示"
      description="建議：重新擷取講義主要區域或切換資料來源（逐字稿 / 另一張截圖），再重生。"
      class="m-2"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { denoiseText, hasMeaningfulText } from '@/utils/contentGuards'
import { cleanMarkdown } from '@/utils/markdownRenderer'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps<{ 
  text: string; 
  evidence?: string[]
}>()

const clean = computed(() => {
  // 先使用 denoiseText 進行基本清理
  let t = denoiseText(props.text)
  // 再使用 markdownRenderer 的清理邏輯 (包含移除 text //)
  t = cleanMarkdown(t)
  return t
})

const ok = computed(() => hasMeaningfulText(clean.value))

const renderedHtml = computed(() => {
  if (!clean.value) return ''
  try {
    const html = marked.parse(clean.value)
    return DOMPurify.sanitize(html)
  } catch (e) {
    return clean.value
  }
})
</script>

<style scoped>
.plain-text-block {
  width: 100%;
}

.plain-text { 
  white-space: pre-wrap; 
  line-height: 1.85; 
  font-size: 15px; 
  color: var(--fg-primary);
  padding: 16px 20px;
  background: var(--surface);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-soft);
}

.m-2 {
  margin: 16px 0;
}
</style>
