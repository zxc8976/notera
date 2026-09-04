<template>
  <div class="table-term-container">
    <div class="table-header">
      <h3>📚 術語對照</h3>
      <el-button size="small" type="primary" plain @click="copyAsTSV">
        📋 複製為 TSV
      </el-button>
    </div>
    
    <div class="table-wrapper">
      <table class="term-table">
        <thead>
          <tr>
            <th class="col-jp">JP（日文）</th>
            <th class="col-tw">TW（中文）</th>
            <th class="col-desc">說明</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in rows" :key="index">
            <td class="col-jp">{{ row.jp }}</td>
            <td class="col-tw">{{ row.tw }}</td>
            <td class="col-desc">{{ row.desc }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    
    <div v-if="evidence && evidence.length > 0" class="evidence-section">
      <div class="evidence-header">📍 來源證據</div>
      <div class="evidence-list">
        <span v-for="(item, index) in evidence" :key="index" class="evidence-item">
          {{ item }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ElMessage } from 'element-plus'

const props = defineProps({
  rows: {
    type: Array,
    required: true,
    default: () => []
  },
  evidence: {
    type: Array,
    default: () => []
  }
})

// 複製為 TSV 格式
const copyAsTSV = async () => {
  const tsvContent = [
    'JP（日文）\tTW（中文）\t說明',
    ...props.rows.map(row => `${row.jp}\t${row.tw}\t${row.desc}`)
  ].join('\n')
  
  try {
    await navigator.clipboard.writeText(tsvContent)
    ElMessage.success('已複製為 TSV 格式到剪貼簿')
  } catch (err) {
    ElMessage.error('複製失敗')
  }
}
</script>

<style scoped>
.table-term-container {
  background: var(--card);
  border-radius: var(--radius-xl);
  border: 1px solid var(--border);
  margin: var(--space-4) 0;
  overflow: hidden;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3);
  background: var(--card);
  border-bottom: 1px solid var(--border);
}

.table-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--fg);
}

.table-wrapper {
  overflow-x: auto;
}

.term-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--card);
}

.term-table th,
.term-table td {
  padding: var(--space-3);
  text-align: left;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}

.term-table th {
  background: var(--card);
  font-weight: 600;
  color: var(--fg);
  position: sticky;
  top: 0;
  z-index: 10;
}

.term-table td {
  color: var(--fg);
  line-height: 1.6;
}

/* 固定欄位寬度 */
.col-jp {
  width: 28%;
  min-width: 120px;
}

.col-tw {
  width: 28%;
  min-width: 120px;
}

.col-desc {
  width: 44%;
  min-width: 200px;
}

/* 長文自動換行 */
.term-table td {
  word-wrap: break-word;
  word-break: break-word;
  hyphens: auto;
}

.evidence-section {
  padding: var(--space-3);
  background: var(--card);
  border-top: 1px solid var(--border);
}

.evidence-header {
  font-weight: 600;
  margin-bottom: var(--space-2);
  color: var(--fg);
  font-size: 14px;
}

.evidence-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.evidence-item {
  background: var(--bg);
  color: var(--muted);
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  border: 1px solid var(--border);
}

/* 響應式設計 */
@media (max-width: 768px) {
  .table-header {
    flex-direction: column;
    gap: var(--space-2);
    align-items: flex-start;
  }
  
  .col-jp,
  .col-tw,
  .col-desc {
    width: auto;
    min-width: 100px;
  }
  
  .term-table th,
  .term-table td {
    padding: var(--space-2);
    font-size: 14px;
  }
}

/* 列印樣式 */
@media print {
  .table-header .el-button {
    display: none;
  }
  
  .term-table {
    break-inside: avoid;
  }
  
  .term-table th {
    background: #f5f5f5 !important;
    color: #000 !important;
  }
}
</style>
