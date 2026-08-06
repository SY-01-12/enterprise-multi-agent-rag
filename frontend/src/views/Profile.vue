<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '../stores/user'
import request from '../api/request'

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)

const profile = ref({ username: '', email: '', created_at: '' })

onMounted(async () => {
  loading.value = true
  try {
    const res = await request.get('/api/auth/me')
    profile.value = res.data
  } catch {
    ElMessage.error('获取用户信息失败')
  } finally {
    loading.value = false
  }
})

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning',
    })
    try { await request.post('/api/auth/logout') } catch { }
    userStore.logout()
    router.push('/login')
  } catch { }
}
</script>

<template>
  <div class="profile-page">
    <div class="profile-card" v-loading="loading">
      <div class="avatar">{{ profile.username?.[0]?.toUpperCase() || '?' }}</div>
      <h2>{{ profile.username }}</h2>
      <div class="info-list">
        <div class="info-row">
          <span class="label">邮箱</span>
          <span class="value">{{ profile.email }}</span>
        </div>
        <div class="info-row">
          <span class="label">注册时间</span>
          <span class="value">{{ profile.created_at?.slice(0, 10) }}</span>
        </div>
      </div>
      <div class="btn-group">
        <button class="btn logout-btn" @click="handleLogout">退出登录</button>
        <button class="btn back-btn" @click="router.push('/chat')">返回对话</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.profile-page {
  height: 100vh; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #f0f2f5 0%, #e8ecf1 100%);
}
.profile-card {
  width: 380px; padding: 40px; background: #fff;
  border-radius: 16px; box-shadow: 0 8px 30px rgba(0,0,0,0.08);
  text-align: center;
}
.avatar {
  width: 72px; height: 72px; line-height: 72px; border-radius: 50%;
  background: linear-gradient(135deg, #4f8fff, #2563eb);
  color: #fff; font-size: 28px; font-weight: 700;
  margin: 0 auto 16px;
}
h2 { font-size: 20px; color: #303133; margin-bottom: 24px; }
.info-list { text-align: left; }
.info-row {
  display: flex; justify-content: space-between; padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}
.label { color: #909399; font-size: 14px; }
.value { color: #303133; font-size: 14px; font-weight: 500; }
.btn-group {
  margin-top: 28px; display: flex; flex-direction: column; gap: 12px;
}
.btn {
  width: 100%; height: 44px; border: none; border-radius: 10px;
  font-size: 15px; font-weight: 600; cursor: pointer; transition: all 0.2s;
}
.logout-btn {
  background: #fff; color: #f56c6c; border: 1px solid #f56c6c;
}
.logout-btn:hover { background: #fef0f0; }
.back-btn {
  background: #f0f2f5; color: #606266; border: 1px solid #e8ecf1;
}
.back-btn:hover { background: #e8ecf1; }
</style>
