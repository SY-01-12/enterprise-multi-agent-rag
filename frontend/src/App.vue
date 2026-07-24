<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from './stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const showNav = computed(() => {
  return userStore.isLoggedIn && route.path !== '/login' && route.path !== '/register'
})

function handleLogout() {
  userStore.logout()
  router.push('/login')
}
</script>

<template>
  <div id="app-root">
    <!-- 顶部导航（登录后显示） -->
    <nav v-if="showNav" class="top-nav">
      <span class="nav-brand">企业知识库 RAG</span>
      <div class="nav-links">
        <router-link to="/chat" :class="{ active: route.path === '/chat' }">AI 问答</router-link>
        <router-link to="/knowledge" :class="{ active: route.path === '/knowledge' }">知识库管理</router-link>
      </div>
      <div class="nav-right">
        <span class="nav-user">{{ userStore.user?.username }}</span>
        <el-button size="small" @click="handleLogout">退出</el-button>
      </div>
    </nav>

    <!-- 页面内容 -->
    <main :class="{ 'with-nav': showNav }">
      <router-view />
    </main>
  </div>
</template>

<style>
html, body, #app { margin: 0; padding: 0; height: 100%; font-family: 'Microsoft YaHei', sans-serif; }

#app-root { height: 100%; display: flex; flex-direction: column; }

.top-nav {
  height: 50px; background: #001529; color: #fff;
  display: flex; align-items: center; padding: 0 24px; gap: 32px; flex-shrink: 0;
}
.nav-brand { font-size: 16px; font-weight: bold; white-space: nowrap; }
.nav-links { display: flex; gap: 8px; flex: 1; }
.nav-links a {
  color: rgba(255,255,255,0.65); text-decoration: none; padding: 6px 14px; border-radius: 6px; font-size: 14px;
}
.nav-links a:hover { color: #fff; background: rgba(255,255,255,0.1); }
.nav-links a.active { color: #fff; background: #1677ff; }
.nav-right { display: flex; align-items: center; gap: 12px; }
.nav-user { color: rgba(255,255,255,0.85); font-size: 13px; }

main.with-nav { height: calc(100vh - 50px); overflow: hidden; }
main:not(.with-nav) { height: 100vh; overflow: hidden; }
</style>
