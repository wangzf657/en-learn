<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  title: { type: String, required: true },
  sentences: { type: Array, default: () => [] },
  currentIndex: { type: Number, default: -1 },
  emptyText: { type: String, default: '暂无字幕数据' },
  cardAction: { type: String, default: 'seek' }, // 'seek' | 'repeat'
})

const emit = defineEmits(['seek', 'repeat'])
const root = ref(null)

function formatTime(s) {
  if (!s && s !== 0) return '0:00'
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${String(sec).padStart(2, '0')}`
}

watch(
  () => props.currentIndex,
  async (next) => {
    await nextTick()
    if (!root.value || next < 0) return
    const active = root.value.querySelector('.sentence-card.active')
    if (active) {
      active.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  },
)
</script>

<template>
  <section ref="root" class="panel-section card">
    <h2 class="panel-title">
      <span class="title-dot" aria-hidden="true"></span>
      {{ title }}
    </h2>
    <div v-if="sentences.length === 0" class="empty-state" style="padding: 40px 20px">
      <p>{{ emptyText }}</p>
    </div>
    <div v-else class="sentence-list">
      <div
        v-for="(s, i) in sentences"
        :key="i"
        class="sentence-card"
        :class="{ active: i === currentIndex }"
        @click="emit(cardAction, s)"
      >
        <div class="sentence-main">
          <div class="en-row">
            <p class="en">{{ s.en }}</p>
            <button
              type="button"
              class="seek-btn"
              :title="`跳转到 ${formatTime(s.start)}`"
              :aria-label="`跳转到 ${formatTime(s.start)}`"
              @click.stop="emit('seek', s)"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="5 3 19 12 5 21 5 3"></polygon>
              </svg>
              <span>{{ formatTime(s.start) }}</span>
            </button>
          </div>
          <p v-if="s.zh" class="zh">{{ s.zh }}</p>
        </div>

        <slot name="actions" :s="s" :i="i" />
      </div>
    </div>
  </section>
</template>

<style scoped>
.panel-section {
  padding: 22px 24px;
  max-height: calc(100svh - 176px);
  overflow-y: auto;
}

.panel-section.panel-fill {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-height: none;
  overflow: hidden;
}

.panel-section.panel-fill .panel-title {
  flex: none;
}

.panel-section.panel-fill .sentence-list {
  flex: 1 1 auto;
  overflow-y: auto;
  min-height: 0;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 22px;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 2px dashed var(--border);
  color: var(--ink);
}

.title-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: linear-gradient(140deg, var(--pink), var(--purple));
  box-shadow: 0 4px 10px rgba(160, 107, 255, 0.45);
}

.sentence-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sentence-card {
  padding: 16px 18px;
  border-radius: var(--radius-sm);
  border: 2px solid var(--border);
  background: var(--card);
  cursor: pointer;
  box-shadow: var(--shadow-pop);
  transition: border-color var(--transition), box-shadow var(--transition),
    transform var(--transition), background var(--transition);
}

.sentence-card:hover {
  border-color: var(--blue);
  transform: translateY(-3px);
  box-shadow: var(--shadow-sm);
}

.sentence-card:active {
  transform: translateY(0) scale(0.99);
}

.sentence-card.active {
  background: linear-gradient(180deg, #fff, var(--blue-bg));
  border-color: var(--blue);
  box-shadow: 0 0 0 4px rgba(63, 140, 255, 0.16), var(--shadow-sm);
  animation: pop-in 380ms var(--ease-bounce) backwards;
}

.sentence-main {
  margin-bottom: 0;
}

.en-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.en-row .en {
  flex: 1;
  min-width: 0;
}

/* 时间戳跳转按钮 */
.seek-btn {
  flex: none;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  margin-top: -2px;
  border-radius: var(--radius-pill);
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 700;
  color: var(--blue);
  background: var(--blue-bg);
  border: 2px solid transparent;
  box-shadow: var(--shadow-pop);
  transition: background var(--transition), color var(--transition),
    transform var(--transition), border-color var(--transition), box-shadow var(--transition);
}

.seek-btn:hover {
  border-color: var(--blue);
  transform: translateY(-2px);
  box-shadow: var(--shadow-sm);
}

.seek-btn:active {
  transform: translateY(1px) scale(0.94);
}

.seek-btn svg {
  width: 14px;
  height: 14px;
}

.en {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  line-height: 1.4;
  margin: 0 0 6px;
  color: var(--ink);
}

.zh {
  font-size: 14px;
  color: var(--muted);
  margin: 0;
}

@media (max-width: 1024px) {
  .panel-section {
    max-height: none;
  }
  .panel-section.panel-fill {
    height: auto;
    overflow: visible;
  }
  .panel-section.panel-fill .sentence-list {
    overflow: visible;
  }
}
</style>
