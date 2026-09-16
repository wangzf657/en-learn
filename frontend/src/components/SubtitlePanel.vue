<script setup>
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import { configureUtterance } from '../utils/tts.js'

const props = defineProps({
  title: { type: String, required: true },
  sentences: { type: Array, default: () => [] },
  currentIndex: { type: Number, default: -1 },
  emptyText: { type: String, default: '暂无字幕数据' },
})

const emit = defineEmits(['seek'])
const root = ref(null)

// 正在朗读的条目 key(台词 `s-0` / 词块 `w-0-1`),null 表示空闲
const speakingKey = ref(null)

function stopSpeaking() {
  if (!('speechSynthesis' in window)) return
  window.speechSynthesis.cancel()
  speakingKey.value = null
}

function toggleSpeak(text, key) {
  // jsdom 无此 API,防御式短路,保证测试不崩
  if (!('speechSynthesis' in window) || !text) return
  if (speakingKey.value === key) return stopSpeaking()
  const synth = window.speechSynthesis
  synth.cancel()
  const utter = configureUtterance(new SpeechSynthesisUtterance(text))
  const done = () => {
    if (speakingKey.value === key) speakingKey.value = null
  }
  utter.onend = done
  utter.onerror = done
  speakingKey.value = key
  synth.speak(utter)
}

onBeforeUnmount(stopSpeaking)

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
          <div class="en-row">
            <p class="en">{{ s.en }}</p>
            <button
              type="button"
              class="speak-btn"
              :class="{ speaking: speakingKey === `s-${i}` }"
              :title="speakingKey === `s-${i}` ? '停止朗读' : '朗读这句'"
              :aria-label="speakingKey === `s-${i}` ? '停止朗读' : '朗读这句'"
              @click.stop="toggleSpeak(s.en, `s-${i}`)"
            >
              <svg v-if="speakingKey !== `s-${i}`" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
                <path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path>
                <path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path>
              </svg>
              <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <rect x="7" y="7" width="10" height="10" rx="2"></rect>
              </svg>
            </button>
          </div>
          <p v-if="s.zh" class="zh">{{ s.zh }}</p>
        </div>

        <div v-if="s.words?.length" class="words">
          <div
            v-for="(w, j) in s.words"
            :key="j"
            class="word-chip"
            :class="{ speaking: speakingKey === `w-${i}-${j}` }"
            :title="`点击朗读 ${w.w}`"
            @click.stop="toggleSpeak(w.w, `w-${i}-${j}`)"
          >
            <span class="w-row">
              <span class="w">{{ w.w }}</span>
              <svg class="speak-hint" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon>
                <path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path>
              </svg>
            </span>
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
  margin-bottom: 10px;
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

/* 朗读按钮:比 .icon-btn 更小更轻,不抢台词本身 */
.speak-btn {
  flex: none;
  width: 38px;
  height: 38px;
  margin-top: -2px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: var(--blue);
  background: var(--blue-bg);
  border: 2px solid transparent;
  box-shadow: var(--shadow-pop);
  transition: background var(--transition), color var(--transition),
    transform var(--transition), border-color var(--transition), box-shadow var(--transition);
}

.speak-btn:hover {
  border-color: var(--blue);
  transform: translateY(-2px) rotate(-6deg);
  box-shadow: var(--shadow-sm);
}

.speak-btn:active {
  transform: translateY(1px) scale(0.94);
}

.speak-btn.speaking {
  color: #fff;
  background: var(--blue);
  border-color: var(--blue);
  animation: speak-pulse 1.1s ease-in-out infinite;
}

.speak-btn svg {
  width: 18px;
  height: 18px;
}

@keyframes speak-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(63, 140, 255, 0.45);
  }
  50% {
    box-shadow: 0 0 0 7px rgba(63, 140, 255, 0);
  }
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

.words {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.word-chip {
  display: inline-flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 12px;
  border-radius: var(--radius-xs);
  background: var(--purple-bg);
  border: 2px solid transparent;
  font-size: 16px;
  cursor: pointer;
  transition: transform var(--transition), border-color var(--transition),
    background var(--transition);
}

.word-chip:hover {
  transform: translateY(-2px) rotate(-1deg);
  border-color: rgba(160, 107, 255, 0.45);
}

.word-chip.speaking {
  border-color: var(--purple);
  background: #fff;
}

.word-chip .w-row {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.word-chip .speak-hint {
  flex: none;
  color: var(--purple);
  opacity: 0;
  transform: translateX(-3px);
  transition: opacity var(--transition), transform var(--transition);
}

.word-chip:hover .speak-hint,
.word-chip.speaking .speak-hint {
  opacity: 0.8;
  transform: none;
}

.word-chip .w {
  font-weight: 700;
  color: var(--ink);
}

.word-chip .phonetic {
  font-family: var(--font-mono);
  color: var(--purple);
  font-size: 13px;
}

.word-chip .note {
  color: var(--muted);
  font-size: 14px;
  line-height: 1.4;
}

@media (max-width: 1024px) {
  .panel-section {
    max-height: none;
  }
}
</style>
