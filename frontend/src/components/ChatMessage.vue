<script setup>
import { computed, ref } from 'vue'
import { marked } from 'marked'

const props = defineProps({
  role: { type: String, required: true },
  content: { type: String, required: true },
  images: { type: Array, default: () => [] },  // [{url, prompt}]
  tools: { type: Array, default: () => [] },    // [{name, input}]
})

const hoveredImg = ref(null)

// 从文本中提取 Markdown 图片 ![alt](url)，转为 cards
const extractMdImages = computed(() => {
  const imgs = []
  const re = /!\[([^\]]*)\]\((https?:\/\/[^\s)]+)\)/g
  let m
  while ((m = re.exec(props.content || '')) !== null) {
    imgs.push({ url: m[2], prompt: m[1] || '' })
  }
  return imgs
})

// 合并：SSE ImageGenerated 事件图片 + Markdown 图片（按 URL 去重）
const allImages = computed(() => {
  const seen = new Set()
  const result = []
  for (const img of [...(props.images || []), ...extractMdImages.value]) {
    if (!seen.has(img.url)) {
      seen.add(img.url)
      result.push(img)
    }
  }
  return result
})

// 过滤文本：去掉 Markdown 图片语法和裸 URL，来源标注降级为小字
const sanitized = computed(() => {
  let text = props.content || ''
  // 去掉 Markdown 图片语法 ![alt](url)
  text = text.replace(/!\[[^\]]*\]\(https?:\/\/[^\s)]+\)/g, '')
  // 去掉 "图片链接: http://xxx.png" 整行
  text = text.replace(/图片链接[:：]\s*https?:\/\/[^\s]*/gi, '')
  // 去掉裸的图片 URL
  text = text.replace(/https?:\/\/[^\s]*\.(?:png|jpg|jpeg|gif|webp)[^\s]*/gi, '')
  // 来源标注用小字展示
  text = text.replace(/📎\s*来源[：:]\s*《([^》]+)》/g, '<span class=\"source-tag\">📎 来源：《$1》</span>')
  // 合并多余空行
  text = text.replace(/\n{3,}/g, '\n\n')
  return text.trim()
})

const html = computed(() => {
  if (!sanitized.value) return ''
  try {
    return marked.parse(sanitized.value, { breaks: true })
  } catch {
    return sanitized.value
  }
})

async function downloadImage(url, prompt) {
  try {
    const resp = await fetch(url)
    const blob = await resp.blob()
    const blobUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = blobUrl
    a.download = (prompt || 'image') + '.png'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(blobUrl)
  } catch {
    // 跨域降级：直接打开
    window.open(url, '_blank')
  }
}
</script>

<template>
  <div :class="['message', role]">
    <div :class="['bubble', role]">
      <div class="role-label">{{ role === 'user' ? '我' : 'AI' }}</div>

      <!-- 工具调用指示 -->
      <div v-for="(tool, i) in tools" :key="'tool-'+i" class="tool-call">
        <span class="tool-name">{{ tool.label || tool.name }}</span>
      </div>

      <!-- 生成的图片卡片 -->
      <div v-for="(img, i) in allImages" :key="'img-'+i" class="image-card"
        @mouseenter="hoveredImg = i" @mouseleave="hoveredImg = null">
        <img :src="img.url" :alt="img.prompt" />
        <div class="image-overlay" v-show="hoveredImg === i">
          <button class="download-btn" @click="downloadImage(img.url, img.prompt)">
            ⬇ 下载
          </button>
        </div>
        <span v-if="img.prompt" class="image-prompt">{{ img.prompt }}</span>
      </div>

      <div class="content" v-html="html"></div>
    </div>
  </div>
</template>

<style scoped>
.message {
  display: flex; margin-bottom: 20px;
}
.message.user { justify-content: flex-end; }
.message.assistant { justify-content: flex-start; }

.bubble {
  max-width: 75%; padding: 14px 18px; border-radius: 16px;
  line-height: 1.65; font-size: 15px;
}
.bubble.user {
  background: linear-gradient(135deg, #4f8fff, #2563eb);
  color: #fff; border-bottom-right-radius: 6px;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.25);
}
.bubble.assistant {
  background: #fff; color: #303133;
  border: 1px solid #e8ecf1; border-bottom-left-radius: 6px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}

/* ── 图片卡片 ── */
.tool-call {
  display: inline-flex; align-items: center; gap: 6px; margin-bottom: 8px;
  padding: 4px 12px; border-radius: 20px; font-size: 13px;
  background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe;
  max-width: 260px;
}
.tool-name {
  font-weight: 500;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.image-card {
  position: relative; margin-bottom: 10px; border-radius: 12px; overflow: hidden;
  max-width: 360px; border: 1px solid #e8ecf1; background: #fafafa;
  cursor: pointer; display: inline-block;
}
.image-card img {
  width: 100%; max-height: 320px; object-fit: cover; display: block;
}
.image-overlay {
  position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center;
  transition: opacity 0.2s;
}
.download-btn {
  background: #fff; color: #333; border: none; padding: 8px 20px;
  border-radius: 20px; font-size: 14px; font-weight: 600; cursor: pointer;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2); transition: transform 0.15s;
}
.download-btn:hover { transform: scale(1.05); }
.image-prompt {
  display: block; padding: 6px 12px; font-size: 13px; color: #909399;
  background: #fafafa; text-align: center;
}

/* ── 文本内容 ── */
.role-label {
  font-size: 12px; font-weight: 600; margin-bottom: 6px;
  opacity: 0.7; letter-spacing: 0.5px;
}
.content { font-size: 15px; word-break: break-word; }

/* 来源标注 */
.content :deep(.source-tag) {
  font-size: 12px;
  font-weight: normal;
  color: #909399;
  display: inline-block;
  margin-top: 8px;
}
/* Markdown 图片自适应（文本中嵌入的图片） */
.content :deep(img) {
  max-width: 260px; max-height: 260px; object-fit: contain;
  border-radius: 8px; margin: 8px 0; display: block; cursor: pointer;
}
.content :deep(pre) {
  background: #f5f6f8; padding: 10px 14px; border-radius: 8px;
  overflow-x: auto; font-size: 13px; border: 1px solid #e8ecf1;
}
.content :deep(code) {
  background: #f0f1f3; color: #d63384; padding: 2px 6px;
  border-radius: 4px; font-size: 13px;
}
.content :deep(pre code) { background: none; padding: 0; color: #333; }

/* user 侧的样式覆盖 */
.bubble.user .content :deep(pre) { background: rgba(255,255,255,0.15); border-color: transparent; }
.bubble.user .content :deep(code) { background: rgba(255,255,255,0.2); color: #fff; }
.bubble.user .content :deep(pre code) { background: none; color: #fff; }
</style>
