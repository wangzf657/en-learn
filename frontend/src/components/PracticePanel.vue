<script setup>
import { ref, computed } from 'vue'
import { speak } from '../utils/tts.js'

// V2.0 带学练习面板:双 Tab(跟读练习 / 家长带学),消费教学 JSON 的四板
// (words 重点单词 / sentences 重点短句 / dialogues 亲子对话 / guide 带学脚本)。
// 旧格式数据(只有全量 sentences)也能用:短句板照常渲染,带学 Tab 走空态。
const props = defineProps({
  practice: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['seek', 'repeat'])

const tab = ref('practice')

const words = computed(() => (Array.isArray(props.practice?.words) ? props.practice.words : []))
const sentences = computed(() =>
  Array.isArray(props.practice?.sentences) ? props.practice.sentences : [],
)
const dialogues = computed(() =>
  Array.isArray(props.practice?.dialogues) ? props.practice.dialogues : [],
)
const guide = computed(() => {
  const g = props.practice?.guide
  return g && typeof g === 'object' ? g : null
})

const hasPractice = computed(
  () => words.value.length > 0 || sentences.value.length > 0 || dialogues.value.length > 0,
)
const hasGuide = computed(
  () => !!(guide.value && (guide.value.goal || guide.value.before?.length || guide.value.after?.length)),
)

const speakingKey = ref('')

async function speakLine(key, text) {
  if (speakingKey.value === key) return
  speakingKey.value = key
  await speak(text)
  if (speakingKey.value === key) speakingKey.value = ''
}

function repeatWord(w) {
  emit('repeat', {
    en: w.w,
    zh: w.zh,
    words: w.note ? [{ w: w.w, note: w.note }] : undefined,
  })
}

// 整段对话带进跟读:en/zh 拼整段供整段评分,segments 逐行传入——
// 弹窗优先用显式断句,一行一整句跟读,不再按标点二次切分
function repeatDialogue(d) {
  emit('repeat', {
    en: d.lines.map((ln) => ln.en).join(' '),
    zh: d.lines.map((ln) => ln.zh).join(' '),
    segments: d.lines.map((ln) => ln.en),
  })
}

function formatTime(s) {
  if (!s && s !== 0) return '0:00'
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${String(sec).padStart(2, '0')}`
}
</script>

<template>
  <section class="panel-section card practice-panel">
    <div class="tabs" role="tablist" aria-label="练习面板">
      <button
        type="button"
        class="tab"
        :class="{ active: tab === 'practice' }"
        role="tab"
        :aria-selected="tab === 'practice'"
        @click="tab = 'practice'"
      >
        跟读练习
      </button>
      <button
        type="button"
        class="tab"
        :class="{ active: tab === 'guide' }"
        role="tab"
        :aria-selected="tab === 'guide'"
        @click="tab = 'guide'"
      >
        家长带学
      </button>
    </div>

    <!-- Tab 1:跟读练习 -->
    <div v-if="tab === 'practice'" class="tab-body">
      <div v-if="!hasPractice" class="empty-state" style="padding: 40px 20px">
        <p>本集暂无练习内容</p>
        <p class="hint">需用新版练习卡 JSON 重新生成</p>
      </div>

      <template v-else>
        <div v-if="words.length" class="block">
          <h3 class="block-title">🎯 重点单词</h3>
          <div class="word-chips">
            <button
              v-for="(w, i) in words"
              :key="i"
              type="button"
              class="word-chip"
              :title="w.note || w.zh"
              @click="repeatWord(w)"
            >
              <span class="w-en">{{ w.w }}</span>
              <span class="w-zh">{{ w.zh }}</span>
            </button>
          </div>
        </div>

        <div v-if="sentences.length" class="block">
          <h3 class="block-title">💬 重点短句</h3>
          <div class="sentence-list">
            <div
              v-for="(s, i) in sentences"
              :key="i"
              class="sentence-card"
              title="点击跟读"
              @click="emit('repeat', s)"
            >
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
              <p v-if="s.note" class="note">{{ s.note }}</p>
            </div>
          </div>
        </div>

        <div v-if="dialogues.length" class="block">
          <h3 class="block-title">🎭 亲子场景对话</h3>
          <div class="dialogue-list">
            <div v-for="(d, i) in dialogues" :key="i" class="dialogue-card">
              <div class="scene-row">
                <div class="scene">【{{ d.scene }}】</div>
                <button
                  type="button"
                  class="repeat-mini"
                  title="整段对话带进跟读练习"
                  @click="repeatDialogue(d)"
                >
                  🎤 跟读本段
                </button>
              </div>
              <div
                v-for="(ln, k) in d.lines"
                :key="k"
                class="line"
                :class="[ln.speaker, { speaking: speakingKey === `${i}-${k}` }]"
              >
                <span class="speaker" aria-hidden="true">{{ ln.speaker === 'parent' ? '👩' : '🧒' }}</span>
                <button type="button" class="line-body" :title="'点击朗读'" @click="speakLine(`${i}-${k}`, ln.en)">
                  <p class="en">{{ ln.en }}</p>
                  <p class="zh">{{ ln.zh }}</p>
                </button>
              </div>
              <p v-if="d.tip" class="tip">💡 {{ d.tip }}</p>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- Tab 2:家长带学 -->
    <div v-else class="tab-body">
      <div v-if="!hasGuide" class="empty-state" style="padding: 40px 20px">
        <p>本集暂无带学脚本</p>
        <p class="hint">需用新版练习卡 JSON 重新生成</p>
      </div>

      <template v-else>
        <div class="goal-card">
          <span class="goal-label">🎯 本集目标</span>
          <p class="goal-text">{{ guide.goal }}</p>
        </div>

        <div v-if="guide.before?.length" class="guide-block">
          <h3 class="block-title">▶ 播前 · 跟孩子说</h3>
          <p v-for="(t, i) in guide.before" :key="i" class="guide-item">{{ t }}</p>
        </div>

        <div v-if="guide.during?.length" class="guide-block">
          <h3 class="block-title">👀 播中 · 一起玩</h3>
          <p v-for="(t, i) in guide.during" :key="i" class="guide-item">{{ t }}</p>
        </div>

        <div v-if="guide.after?.length" class="guide-block">
          <h3 class="block-title">❓ 播后 · 问一问</h3>
          <p v-for="(t, i) in guide.after" :key="i" class="guide-item">{{ t }}</p>
        </div>

        <div v-if="guide.tips?.length" class="guide-block">
          <h3 class="block-title">💡 给你的提示</h3>
          <p v-for="(t, i) in guide.tips" :key="i" class="guide-item">{{ t }}</p>
        </div>
      </template>
    </div>
  </section>
</template>

<style scoped>
.panel-section {
  padding: 18px 20px;
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

/* 双 Tab 头(固定,不随内容滚动) */
.tabs {
  flex: none;
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  padding-bottom: 14px;
  border-bottom: 2px dashed var(--border);
}

.tab {
  flex: 1;
  padding: 10px 12px;
  min-height: 42px;
  border-radius: var(--radius-pill);
  font-size: 15px;
  font-weight: 700;
  color: var(--muted);
  background: var(--card);
  border: 2px solid var(--border);
  box-shadow: var(--shadow-pop);
  transition: transform var(--transition), background var(--transition),
    color var(--transition), border-color var(--transition);
}

.tab:hover {
  border-color: var(--blue);
  color: var(--blue);
  transform: translateY(-2px);
}

.tab.active {
  background: var(--grad-blue);
  color: #fff;
  border-color: transparent;
  box-shadow: var(--shadow-blue), var(--shadow-pop);
}

.tab-body {
  flex: 1 1 auto;
  overflow-y: auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.block-title {
  font-size: 16px;
  margin: 0;
  color: var(--ink);
}

.hint {
  font-size: 13px;
  color: var(--muted);
  margin: 6px 0 0;
}

/* 重点单词 chips */
.word-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.word-chip {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 10px 16px;
  border-radius: var(--radius-sm);
  border: 2px solid var(--border);
  background: var(--card);
  cursor: pointer;
  box-shadow: var(--shadow-pop);
  transition: border-color var(--transition), box-shadow var(--transition),
    transform var(--transition);
}

.word-chip:hover {
  border-color: var(--pink);
  transform: translateY(-3px);
  box-shadow: var(--shadow-sm);
}

.word-chip:active {
  transform: translateY(0) scale(0.97);
}

.w-en {
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
  color: var(--ink);
}

.w-zh {
  font-size: 13px;
  color: var(--muted);
}

/* 重点短句卡(沿用台词卡样式) */
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

.en-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.en-row .en {
  flex: 1;
  min-width: 0;
}

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
  text-align: left;
}

.zh {
  font-size: 14px;
  color: var(--muted);
  margin: 0;
}

.note {
  font-size: 13px;
  color: var(--secondary);
  margin: 6px 0 0;
}

/* 亲子对话卡 */
.dialogue-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.dialogue-card {
  padding: 14px 16px;
  border-radius: var(--radius-sm);
  border: 2px solid var(--border);
  background: var(--card);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.scene-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.scene {
  font-size: 15px;
  font-weight: 700;
  color: var(--ink);
}

.line {
  display: flex;
  align-items: center;
  gap: 8px;
}

.speaker {
  flex: none;
  font-size: 20px;
  line-height: 1;
}

.line-body {
  flex: 1 1 auto;
  min-width: 0;
  padding: 8px 12px;
  border-radius: var(--radius-xs);
  background: var(--bg);
  border: 2px solid transparent;
  cursor: pointer;
  text-align: left;
  transition: background var(--transition), border-color var(--transition);
}

.line.child .line-body {
  background: var(--blue-bg);
}

.line-body:hover {
  border-color: var(--blue);
}

.line.speaking .line-body {
  border-color: var(--pink);
  box-shadow: 0 0 0 3px rgba(255, 122, 165, 0.18);
}

.line-body .en {
  font-size: 16px;
  margin: 0 0 2px;
}

.line-body .zh {
  font-size: 13px;
}

.repeat-mini {
  flex: none;
  padding: 8px 12px;
  min-height: 36px;
  border-radius: var(--radius-pill);
  font-size: 13px;
  font-weight: 700;
  color: var(--pink);
  background: var(--card);
  border: 2px solid var(--border);
  box-shadow: var(--shadow-pop);
  transition: border-color var(--transition), transform var(--transition);
}

.repeat-mini:hover {
  border-color: var(--pink);
  transform: translateY(-2px);
}

.tip {
  font-size: 13px;
  color: var(--muted);
  margin: 2px 0 0;
}

/* 家长带学 */
.goal-card {
  padding: 14px 16px;
  border-radius: var(--radius-sm);
  border: 2px solid var(--pink);
  background: linear-gradient(180deg, #fff, #fff4f8);
  box-shadow: var(--shadow-pop);
}

.goal-label {
  display: block;
  font-size: 13px;
  font-weight: 700;
  color: var(--pink);
  margin-bottom: 4px;
}

.goal-text {
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
  margin: 0;
  line-height: 1.5;
}

.guide-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.guide-item {
  margin: 0;
  padding: 12px 14px;
  border-radius: var(--radius-xs);
  background: var(--bg);
  font-size: 15px;
  line-height: 1.6;
  color: var(--ink);
}

@media (max-width: 1024px) {
  .panel-section {
    max-height: none;
  }
  .panel-section.panel-fill {
    height: auto;
    overflow: visible;
  }
  .panel-section.panel-fill .tab-body {
    overflow: visible;
  }
}
</style>
