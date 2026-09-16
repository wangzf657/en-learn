<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  title: { type: String, required: true },
  sentences: { type: Array, default: () => [] },
  currentIndex: { type: Number, default: -1 },
  emptyText: { type: String, default: '暂无字幕数据' },
})

const emit = defineEmits(['seek'])
const root = ref(null)

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
        @click="emit('seek', s)"
      >
        <div class="sentence-main">
          <p class="en">{{ s.en }}</p>
          <p v-if="s.zh" class="zh">{{ s.zh }}</p>
        </div>

        <div v-if="s.words?.length" class="words">
          <div v-for="(w, j) in s.words" :key="j" class="word-chip">
            <span class="w">{{ w.w }}</span>
            <span v-if="w.phonetic" class="phonetic">/{{ w.phonetic }}/</span>
            <span v-if="w.note" class="note">{{ w.note }}</span>
          </div>
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

.panel-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 22px;
  margin-bottom: 18px;
  padding-bottom: 14px;
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
  gap: 14px;
}

.sentence-card {
  padding: 18px 20px;
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
  margin-bottom: 10px;
}

.en {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 700;
  line-height: 1.5;
  margin: 0 0 6px;
  color: var(--ink);
}

.zh {
  font-size: 15px;
  color: var(--muted);
  margin: 0;
}

.words {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.word-chip {
  display: inline-flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 12px;
  border-radius: var(--radius-xs);
  background: var(--purple-bg);
  border: 2px solid transparent;
  font-size: 13px;
  transition: transform var(--transition), border-color var(--transition);
}

.word-chip:hover {
  transform: translateY(-2px) rotate(-1deg);
  border-color: rgba(160, 107, 255, 0.45);
}

.word-chip .w {
  font-weight: 700;
  color: var(--ink);
}

.word-chip .phonetic {
  font-family: var(--font-mono);
  color: var(--purple);
  font-size: 12px;
}

.word-chip .note {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.4;
}

@media (max-width: 1024px) {
  .panel-section {
    max-height: none;
  }
}
</style>
