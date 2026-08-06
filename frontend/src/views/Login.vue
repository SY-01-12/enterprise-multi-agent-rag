<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '../api/request'
import { useUserStore } from '../stores/user'

const router = useRouter()
const userStore = useUserStore()

const form = ref({
  username: '',
  password: '',
})
const loading = ref(false)

async function handleLogin() {
  if (!form.value.username || !form.value.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }

  loading.value = true
  try {
    const res = await request.post('/api/auth/login', {
      username: form.value.username,
      password: form.value.password,
    })
    const { access_token } = res.data

    // 拉取完整用户信息（含 id、username、email 等）
    const meRes = await request.get('/api/auth/me', {
      headers: { Authorization: `Bearer ${access_token}` }
    })
    userStore.setAuth(access_token, meRes.data)
    ElMessage.success('登录成功')
    router.push('/chat')
  } catch {
    // 错误已由拦截器处理
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-container">
    <div class="login-card">
      <h1 class="login-title">企业 AI 助手</h1>
      <p class="login-subtitle">登录以继续</p>

      <el-form @submit.prevent="handleLogin" label-position="top">
        <el-form-item label="用户名">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            size="large"
            clearable
          />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            size="large"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            @click="handleLogin"
            class="login-btn"
          >
            {{ loading ? '登录中...' : '登 录' }}
          </el-button>
        </el-form-item>
      </el-form>

      <p class="switch-link">
        没有账号？<router-link to="/register">去注册</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped>
.login-container {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-card {
  width: 400px;
  padding: 40px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}

.login-title {
  text-align: center;
  font-size: 24px;
  color: #303133;
  margin-bottom: 8px;
}

.login-subtitle {
  text-align: center;
  color: #909399;
  margin-bottom: 32px;
}

.login-btn {
  width: 100%;
}
.switch-link { text-align: center; color: #909399; font-size: 14px; margin-top: 16px; }
.switch-link a { color: #1677ff; text-decoration: none; }
</style>
