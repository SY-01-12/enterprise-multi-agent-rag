<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../api/request'

const router = useRouter()

// --- 知识库列表 ---
const kbList = ref([])
const loadingKB = ref(false)

async function loadKBList() {
  loadingKB.value = true
  try {
    const res = await request.get('/api/knowledge-base/list')
    kbList.value = res.data
  } catch { } finally { loadingKB.value = false }
}

async function loadDocuments(kb) {
  try {
    const res = await request.get(`/api/knowledge-base/${kb.id}/documents`)
    kb.documents = res.data || []
    kb.docLoading = false
  } catch {
    kb.documents = []
    kb.docLoading = false
  }
}

// --- 创建知识库 ---
const showCreate = ref(false)
const createForm = ref({ name: '', description: '' })
const creating = ref(false)

async function handleCreate() {
  if (!createForm.value.name || !createForm.value.description) {
    ElMessage.warning('请填写名称和描述')
    return
  }
  creating.value = true
  try {
    await request.post('/api/knowledge-base/create', createForm.value)
    ElMessage.success('知识库创建成功')
    showCreate.value = false
    createForm.value = { name: '', description: '' }
    await loadKBList()
  } catch { } finally { creating.value = false }
}

// --- 删除知识库 ---
async function handleDelete(kb) {
  try {
    await ElMessageBox.confirm(`确定删除知识库「${kb.name}」？所有文档将一并删除。`, '确认删除', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
    })
    await request.delete(`/api/knowledge-base/delete/${kb.id}`)
    ElMessage.success('删除成功')
    await loadKBList()
  } catch { }
}

// --- 上传文档 ---
const uploadKbId = ref(null)
const uploadFile = ref(null)
const uploading = ref(false)
const uploadRef = ref(null)

async function handleUpload() {
  if (!uploadKbId.value || !uploadFile.value) {
    ElMessage.warning('请选择知识库和文件')
    return
  }
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('knowledge_base_id', uploadKbId.value)
    fd.append('file', uploadFile.value)
    const res = await request.post('/api/document/upload', fd)
    ElMessage.success(`上传成功`)

    // 自动处理
    try {
      const r = await request.post(`/api/document/process/${res.data.id}`)
      ElMessage.success(`处理完成：${r.data.chunks} chunks, ${r.data.vectors} vectors`)
    } catch { }

    uploadFile.value = null
    if (uploadRef.value) uploadRef.value.clearFiles()
    await loadKBList()
  } catch { } finally { uploading.value = false }
}

// --- 重新处理文档 ---
async function handleReprocess(doc) {
  try {
    await ElMessageBox.confirm('重新处理将清除旧向量并重新索引', '确认重新处理', {
      type: 'info', confirmButtonText: '确认', cancelButtonText: '取消',
    })
    const r = await request.post(`/api/document/process/${doc.id}`)
    ElMessage.success(`重新处理完成：${r.data.chunks} chunks, ${r.data.vectors} vectors`)
    await loadKBList()
  } catch { }
}

// --- 删除文档 ---
async function handleDeleteDoc(doc) {
  try {
    await ElMessageBox.confirm(`确定删除「${doc.filename}」？`, '确认删除', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
    })
    // Delete document endpoint not available, just refresh
    ElMessage.warning('请通过API删除文档')
  } catch { }
}

// --- 展开行 ---
const expandedRows = ref([])

function onExpandChange(row, rows) {
  // 非 owner 阻止展开
  if (!isOwner(row)) return
  // 保持已展开的 owner 行，过滤掉非 owner 行
  expandedRows.value = rows.filter(r => isOwner(r)).map(r => r.id)
  // 当前行是展开动作才加载文档
  if (rows.some(r => r.id === row.id)) {
    loadDocuments(row)
  }
}

function isOwner(kb) {
  const user = JSON.parse(localStorage.getItem('user') || '{}')
  return user.id === kb.owner_id
}

function getStatusTag(status) {
  const map = { pending: '待处理', processed: '已完成', failed: '失败' }
  const type = { pending: 'warning', processed: 'success', failed: 'danger' }
  return { text: map[status] || status, type: type[status] || 'info' }
}

onMounted(() => loadKBList())
</script>

<template>
  <div class="kb-page">
    <h2>知识库管理</h2>

    <div class="toolbar">
      <el-button type="primary" @click="showCreate = true">+ 新建知识库</el-button>
    </div>

    <!-- 知识库列表 -->
    <el-table :data="kbList" v-loading="loadingKB" border stripe row-key="id"
      :expand-row-keys="expandedRows" @expand-change="onExpandChange">
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="doc-section" v-if="isOwner(row)">
            <h4>📄 文档列表（{{ row.documents?.length || 0 }} 个）</h4>
            <el-table :data="row.documents" size="small" border v-if="row.documents?.length">
              <el-table-column prop="id" label="ID" width="60" />
              <el-table-column prop="filename" label="文件名" min-width="200" />
              <el-table-column prop="file_type" label="格式" width="70" />
              <el-table-column label="状态" width="100">
                <template #default="{ row: doc }">
                  <el-tag :type="getStatusTag(doc.status).type" size="small">
                    {{ getStatusTag(doc.status).text }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="created_at" label="上传时间" width="170" />
              <el-table-column label="操作" width="160">
                <template #default="{ row: doc }">
                  <el-button size="small" @click="handleReprocess(doc)">重新处理</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-else description="暂无文档，请上传" :image-size="60" />
          </div>
          <div class="doc-section" v-else>
            <el-empty description="仅知识库所有者可查看文档列表" :image-size="60" />
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="id" label="ID" width="80" sortable />
      <el-table-column prop="name" label="名称" min-width="150" sortable />
      <el-table-column prop="description" label="描述" min-width="200" />
      <el-table-column label="拥有者" width="120" sortable sort-by="owner_name">
        <template #default="{ row }">
          {{ row.owner_name || '用户#' + row.owner_id }}
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180" sortable />
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="router.push({ path: '/chat', query: { kb: row.id } })">💬 对话</el-button>
          <el-button v-if="isOwner(row)" type="danger" size="small" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 上传区域 -->
    <h3 style="margin-top: 32px;">上传文档</h3>
    <div class="upload-area">
      <el-select v-model="uploadKbId" placeholder="选择知识库" size="large" style="width: 240px;">
        <el-option v-for="kb in kbList" :key="kb.id" :label="kb.name" :value="kb.id" />
      </el-select>
      <el-upload ref="uploadRef" :auto-upload="false" :limit="1"
        accept=".pdf,.docx,.txt,.xlsx,.xlsm,.jpg,.jpeg,.png,.gif,.bmp,.webp"
        :on-change="(f) => uploadFile = f.raw" style="display: inline-block; margin: 0 12px;">
        <el-button size="large">选择文件</el-button>
      </el-upload>
      <el-button type="success" size="large" :loading="uploading" @click="handleUpload">
        {{ uploading ? '处理中...' : '上传并处理' }}
      </el-button>
    </div>
    <p class="hint">支持 PDF / DOCX / TXT / XLSX / 图片（JPG/PNG/GIF/BMP/WebP），最大 50MB。上传后自动解析+向量化+全文索引。</p>

    <!-- 创建知识库对话框 -->
    <el-dialog v-model="showCreate" title="新建知识库" width="480px">
      <el-form label-position="top">
        <el-form-item label="名称">
          <el-input v-model="createForm.name" placeholder="如：企业制度知识库" maxlength="100" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3"
            placeholder="简要描述知识库的用途和内容范围" maxlength="500" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">确定创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.kb-page { padding: 24px; max-width: 1200px; margin: 0 auto; }
h2 { margin-bottom: 20px; }
.toolbar { margin-bottom: 16px; }
.upload-area { display: flex; align-items: center; margin-top: 12px; }
.hint { color: #909399; font-size: 13px; margin-top: 8px; }
.doc-section { padding: 12px 24px; background: #fafafa; }
.doc-section h4 { margin: 0 0 8px 0; font-size: 14px; color: #303133; }
</style>
