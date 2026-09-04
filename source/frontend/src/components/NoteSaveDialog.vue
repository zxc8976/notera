<template>
  <el-dialog
    v-model="visible"
    title="保存筆記"
    width="600px"
    :before-close="handleClose"
  >
    <el-form :model="form" label-width="100px">
      <el-form-item label="分類">
        <el-select v-model="form.category" placeholder="請選擇分類" style="width: 100%">
          <el-option
            v-for="cat in categories"
            :key="cat"
            :label="cat"
            :value="cat"
          />
        </el-select>
      </el-form-item>
      
      <el-form-item label="標題">
        <el-input v-model="form.title" placeholder="請輸入筆記標題" />
      </el-form-item>
      
      <el-form-item label="內容預覽">
        <div class="content-preview">
          {{ contentPreview }}
        </div>
      </el-form-item>
      
      <!-- 暫存刪除選項 -->
      <el-form-item v-if="hasTmpData" label="暫存處理">
        <el-alert
          title="檢測到暫存資料"
          type="info"
          :description="`此影片有 ${tmpInfo.type === 'scenes' ? tmpInfo.scene_count + ' 個場景' : tmpInfo.image_count + ' 張圖片'} 的暫存資料`"
          show-icon
          :closable="false"
          style="margin-bottom: 12px"
        />
        <el-checkbox v-model="form.deleteTmp">
          保存筆記後自動刪除暫存資料（建議勾選以節省空間）
        </el-checkbox>
      </el-form-item>
    </el-form>
    
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">
          {{ saving ? '保存中...' : '保存筆記' }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage, ElDialog, ElForm, ElFormItem, ElSelect, ElOption, ElInput, ElAlert, ElCheckbox, ElButton } from 'element-plus'
import axios from 'axios'

const props = defineProps({
  modelValue: Boolean,
  content: String,
  tmpFilename: String,
  tmpInfo: Object
})

const emit = defineEmits(['update:modelValue', 'saved'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const form = ref({
  category: '日本電子課程/サーバーサイドプログラミングⅡ',
  title: '',
  deleteTmp: true
})

const categories = ref([
  "日本電子課程/サーバーサイドプログラミングⅡ",
  "日本電子課程/ITストラテジー", 
  "日本電子課程/クライアントサイドプログラミングⅡ",
  "日本電子課程/機械学習Ⅱ",
  "日本電子課程/オブジェクト指向分析・設計Ⅰ",
  "日本電子課程/データマイニング",
  "日本電子課程/AIプログラミングⅡ",
  "日本電子課程/エッジコンピューティングⅠ・Ⅱ"
])

const saving = ref(false)

const contentPreview = computed(() => {
  if (!props.content) return '無內容'
  const text = props.content.replace(/[#*`]/g, '').trim()
  return text.length > 100 ? text.substring(0, 100) + '...' : text
})

const hasTmpData = computed(() => {
  return props.tmpFilename && props.tmpInfo && (props.tmpInfo.scene_count > 0 || props.tmpInfo.image_count > 0)
})

// 自動生成標題
watch(() => props.content, (newContent) => {
  if (newContent && !form.value.title) {
    // 從內容中提取第一個標題作為預設標題
    const titleMatch = newContent.match(/^#\s+(.+)$/m)
    if (titleMatch) {
      form.value.title = titleMatch[1].trim()
    } else {
      // 如果沒有標題，使用時間戳
      form.value.title = `筆記_${new Date().toLocaleString('zh-TW')}`
    }
  }
}, { immediate: true })

async function handleSave() {
  if (!form.value.title.trim()) {
    ElMessage.error('請輸入筆記標題')
    return
  }
  
  if (!props.content) {
    ElMessage.error('筆記內容不能為空')
    return
  }
  
  saving.value = true
  
  try {
    const formData = new FormData()
    formData.append('category', form.value.category)
    formData.append('title', form.value.title)
    formData.append('content', props.content)
    
    // 如果有暫存資料且用戶選擇刪除
    if (hasTmpData.value && form.value.deleteTmp) {
      formData.append('tmp_filename', props.tmpFilename)
    }
    
    const response = await axios.post('/api/notes/save', formData)
    
    if (response.data.status === 'ok') {
      ElMessage.success('筆記保存成功！')
      emit('saved', {
        category: form.value.category,
        title: form.value.title,
        file: response.data.note,
        deletedTmp: hasTmpData.value && form.value.deleteTmp
      })
      handleClose()
    }
  } catch (error) {
    console.error('保存筆記失敗:', error)
    ElMessage.error('保存筆記失敗：' + (error.response?.data?.detail || error.message))
  } finally {
    saving.value = false
  }
}

function handleClose() {
  visible.value = false
  // 重置表單
  form.value.title = ''
  form.value.deleteTmp = true
}
</script>

<style scoped>
.content-preview {
  max-height: 100px;
  overflow-y: auto;
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
  color: #606266;
  font-size: 14px;
  line-height: 1.5;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

:deep(.el-alert) {
  border-radius: 6px;
}

:deep(.el-alert__title) {
  font-weight: 600;
}
</style>