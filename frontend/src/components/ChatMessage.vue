<script setup>
defineProps({
  role: { type: String, required: true },   // 'user' | 'assistant'
  content: { type: String, required: true },
})
</script>

<template>
  <div :class="['message', role]">
    <div :class="['bubble', role]">
      <div class="role-label">{{ role === 'user' ? '我' : 'AI 助手' }}</div>
      <div class="content" v-text="content"></div>
    </div>
  </div>
</template>

<style scoped>
.message {
  display: flex;
  margin-bottom: 16px;
}

.message.user {
  justify-content: flex-end;
}

.message.assistant {
  justify-content: flex-start;
}

.bubble {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 12px;
}

.bubble.user {
  background: #1677ff;
  color: #fff;
  border-bottom-right-radius: 4px;
}

.bubble.assistant {
  background: #f0f0f0;
  color: #303133;
  border-bottom-left-radius: 4px;
}

.role-label {
  font-size: 12px;
  font-weight: bold;
  margin-bottom: 4px;
  opacity: 0.8;
}

.content {
  font-size: 15px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
