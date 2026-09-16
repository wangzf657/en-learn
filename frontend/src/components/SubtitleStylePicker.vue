<script setup>
import { onMounted } from 'vue'

const STYLE_KEY = 'enlearn.subtitleStyle'
const SIZE_KEY = 'enlearn.subtitleSize'

const props = defineProps({
  modelValue: { type: String, required: true },
  size: { type: String, default: 'sub-size-lg' },
})
const emit = defineEmits(['update:modelValue', 'update:size'])

const styles = [
  { key: 'sub-clean', label: '清晰' },
  { key: 'sub-cinema', label: '影院' },
  { key: 'sub-opaque', label: '黑底' },
  { key: 'sub-off', label: '关闭' },
]

const sizes = [
  { key: 'sub-size-md', label: '标准' },
  { key: 'sub-size-lg', label: '大' },
  { key: 'sub-size-xl', label: '特大' },
]

// 设置持久化:非法/缺失值安全回落默认。两个视图共用同一套键。
function loadPref(key, options, fallback) {
  try {
    const saved = localStorage.getItem(key)
    return options.some((o) => o.key === saved) ? saved : fallback
  } catch {
    return fallback
  }
}

function savePref(key, value) {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* 隐私模式等写入失败:忽略,不影响本次会话 */
  }
}

function pickStyle(key) {
  emit('update:modelValue', key)
  savePref(STYLE_KEY, key)
}

function pickSize(key) {
  emit('update:size', key)
  savePref(SIZE_KEY, key)
}

// 挂载时恢复上次选择;与当前值相同则不 emit,避免多余更新
onMounted(() => {
  const style = loadPref(STYLE_KEY, styles, props.modelValue)
  if (style !== props.modelValue) emit('update:modelValue', style)
  const size = loadPref(SIZE_KEY, sizes, props.size)
  if (size !== props.size) emit('update:size', size)
})
</script>

<template>
  <div class="style-picker">
    <select
      class="picker-select style-select"
      :value="modelValue"
      aria-label="字幕样式"
      title="字幕样式"
      @change="pickStyle($event.target.value)"
    >
      <option v-for="s in styles" :key="s.key" :value="s.key">{{ s.label }}</option>
    </select>
    <select
      class="picker-select size-select"
      :value="size"
      aria-label="字幕字号"
      title="字幕字号"
      @change="pickSize($event.target.value)"
    >
      <option v-for="s in sizes" :key="s.key" :value="s.key">{{ s.label }}</option>
    </select>
  </div>
</template>

<style scoped>
.style-picker {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.picker-select {
  min-height: 46px;
  padding: 8px 34px 8px 16px;
  border-radius: var(--radius-pill);
  background-color: #fff;
  border: 2px solid var(--border);
  font-family: var(--font-body);
  font-size: 15px;
  font-weight: 700;
  color: var(--blue);
  box-shadow: var(--shadow-pop);
  cursor: pointer;
  transition: border-color var(--transition), box-shadow var(--transition);
}

.picker-select:hover {
  border-color: var(--blue);
}
</style>
