<template>
  <div id="vue-export-fab" class="export-fab">
    <el-button size="small" type="primary" @click="onMdClick">導出 Markdown</el-button>
    <el-button size="small" type="success" @click="onPdfClick">導出 PDF</el-button>
    <el-button size="small" type="warning" @click="onCsvClick">導出 Anki CSV</el-button>
  </div>
  
</template>

<script setup>
const props = defineProps({
  onMd: { type: Function, default: null },
  onPdf: { type: Function, default: null },
  onCsv: { type: Function, default: null }
})

function onMdClick() {
  if (props.onMd) return props.onMd()
  if (window.exportMarkdown) return window.exportMarkdown()
}
function onPdfClick() {
  if (props.onPdf) return props.onPdf()
  if (window.exportPDF) return window.exportPDF()
}
function onCsvClick() {
  if (props.onCsv) return props.onCsv()
  if (window.exportAnkiCSV) return window.exportAnkiCSV()
}
</script>

<style scoped>
.export-fab{
  position: fixed;
  right: 16px;
  bottom: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 60;
}
@media print { .export-fab { display: none; } }
</style>


