<script setup>
defineProps({ modelValue: { type: String, required: true } })
const emit = defineEmits(['update:modelValue'])

const styles = [
  { key: 'sub-clean', label: '清晰' },
  { key: 'sub-cinema', label: '影院' },
  { key: 'sub-opaque', label: '黑底' },
  { key: 'sub-off', label: '关闭' },
]
</script>

<template>
  <div class="style-picker" role="group" aria-label="字幕样式">
    <button
      v-for="s in styles"
      :key="s.key"
      type="button"
      class="style-btn"
      :class="{ active: modelValue === s.key }"
      @click="emit('update:modelValue', s.key)"
    >
      {{ s.label }}
    </button>
  </div>
</template>

<style scoped>
.style-picker {
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  background: var(--bg);
  border-radius: var(--radius-pill);
  border: 1px solid var(--border);
}

.style-btn {
  padding: 5px 12px;
  border-radius: var(--radius-pill);
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
  background: transparent;
  transition: background var(--transition), color var(--transition);
}

.style-btn:hover {
  color: var(--blue);
}

.style-btn.active {
  background: #fff;
  color: var(--blue);
  box-shadow: var(--shadow-sm);
}
</style>
