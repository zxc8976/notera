<template>
  <el-config-provider :locale="zhTw">
    <router-view></router-view>
    <!-- 單例匯出 FAB -->
    <!-- 測試期移除導出浮動按鈕，避免干擾畫面 -->
    <!-- <ExportFab /> -->
  </el-config-provider>
</template>

<script setup>
import { ElConfigProvider } from 'element-plus'
import zhTw from 'element-plus/dist/locale/zh-tw.mjs'
import ExportFab from './components/ExportFab.vue'
</script>

<style>
/* 全局重置 */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
  background: #f5f7fa;
  color: #333;
}

/* Element Plus 深色模式修復 */
html.dark {
  --el-bg-color: #181818;
  --el-bg-color-overlay: #232323;
  --el-text-color-primary: #E0E0E0;
}
</style>
