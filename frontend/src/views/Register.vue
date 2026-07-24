<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '../api/request'

const router = useRouter()

const form = ref({
  username: '',
  email: '',
  password: '',
  confirm_password: '',
})
const loading = ref(false)

async function handleRegister() {
  if (!form.value.username || !form.value.email || !form.value.password) {
    ElMessage.warning('请填写所有必填项')
    return
  }
  if (form.value.password !== form.value.confirm_password) {
    ElMessage.warning('两次密码不一致')
    return
  }

  loading.value = true
  try {
    await request.post('/api/auth/register', {
      username: form.value.username,
      email: form.value.email,
      password: form.value.password,
      confirm_password: form.value.confirm_password,
    })
    ElMessage.success('注册成功，请登录')
    router.push('/login')
  } catch {
    // 错误已由拦截器处理
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="register-container">
    <div class="register-card">
      <h1 class="register-title">创建账号</h1>
      <p class="register-subtitle">注册企业知识库 RAG 系统</p>

      <el-form @submit.prevent="handleRegister" label-position="top">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="3-50 个字符" size="large" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" placeholder="example@company.com" size="large" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="至少 6 个字符" size="large" show-password />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="form.confirm_password" type="password" placeholder="再次输入密码" size="large" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" size="large" :loading="loading" @click="handleRegister" class="reg-btn">
            {{ loading ? '注册中...' : '注 册' }}
          </el-button>
        </el-form-item>
      </el-form>

      <p class="switch-link">
        已有账号？<router-link to="/login">去登录</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped>
.register-container {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.register-card {
  width: 420px;
  padding: 40px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
}
.register-title { text-align: center; font-size: 24px; color: #303133; margin-bottom: 8px; }
.register-subtitle { text-align: center; color: #909399; margin-bottom: 28px; }
.reg-btn { width: 100%; }
.switch-link { text-align: center; color: #909399; font-size: 14px; margin-top: 16px; }
.switch-link a { color: #1677ff; text-decoration: none; }
</style>
