<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '../stores/user'
import request from '../api/request'
import KnowledgeSelect from '../components/KnowledgeSelect.vue'
import ChatMessage from '../components/ChatMessage.vue'

const userStore = useUserStore()

// --- 知识库 ---
const kbId = ref(0)
const kbSelectRef = ref(null)
function onKbSelect(id) { kbId.value = id }

// --- 当前会话 ---
const question = ref('')
const messages = ref([])
const sessionId = ref(null)
const loading = ref(false)
const chatContainer = ref(null)

// --- 历史会话侧边栏 ---
const sessions = ref([])
const loadingSessions = ref(false)

async function loadSessions() {
  loadingSessions.value = true
  try {
    const res = await request.get('/api/chat/sessions')
    sessions.value = res.data
  } catch { } finally { loadingSessions.value = false }
}

// 静默刷新：更新列表但不显示loading（发消息后自动更新侧边栏）
async function refreshSessionsSilent() {
  try {
    const res = await request.get('/api/chat/sessions')
    sessions.value = res.data
  } catch { }
}

async function selectSession(s) {
  sessionId.value = s.id
  kbId.value = s.knowledge_base_id   // 同步选中知识库
  try {
    const res = await request.get(`/api/chat/history/${s.id}`)
    const msgs = res.data || []
    if (msgs.length === 0) {
      // 会话存在但无消息记录（异常情况）
      messages.value = []
    } else {
      messages.value = msgs.map(m => ({ role: m.role, content: m.content }))
    }
    await scrollToBottom()
  } catch (e) {
    ElMessage.error('加载会话记录失败')
  }
}

async function deleteSession(s, event) {
  event.stopPropagation()
  try {
    await request.delete(`/api/chat/sessions/${s.id}`)
    ElMessage.success('会话已删除')
    if (sessionId.value === s.id) { newChat() }
    await loadSessions()
  } catch { }
}

function newChat() {
  sessionId.value = null
  messages.value = []
  kbId.value = 0
}

// --- 发送消息（SSE 流式） ---
async function handleSend() {
  const q = question.value.trim()
  if (!q) return
  if (kbId.value == null) { ElMessage.warning('请先选择知识库或通用对话'); return }

  messages.value.push({ role: 'user', content: q })
  question.value = ''
  loading.value = true
  await scrollToBottom()

  const aiIndex = messages.value.length
  messages.value.push({ role: 'assistant', content: '' })

  try {
    const token = localStorage.getItem('token')
    const resp = await fetch('http://127.0.0.1:8000/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ knowledge_base_id: kbId.value, question: q, session_id: sessionId.value }),
    })

    if (!resp.ok) {
      const errText = await resp.text()
      throw new Error(errText || `HTTP ${resp.status}`)
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      // 正确切分 SSE 行：最后一行可能不完整，保留到下次循环
      const parts = buffer.split('\n')
      buffer = parts.pop() || ''

      for (const line of parts) {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data: ')) continue
        const jsonStr = trimmed.slice(6)

        let data
        try { data = JSON.parse(jsonStr) } catch { continue }

        if (data.session_id) {
          sessionId.value = data.session_id
          refreshSessionsSilent()   // 后台更新侧边栏，不转圈
        } else if (data.token) {
          messages.value[aiIndex].content += data.token
          await nextTick()
          await scrollToBottom()
        } else if (data.error) {
          ElMessage.error(data.error)
          messages.value[aiIndex].content = '[错误] ' + data.error
        }
      }
    }
  } catch (e) {
    console.error('SSE error:', e)
    ElMessage.error('连接失败：' + (e.message || '请检查 Ollama 是否运行'))
    if (messages.value[aiIndex].content === '') {
      messages.value[aiIndex].content = '[连接失败，请检查后端和 Ollama 服务]'
    }
  } finally {
    loading.value = false
  }
}

async function scrollToBottom() {
  await nextTick()
  if (chatContainer.value) chatContainer.value.scrollTop = chatContainer.value.scrollHeight
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
}

onMounted(() => { loadSessions(); scrollToBottom() })
</script>

<template>
  <div class="chat-page">
    <!-- ===== 左侧：历史会话列表 ===== -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <el-button type="primary" size="small" @click="newChat" style="width:100%">+ 新对话</el-button>
      </div>
      <div class="session-list" v-loading="loadingSessions">
        <div
          v-for="s in sessions"
          :key="s.id"
          :class="['session-item', { active: sessionId === s.id }]"
          @click="selectSession(s)"
        >
          <div class="session-row">
            <div class="session-info">
              <span class="session-title">{{ s.title || '新对话' }}</span>
              <span class="session-time">{{ s.created_at?.slice(0, 10) }}</span>
            </div>
            <el-button class="session-del" size="small" type="danger" plain @click="deleteSession(s, $event)">✕</el-button>
          </div>
        </div>
        <div v-if="sessions.length === 0 && !loadingSessions" class="no-sessions">
          暂无历史对话
        </div>
      </div>
    </aside>

    <!-- ===== 右侧：聊天主区域 ===== -->
    <div class="chat-main">
      <header class="chat-header">
        <KnowledgeSelect v-model="kbId" @select="onKbSelect" />
        <span class="user-info">{{ userStore.user?.username }}</span>
      </header>

      <main class="chat-body" ref="chatContainer">
        <div v-if="messages.length === 0" class="empty-hint">
          选择知识库，输入问题开始对话
        </div>
        <ChatMessage v-for="(msg, idx) in messages" :key="idx" :role="msg.role" :content="msg.content" />
        <div v-if="loading" class="typing-hint">AI 正在生成...</div>
      </main>

      <footer class="chat-footer">
        <el-input v-model="question" type="textarea" :rows="2"
          placeholder="输入问题，Enter 发送"
          :disabled="loading" resize="none" @keydown="handleKeydown" />
        <el-button type="primary" :disabled="loading || !question.trim()" @click="handleSend" class="send-btn">
          {{ loading ? '...' : '发送' }}
        </el-button>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.chat-page { height: 100%; display: flex; background: #f5f7fa; }

/* --- 侧边栏 --- */
.sidebar {
  width: 260px; background: #fff; border-right: 1px solid #e4e7ed;
  display: flex; flex-direction: column; flex-shrink: 0;
}
.sidebar-header { padding: 12px; border-bottom: 1px solid #e4e7ed; }
.session-list { flex: 1; overflow-y: auto; }
.session-item {
  padding: 10px 12px 10px 16px; cursor: pointer; border-bottom: 1px solid #f0f0f0;
}
.session-item:hover { background: #f0f5ff; }
.session-item.active { background: #e6f0ff; border-left: 3px solid #1677ff; }
.session-row { display: flex; align-items: center; gap: 4px; }
.session-info { flex: 1; display: flex; flex-direction: column; gap: 2px; overflow: hidden; }
.session-title { font-size: 14px; color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.session-time { font-size: 12px; color: #c0c4cc; }
.session-del { flex-shrink: 0; }
.no-sessions { text-align: center; color: #909399; padding: 40px 16px; font-size: 13px; }

/* --- 右侧主区域 --- */
.chat-main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.chat-header {
  height: 56px; padding: 0 20px; background: #fff;
  border-bottom: 1px solid #e4e7ed; display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;
}
.user-info { color: #606266; font-size: 14px; }
.chat-body { flex: 1; overflow-y: auto; padding: 20px; min-height: 0; }
.empty-hint { text-align: center; color: #909399; margin-top: 80px; font-size: 16px; }
.typing-hint { color: #909399; font-size: 13px; margin-left: 10px; }
.chat-footer {
  padding: 12px 20px 20px; background: #fff;
  border-top: 1px solid #e4e7ed; display: flex; gap: 12px; align-items: flex-end; flex-shrink: 0;
}
.send-btn { height: 40px; flex-shrink: 0; }
</style>
