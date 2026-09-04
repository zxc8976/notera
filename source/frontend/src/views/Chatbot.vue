<template>
  <ChatbotLayout @new-chat="startNewChat">
    <!-- 聊天區域 -->
    <div class="chat-area">
      <!-- 消息區域 -->
      <div class="messages" ref="messagesArea">
        <!-- 歡迎消息 -->
        <div v-if="messages.length === 0" class="welcome">
          <div class="welcome-icon">🤖</div>
          <h3>{{ welcomeTitle }}</h3>
          <p>{{ welcomeText }}</p>
        </div>

        <!-- 聊天消息 -->
        <div v-for="(message, index) in messages" :key="index" 
             class="msg" :class="message.role">
          <div class="avatar">
            <span v-if="message.role === 'user'">👤</span>
            <span v-else>🤖</span>
          </div>
          <div class="content" v-html="message.html"></div>
        </div>

        <!-- 載入指示器 -->
        <div v-if="isLoading" class="msg assistant">
          <div class="avatar">🤖</div>
          <div class="typing">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>

      <!-- 輸入區域 -->
      <div class="input-section">
        <div class="input-box">
          <textarea 
            v-model="userInput" 
            :placeholder="inputPlaceholder"
            @keydown="handleKeydown"
            :disabled="isLoading"
            rows="1"
            ref="textareaInput">
          </textarea>
          <button class="send" @click="sendMessage" :disabled="!userInput.trim() || isLoading">
            ↑
          </button>
        </div>
        <div class="disclaimer">
          <p>{{ disclaimerText }}</p>
        </div>
      </div>
    </div>
  </ChatbotLayout>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { marked } from 'marked'
import ChatbotLayout from '../layouts/ChatbotLayout.vue'
import { useLanguage } from '../composables/useLanguage.js'

// 使用語言系統
const { currentLanguage, t } = useLanguage()

// 計算屬性用於翻譯
const welcomeTitle = computed(() => t('aiAssistantGreeting') || '您好！我是您的AI助手')
const welcomeText = computed(() => t('welcomeMessage') || '我可以幫助您解答問題、分析文件、編寫代碼等。請告訴我您需要什麼協助？')
const inputPlaceholder = computed(() => t('sendMessagePlaceholder') || '傳送訊息給 AI 助手...')
const disclaimerText = computed(() => t('aiDisclaimer') || 'AI 可能會發生錯誤。請查核重要資訊。')

// 聊天狀態
const messages = ref([])
const userInput = ref('')
const isLoading = ref(false)
const messagesArea = ref(null)
const textareaInput = ref(null)

// 初始化
onMounted(() => {
  console.log('Chatbot mounted, current language:', currentLanguage.value)
  console.log('Welcome title:', welcomeTitle.value)
  console.log('Welcome text:', welcomeText.value)
})

const startNewChat = () => {
  messages.value = []
  userInput.value = ''
}

const handleKeydown = (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    sendMessage()
  }
}

const sendMessage = async () => {
  if (!userInput.value.trim() || isLoading.value) return

  const userMessage = {
    role: 'user',
    content: userInput.value,
    html: marked.parse(userInput.value)
  }

  messages.value.push(userMessage)
  const currentInput = userInput.value
  userInput.value = ''
  isLoading.value = true

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'qwen3-vl:4b',
        messages: messages.value.map(msg => ({
          role: msg.role,
          content: msg.content
        }))
      })
    })

    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
    
    const data = await response.json()

    const botMessage = {
      role: 'assistant',
      content: data.reply,
      html: marked.parse(data.reply)
    }

    messages.value.push(botMessage)
    scrollToBottom()
  } catch (error) {
    console.error('發送訊息時出錯', error)
    showError(t('sendMessageFailed'))
  } finally {
    isLoading.value = false
  }
}

const showError = (message) => {
  const errorMessage = {
    role: 'assistant',
    content: `❌ ${message}`,
    html: `<p style="color: #ff6b6b;">❌ ${message}</p>`
  }
  messages.value.push(errorMessage)
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesArea.value) {
      messagesArea.value.scrollTop = messagesArea.value.scrollHeight
    }
  })
}
</script>

<style scoped>
/* 聊天區域 */
.chat-area {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 64px);
  background: var(--bg-color, #1a1a1a);
}

/* 消息區域 */
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
  background: var(--bg-color, #1a1a1a);
}

/* 歡迎消息 */
.welcome {
  text-align: center;
  padding: 3rem 1.5rem;
  color: var(--text-secondary, #b3b3b3);
}

.welcome-icon {
  font-size: 4rem;
  margin-bottom: 1.5rem;
}

.welcome h3 {
  font-size: 1.25rem;
  margin-bottom: 1rem;
  color: var(--text-color, #ffffff);
}

.welcome p {
  font-size: 1rem;
  line-height: 1.6;
  max-width: 600px;
  margin: 0 auto;
}

/* 聊天消息 */
.msg {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
  animation: fadeIn 0.3s ease;
}

.msg.user {
  flex-direction: row-reverse;
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--primary-color, #0078d7);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.2rem;
  flex-shrink: 0;
}

.msg.user .avatar {
  background: var(--success-color, #28a745);
}

.content {
  flex: 1;
  background: var(--card-bg, #2d2d2d);
  border: 1px solid var(--border-color, #333);
  border-radius: 8px;
  padding: 1rem;
  max-width: 70%;
  word-wrap: break-word;
}

.msg.user .content {
  background: rgba(0, 120, 215, 0.2);
  border-color: var(--primary-color, #0078d7);
}

/* 打字動畫 */
.typing {
  display: flex;
  gap: 4px;
  padding: 1rem;
}

.typing span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-secondary, #b3b3b3);
  animation: typing 1.4s infinite ease-in-out;
}

.typing span:nth-child(1) { 
  animation-delay: -0.32s; 
}

.typing span:nth-child(2) { 
  animation-delay: -0.16s; 
}

@keyframes typing {
  0%, 80%, 100% {
    transform: scale(0);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

/* 輸入區域 */
.input-section {
  border-top: 1px solid var(--border-color, #333);
  background: var(--card-bg, #2d2d2d);
  padding: 1.5rem;
}

.input-box {
  display: flex;
  gap: 0.5rem;
  align-items: flex-end;
  max-width: 1000px;
  margin: 0 auto;
}

.input-box textarea {
  flex: 1;
  min-height: 44px;
  max-height: 120px;
  padding: 0.5rem 1rem;
  border: 1px solid var(--border-color, #333);
  border-radius: 8px;
  background: var(--bg-color, #1a1a1a);
  color: var(--text-color, #ffffff);
  font-family: inherit;
  font-size: 1rem;
  resize: none;
  transition: all 0.15s ease;
}

.input-box textarea:focus {
  outline: none;
  border-color: var(--primary-color, #0078d7);
  box-shadow: 0 0 0 2px rgba(0, 120, 215, 0.2);
}

.input-box textarea:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.send {
  width: 44px;
  height: 44px;
  border: none;
  border-radius: 50%;
  background: var(--primary-color, #0078d7);
  color: white;
  font-size: 1.2rem;
  cursor: pointer;
  transition: all 0.15s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.send:hover:not(:disabled) {
  background: var(--primary-hover, #106ebe);
  transform: translateY(-1px);
}

.send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

/* 免責聲明 */
.disclaimer {
  text-align: center;
  margin-top: 0.5rem;
}

.disclaimer p {
  font-size: 0.75rem;
  color: var(--text-secondary, #b3b3b3);
  margin: 0;
}

/* 動畫 */
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 響應式設計 */
@media (max-width: 768px) {
  .messages {
    padding: 1rem;
  }
  
  .content {
    max-width: 85%;
  }
  
  .input-section {
    padding: 1rem;
  }
  
  .welcome {
    padding: 1.5rem 1rem;
  }
}
</style>
