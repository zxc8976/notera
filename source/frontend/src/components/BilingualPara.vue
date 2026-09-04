<template>
  <div class="bilingual-para" :class="`view-${view}`">
    <!-- 來源標記 -->
    <SourceBadge
      v-if="showSource && pair.source_ids"
      :source-ids="pair.source_ids"
      :confidence="pair.conf"
      class="source-badge"
    />
    
    <!-- 雙語內容 -->
    <div class="para-content">
      <!-- 分割視圖 -->
      <div v-if="view === 'split'" class="split-view">
        <div class="jp-text">
          <div class="lang-label">日文</div>
          <div class="text-content">{{ pair.jp }}</div>
        </div>
        <div class="tw-text">
          <div class="lang-label">繁中</div>
          <div class="text-content">{{ pair.tw }}</div>
        </div>
      </div>
      
      <!-- 日文視圖 -->
      <div v-else-if="view === 'jp'" class="single-view">
        <div class="lang-label">日文</div>
        <div class="text-content">{{ pair.jp }}</div>
      </div>
      
      <!-- 繁中視圖 -->
      <div v-else-if="view === 'tw'" class="single-view">
        <div class="lang-label">繁中</div>
        <div class="text-content">{{ pair.tw }}</div>
      </div>
    </div>
    
    <!-- 對齊資訊 -->
    <div v-if="showSource && pair.align_info" class="align-info">
      <span class="align-score">對齊分數: {{ Math.round((pair.align_info.score || 0) * 100) }}%</span>
      <span v-if="pair.align_info.method" class="align-method">{{ pair.align_info.method }}</span>
    </div>
  </div>
</template>

<script setup>
import SourceBadge from './SourceBadge.vue'

const props = defineProps({
  pair: {
    type: Object,
    required: true
  },
  view: {
    type: String,
    default: 'split'
  },
  showSource: {
    type: Boolean,
    default: true
  }
})
</script>

<style scoped>
.bilingual-para {
  position: relative;
  background: var(--el-bg-color-page);
  border-radius: 0.5rem;
  padding: 1rem;
  border: 1px solid var(--el-border-color-light);
  transition: all 0.2s ease;
}

.bilingual-para:hover {
  border-color: var(--el-color-primary-light-7);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.source-badge {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  z-index: 1;
}

.para-content {
  margin-top: 0.5rem;
}

/* 分割視圖 */
.split-view {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.jp-text,
.tw-text {
  padding: 0.75rem;
  background: var(--el-bg-color);
  border-radius: 0.375rem;
  border: 1px solid var(--el-border-color-light);
}

.jp-text {
  border-left: 3px solid #e74c3c;
}

.tw-text {
  border-left: 3px solid #3498db;
}

/* 單一視圖 */
.single-view {
  padding: 0.75rem;
  background: var(--el-bg-color);
  border-radius: 0.375rem;
  border: 1px solid var(--el-border-color-light);
}

.lang-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--el-text-color-secondary);
  margin-bottom: 0.5rem;
  letter-spacing: 0.05em;
}

.jp-text .lang-label {
  color: #e74c3c;
}

.tw-text .lang-label {
  color: #3498db;
}

.single-view .lang-label {
  color: var(--el-color-primary);
}

.text-content {
  font-size: 1rem;
  line-height: 1.6;
  color: var(--el-text-color-primary);
  word-break: break-word;
}

/* 對齊資訊 */
.align-info {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--el-border-color-light);
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.8rem;
  color: var(--el-text-color-secondary);
}

.align-score {
  font-weight: 500;
}

.align-method {
  font-style: italic;
}

/* 響應式設計 */
@media (max-width: 768px) {
  .split-view {
    grid-template-columns: 1fr;
    gap: 0.75rem;
  }
  
  .bilingual-para {
    padding: 0.75rem;
  }
  
  .jp-text,
  .tw-text,
  .single-view {
    padding: 0.5rem;
  }
  
  .text-content {
    font-size: 0.9rem;
  }
}

@media (max-width: 480px) {
  .align-info {
    flex-direction: column;
    gap: 0.25rem;
    align-items: flex-start;
  }
}

/* 深色模式適配 */
@media (prefers-color-scheme: dark) {
  .bilingual-para {
    background: #1f1f1f;
    border-color: #333;
  }
  
  .bilingual-para:hover {
    border-color: var(--el-color-primary-light-5);
  }
  
  .jp-text,
  .tw-text,
  .single-view {
    background: #1a1a1a;
    border-color: #333;
  }
  
  .align-info {
    border-top-color: #333;
  }
}
</style>
