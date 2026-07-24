<script setup>
import { ref, onMounted, watch } from 'vue'
import request from '../api/request'

const props = defineProps({ modelValue: { type: Number, default: 0 } })
const emit = defineEmits(['select', 'update:modelValue'])

const kbList = ref([])
const selectedKb = ref(props.modelValue)
const loading = ref(false)
const error = ref(false)

// 父组件通过 v-model 同步 kbId 时更新下拉框
watch(() => props.modelValue, (val) => { selectedKb.value = val })

async function loadKnowledgeBases() {
  loading.value = true
  error.value = false
  try {
    const res = await request.get('/api/knowledge-base/list')
    kbList.value = res.data || []
    if (kbList.value.length > 0 && selectedKb.value === 0) {
      selectedKb.value = kbList.value[0].id
    }
    emit('select', selectedKb.value)
  } catch {
    error.value = true
    selectedKb.value = 0
    emit('select', 0)
  } finally {
    loading.value = false
  }
}

function handleChange(val) {
  emit('update:modelValue', val)
  emit('select', val)
}

onMounted(() => { loadKnowledgeBases() })
</script>

<template>
  <div class="kb-select">
    <span class="label">知识库：</span>
    <el-select
      v-model="selectedKb"
      placeholder="选择知识库"
      :loading="loading"
      @change="handleChange"
      size="default"
      style="width: 220px;"
    >
      <el-option label="💬 通用对话（无需知识库）" :value="0" />
      <el-option
        v-for="kb in kbList"
        :key="kb.id"
        :label="kb.name"
        :value="kb.id"
      />
    </el-select>
    <el-tag v-if="error" type="danger" size="small">后端未连接</el-tag>
  </div>
</template>

<style scoped>
.kb-select { display: flex; align-items: center; gap: 8px; }
.label { color: #606266; font-size: 14px; white-space: nowrap; }
</style>
