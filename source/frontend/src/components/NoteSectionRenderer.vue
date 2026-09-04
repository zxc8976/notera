<template>
  <section v-if="visible" :id="section.id" class="note-section card">
    <div v-if="section.type === 'heading'" class="section-header">
      <span class="chip">{{ section.icon || '📘' }}</span>
      <h2>{{ section.title }}</h2>
      <p v-if="section.subtitle" class="subtitle">{{ section.subtitle }}</p>
    </div>

    <!-- 段落內容 -->
    <div v-if="section.type === 'paragraphs'" class="paragraph-section">
      <PlainTextBlock 
        v-for="(block, idx) in section.blocks" 
        :key="idx"
        :text="typeof block === 'string' ? block : (block.japanese || block.text || block.tw)"
        :evidence="block.evidence"
      />
    </div>

    <!-- 程式碼區塊 -->
    <div v-if="section.type === 'code-list'" class="code-section">
      <SuperCodeBlock
        v-for="(item, idx) in section.items"
        :key="idx"
        :code="item.code"
        :language="item.language || section.language || 'java'"
        :title="item.title"
        :explanation="item.explanation ? [item.explanation] : []"
        :evidence="item.evidence"
      />
    </div>

    <!-- 術語對照表 -->
    <div v-if="section.type === 'table'" class="terminology-table">
      <div class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th style="width: 28%; white-space: nowrap;">🇯🇵 日文</th>
              <th style="width: 28%; white-space: nowrap;">🇹🇼 中文</th>
              <th style="width: 44%;">📝 說明</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in section.rows" :key="idx">
              <td style="word-wrap: break-word; word-break: break-word;">{{ row[0] }}</td>
              <td style="word-wrap: break-word; word-break: break-word;">{{ row[1] }}</td>
              <td style="word-wrap: break-word; word-break: break-word;">{{ row[2] }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 問題與練習 -->
    <div v-if="section.type === 'problems'" class="problems-section">
      <div v-for="(problem, idx) in section.items" :key="idx" class="problem-card">
        <h4>練習 {{ idx + 1 }}</h4>
        <p><strong>題目：</strong>{{ problem.prompt_tw || problem.prompt_jp }}</p>
        <details>
          <summary>🔄 查看答案</summary>
          <div class="answer">
            <strong>答案：</strong>{{ problem.answer }}
          </div>
        </details>
      </div>
    </div>

    <!-- Q&A 區塊 -->
    <div v-if="section.type === 'qa'" class="qa-section">
      <details v-for="(qa, idx) in section.items" :key="idx" class="qa-item">
        <summary>
          <span class="qa-icon">❓</span>
          <strong>{{ qa.q_tw || qa.question_jp || qa.question_tw }}</strong>
        </summary>
        <div class="answer">
          <span class="answer-icon">✅</span>
          {{ qa.a_tw || qa.answer_jp || qa.answer_tw }}
        </div>
      </details>
    </div>
  </section>

  <!-- 無內容時的替代顯示 -->
  <div v-if="!visible && section" class="empty-section-notice">
    <el-alert
      type="info"
      :closable="false"
      title="此區塊尚未準備完成"
      description="正在生成相關內容，請稍候重新載入。"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { shouldRenderSection } from '@/utils/contentGuards'
import { sectionVisible } from '@/utils/evidenceGuard'
import PlainTextBlock from './PlainTextBlock.vue'
import SuperCodeBlock from './SuperCodeBlock.vue'

const props = defineProps<{ 
  section: any 
}>()

// 先用內容守門檢查
const visible = computed(() => {
  return shouldRenderSection(props.section) && sectionVisible(props.section)
})

const copyCode = async (code: string) => {
  try {
    await navigator.clipboard.writeText(code)
    // 可以在這裡添加成功提示
  } catch (err) {
    console.error('複製失敗:', err)
  }
}
</script>

<style scoped>
.note-section {
  margin: 18px 0;
  border: 1px solid var(--border-soft);
}

.section-header {
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--primary);
}

.section-header h2 {
  margin: 8px 0;
  color: var(--primary);
}

.subtitle {
  color: var(--muted);
  font-size: 14px;
  margin: 4px 0 0 0;
}

.code-section {
  margin: 16px 0;
}

.code-block {
  margin: 12px 0;
  border: 1px solid var(--border-soft);
  border-radius: 12px;
  overflow: hidden;
}

.code-header {
  display: flex;
  justify-content: between;
  align-items: center;
  padding: 8px 12px;
  background: var(--surface);
  border-bottom: 1px solid var(--border-soft);
}

.language-tag {
  background: var(--primary);
  color: white;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
}

.copy-btn {
  background: var(--success);
  color: white;
  border: none;
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.code-explanation,
.evidence-source {
  padding: 8px 12px;
  background: var(--surface);
  color: var(--muted);
  font-size: 13px;
  border-top: 1px solid var(--border-soft);
}

.terminology-table {
  margin: 16px 0;
  width: 100%;
  overflow-x: auto;
}

.terminology-table .table-wrapper {
  width: 100%;
  overflow-x: auto;
  border-radius: 8px;
  border: 1px solid var(--border-soft);
}

.terminology-table table {
  width: 100%;
  min-width: 100%;
  border-collapse: collapse;
  table-layout: auto;
}

.terminology-table th,
.terminology-table td {
  padding: 8px 12px;
  border: 1px solid var(--border-soft);
  text-align: left;
  vertical-align: top;
}

.terminology-table th {
  background: var(--surface);
  font-weight: 600;
  color: var(--primary);
  white-space: nowrap;
}

.terminology-table td {
  word-wrap: break-word;
  word-break: break-word;
  hyphens: auto;
}

.problem-card {
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  padding: 12px;
  margin: 8px 0;
}

.problem-card h4 {
  margin: 0 0 8px 0;
  color: var(--accent);
}

.problem-card details {
  margin-top: 8px;
}

.answer {
  margin-top: 8px;
  padding: 8px;
  background: var(--surface);
  border-radius: 6px;
  color: var(--success);
}

.qa-section {
  margin: 16px 0;
}

.qa-item {
  border: 1px solid var(--border-soft);
  border-radius: 8px;
  margin: 8px 0;
}

.qa-item summary {
  padding: 12px;
  cursor: pointer;
  background: var(--surface);
  border-radius: 8px 8px 0 0;
}

.qa-item .answer {
  padding: 12px;
  background: var(--card);
  color: var(--fg-secondary);
}

.empty-section-notice {
  margin: 16px 0;
}
</style>
