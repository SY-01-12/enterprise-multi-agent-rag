<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '../stores/user'
import request from '../api/request'
import ChatMessage from '../components/ChatMessage.vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

// --- 模型选择 ---
const models = ref([])
const selectedModel = ref('')
async function loadModels() {
  try {
    const res = await request.get('/api/chat/models')
    models.value = res.data.models || []
    selectedModel.value = res.data.default || ''
  } catch { }
}

// --- 知识库选择 ---
const kbList = ref([])
const selectedKb = ref(0)   // 0 = 通用对话
async function loadKBList() {
  try {
    const res = await request.get('/api/knowledge-base/list')
    kbList.value = res.data || []
    // 从 URL 参数读取 kb
    const urlKb = parseInt(route.query.kb)
    if (urlKb && kbList.value.some(k => k.id === urlKb)) {
      selectedKb.value = urlKb
    }
  } catch { }
}

// --- 当前会话 ---
const question = ref('')
const messages = ref([])
const sessionId = ref(null)
const loading = ref(false)
const chatContainer = ref(null)

// --- 文件上传 ---
const attachedFile = ref(null)
const fileInputRef = ref(null)
function handleFileChange(e) {
  const f = e.target.files[0]
  if (f) attachedFile.value = f
}
function removeFile() {
  attachedFile.value = null
  if (fileInputRef.value) fileInputRef.value.value = ''
}

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

async function refreshSessionsSilent() {
  try {
    const res = await request.get('/api/chat/sessions')
    sessions.value = res.data
  } catch { }
}

async function selectSession(s) {
  sessionId.value = s.id
  try {
    const res = await request.get(`/api/chat/history/${s.id}`)
    const msgs = res.data || []
    messages.value = msgs.length === 0
      ? []
      : msgs.map(m => ({ role: m.role, content: m.content }))
    await scrollToBottom()
  } catch {
    ElMessage.error('加载会话记录失败')
  }
}

async function deleteSession(s, event) {
  event.stopPropagation()
  try {
    await request.delete(`/api/chat/sessions/${s.id}`)
    ElMessage.success('会话已删除')
    if (sessionId.value === s.id) newChat()
    await loadSessions()
  } catch { }
}

function newChat() {
  sessionId.value = null
  messages.value = []
}

// --- 发送消息 ---
async function handleSend() {
  const q = question.value.trim()
  if (!q) return

  const file = attachedFile.value
  const label = file ? `[文件: ${file.name}] ${q}` : q
  messages.value.push({ role: 'user', content: label })
  question.value = ''
  loading.value = true
  await scrollToBottom()

  const aiIndex = messages.value.length
  messages.value.push({ role: 'assistant', content: '', images: [], tools: [] })

  try {
    const token = localStorage.getItem('token')
    let resp

    if (file) {
      // 有附加文件 → /api/file/ask
      const fd = new FormData()
      fd.append('file', file)
      fd.append('question', q)
      if (sessionId.value) fd.append('session_id', sessionId.value)
      resp = await fetch('/api/file/ask', {
        method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: fd,
      })
      removeFile()
    } else {
      // 纯文本对话 → /api/chat/stream
      resp = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          knowledge_base_id: selectedKb.value,
          question: q,
          session_id: sessionId.value,
          model: selectedModel.value || null,
          mode: 'auto',
        }),
      })
    }

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
          refreshSessionsSilent()
        } else if (data.tool) {
          // 工具调用开始
          if (!messages.value[aiIndex].tools) messages.value[aiIndex].tools = []
          messages.value[aiIndex].tools.push({
            name: data.tool,
            label: data.label || data.tool,
            input: data.input || '',
          })
          await nextTick()
          await scrollToBottom()
        } else if (data.url) {
          // 图片生成完成
          if (!messages.value[aiIndex].images) messages.value[aiIndex].images = []
          messages.value[aiIndex].images.push({ url: data.url, prompt: data.prompt || '' })
          await nextTick()
          await scrollToBottom()
        } else if (data.token) {
          messages.value[aiIndex].content += data.token
          await nextTick()
          await scrollToBottom()
        } else if (data.done) {
          loading.value = false
        } else if (data.error) {
          ElMessage.error(data.error)
          messages.value[aiIndex].content = '[错误] ' + data.error
          loading.value = false
        }
      }
    }
  } catch (e) {
    console.error('SSE error:', e)
    ElMessage.error('连接失败：' + (e.message || '请检查后端服务'))
    if (messages.value[aiIndex].content === '') {
      messages.value[aiIndex].content = '[连接失败，请检查后端服务]'
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

onMounted(() => {
  loadSessions(); loadModels(); loadKBList(); scrollToBottom()
})
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
            <span class="session-del" @click="deleteSession(s, $event)">✕</span>
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
        <div class="header-left">
          <span class="mode-badge">🤖 AI 自动调度（知识库 + 通用）</span>
          <el-select v-model="selectedKb" size="default" style="width: 190px;" placeholder="选择知识库">
            <el-option label="💬 通用对话（无知识库）" :value="0" />
            <el-option v-for="kb in kbList" :key="kb.id" :label="kb.name" :value="kb.id" />
          </el-select>
          <el-select v-model="selectedModel" size="default" style="width: 210px;">
            <el-option
              v-for="m in models"
              :key="m.name"
              :label="m.label"
              :value="m.name"
            />
          </el-select>
        </div>
        <div class="user-area" @click="router.push('/profile')" title="个人中心">
          <span class="user-avatar">{{ userStore.user?.username?.[0]?.toUpperCase() || '?' }}</span>
          <span class="user-info">{{ userStore.user?.username }}</span>
        </div>
      </header>

      <main class="chat-body" ref="chatContainer">
        <div v-if="messages.length === 0" class="empty-hint">
          🤖 AI 自动调度 — 知识库检索 / 图片生成 / 文案创作 / 计算 / 翻译
        </div>
        <ChatMessage v-for="(msg, idx) in messages" :key="idx" :role="msg.role" :content="msg.content" :images="msg.images || []" :tools="msg.tools || []" />
        <div v-if="loading" class="typing-hint">AI 正在生成...</div>
      </main>

      <footer class="chat-footer">
        <!-- 已选文件标签 -->
        <div v-if="attachedFile" class="file-tag">
          📎 {{ attachedFile.name }}
          <span class="file-remove" @click="removeFile">✕</span>
        </div>
        <div class="input-row">
          <!-- 隐藏文件选择器 -->
          <input type="file" ref="fileInputRef" style="display:none"
            accept=".pdf,.docx,.txt,.xlsx,.xlsm,.jpg,.jpeg,.png,.gif,.bmp,.webp"
            @change="handleFileChange" />
          <el-button class="upload-btn" :disabled="loading" @click="fileInputRef.click()">
            📎
          </el-button>
          <el-input v-model="question" type="textarea" :rows="2"
            placeholder="输入问题，Enter 发送"
            :disabled="loading" resize="none" @keydown="handleKeydown" />
          <el-button type="primary" :disabled="loading || !question.trim()" @click="handleSend" class="send-btn">
            {{ loading ? '...' : '发送' }}
          </el-button>
        </div>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.chat-page { height: 100%; display: flex; background: #f0f2f5; }

/* --- 侧边栏 --- */
.sidebar {
  width: 260px; background: #fff; border-right: 1px solid #e8ecf1;
  display: flex; flex-direction: column; flex-shrink: 0;
}
.sidebar-header { padding: 14px; border-bottom: 1px solid #e8ecf1; }
.session-list { flex: 1; overflow-y: auto; }
.session-item {
  padding: 12px 14px 12px 18px; cursor: pointer; border-bottom: 1px solid #f5f5f5;
  transition: background 0.15s;
}
.session-item:hover { background: #f5f7fa; }
.session-item.active { background: #e8f0fe; border-left: 3px solid #2563eb; }
.session-row { display: flex; align-items: center; gap: 4px; }
.session-info { flex: 1; display: flex; flex-direction: column; gap: 2px; overflow: hidden; }
.session-title { font-size: 14px; color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.session-time { font-size: 12px; color: #c0c4cc; }
.session-del {
  flex-shrink: 0; width: 22px; height: 22px; line-height: 22px; text-align: center;
  font-size: 14px; color: #c0c4cc; border-radius: 4px; cursor: pointer; user-select: none;
  transition: all 0.15s;
}
.session-del:hover { color: #fff; background: #f56c6c; }
.no-sessions { text-align: center; color: #909399; padding: 40px 16px; font-size: 13px; }

/* --- 右侧主区域 --- */
.chat-main { flex: 1; display: flex; flex-direction: column; min-width: 0; background: #f7f8fa; }
.chat-header {
  height: 56px; padding: 0 24px; background: #fff;
  border-bottom: 1px solid #e8ecf1; display: flex; align-items: center;
  justify-content: space-between; flex-shrink: 0; box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.header-left { display: flex; align-items: center; gap: 12px; }
.user-area {
  display: flex; align-items: center; gap: 8px; cursor: pointer;
  padding: 4px 12px 4px 4px; border-radius: 20px; transition: background 0.15s;
}
.user-area:hover { background: #f0f2f5; }
.user-avatar {
  width: 30px; height: 30px; line-height: 30px; border-radius: 50%;
  background: linear-gradient(135deg, #4f8fff, #2563eb);
  color: #fff; font-size: 13px; font-weight: 700; text-align: center; flex-shrink: 0;
}
.user-info { color: #303133; font-size: 14px; font-weight: 500; }
.mode-badge {
  font-size: 14px; font-weight: 600; color: #2563eb;
  background: #eff6ff; padding: 6px 14px; border-radius: 8px; flex-shrink: 0;
  white-space: nowrap;
}
.chat-body {
  flex: 1; overflow-y: auto; padding: 24px 28px; min-height: 0;
  background:
    radial-gradient(ellipse at 50% 0%, rgba(37,99,235,0.02) 0%, transparent 60%),
    linear-gradient(180deg, #f7f8fa 0%, #f0f2f5 100%);
}
.empty-hint { text-align: center; color: #b0b5be; margin-top: 100px; font-size: 16px; }
.typing-hint { color: #909399; font-size: 13px; margin: 8px 0 8px 22px; }
.chat-footer {
  padding: 16px 24px 24px; background: #fff;
  border-top: 1px solid #e8ecf1; display: flex; flex-direction: column; gap: 10px;
  flex-shrink: 0; box-shadow: 0 -1px 3px rgba(0,0,0,0.03);
}
.file-tag {
  display: inline-flex; align-items: center; gap: 6px; font-size: 13px;
  background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; padding: 4px 12px;
  color: #2563eb; max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.file-remove { cursor: pointer; font-weight: bold; color: #f56c6c; }
.input-row { display: flex; gap: 10px; align-items: flex-end; }
.upload-btn {
  height: 44px; flex-shrink: 0; border-radius: 10px;
  border: 1px solid #d9dce1; background: #fafbfc; color: #606266;
  transition: all 0.2s;
}
.upload-btn:hover { border-color: #2563eb; color: #2563eb; background: #eff6ff; }
.send-btn {
  height: 44px; flex-shrink: 0; border-radius: 10px;
  background: linear-gradient(135deg, #4f8fff, #2563eb);
  border: none; font-weight: 600; box-shadow: 0 2px 6px rgba(37,99,235,0.3);
  transition: all 0.2s;
}
.send-btn:hover { box-shadow: 0 4px 12px rgba(37,99,235,0.4); transform: translateY(-1px); }
.chat-footer :deep(.el-textarea__inner) {
  border-radius: 12px; border-color: #d9dce1; font-size: 15px;
  padding: 12px 16px; line-height: 1.5; background: #f9fafb;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.chat-footer :deep(.el-textarea__inner:focus) {
  border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,0.1);
  background: #fff;
}
</style>
